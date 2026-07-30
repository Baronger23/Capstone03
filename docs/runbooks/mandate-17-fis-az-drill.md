# Runbook — Diễn tập mất AZ bằng AWS FIS (Mandate 17 req#2)

**Mục tiêu:** chứng minh **mất trọn một Availability Zone một cách bất ngờ** mà luồng browse → cart → checkout vẫn giữ SLO.
**Mục tiêu diễn tập:** `ap-southeast-1b` · **Thời lượng fault:** `PT5M` · **Chủ trì:** CDO-02
**Công cụ:** AWS Fault Injection Service — template `aws_fis_experiment_template.az_connectivity_loss` (`infra/live/production/fis-chaos-experiments.tf`)

> **Vì sao FIS chứ không phải `cordon`/`drain`:** Directive #17 tự phân biệt với Directive #3 — *"#3 là bảo trì **có kế hoạch**; đây là **chết bất ngờ**"*. `cordon`+`drain` evict pod lịch sự, tôn trọng PDB, chạy preStop → đó là bài #3. FIS `disrupt-connectivity` cắt đứt traffic vào/ra AZ đúng như sự cố thật.

---

## 0. Nguyên tắc an toàn (không được bỏ)

1. **Không bao giờ chạy khi thiếu stop condition.** Alarm `tf3-fis-stop-storefront-5xx` phải ở trạng thái `OK` trước khi bắn.
2. **Luôn có người trực** với lệnh `stop-experiment` sẵn trong terminal.
3. **Chỉ bắn `ap-southeast-1b`.** KHÔNG bắn `1a` trong lần này — xem §2.
4. Fault tự hết sau `PT5M`; **không kéo dài** vì "muốn xem thêm".
5. Nếu bất kỳ tiêu chí ABORT nào (§7) chạm → dừng ngay, không cần xin phép thêm.

---

## 1. Điều kiện tiên quyết

| Việc | Cách kiểm |
|---|---|
| Terraform đã apply | `aws fis list-experiment-templates --region ap-southeast-1` phải thấy template |
| Lấy template id | `TPL=$(aws fis list-experiment-templates --region ap-southeast-1 --query 'experimentTemplates[?tags.mandate==`mandate-17`].id' --output text)` |
| Alarm tồn tại + OK | `aws cloudwatch describe-alarms --alarm-names tf3-fis-stop-storefront-5xx --query 'MetricAlarms[].StateValue' --output text` |
| Đã báo CDO-01 + AIO02 | Experiment ảnh hưởng pod của họ trong 1b — **báo trước, không bắn lén** |
| Tunnel SSM mở | `scripts/kube-tunnel.sh` — endpoint SSM nằm ở **1a** nên vẫn sống khi bắn 1b |

---

## 2. ⚠️ Bẫy phải xử lý TRƯỚC khi bắn

### 2.1. Prometheus có thể đang nằm trong 1b → bắn xong là mù

Anti-affinity REL-17-04 đẩy Grafana và Prometheus ra 2 AZ khác nhau. Lần verify gần nhất: **Grafana ở 1a, Prometheus ở 1b**. Nếu giữ nguyên mà bắn 1b thì **mất luôn nguồn metric ngay giữa bài đo** — không còn gì để chứng minh SLO.

**Kiểm:**
```bash
for l in grafana prometheus; do
  N=$(kubectl -n techx-tf3 get pods -l app.kubernetes.io/name=$l --field-selector status.phase=Running -o jsonpath='{.items[0].spec.nodeName}')
  echo "$l -> $N -> $(kubectl get node $N -o jsonpath='{.metadata.labels.topology\.kubernetes\.io/zone}')"
done
```

**Nếu Prometheus đang ở 1b — đẩy nó sang 1c trước khi bắn:**
```bash
# cordon các node 1b để pod mới không quay lại đó
for n in $(kubectl get nodes -l topology.kubernetes.io/zone=ap-southeast-1b -o name); do kubectl cordon ${n#node/}; done
kubectl -n techx-tf3 delete pod -l app.kubernetes.io/name=prometheus   # reschedule
# doi Running roi uncordon
kubectl -n techx-tf3 wait --for=condition=Ready pod -l app.kubernetes.io/name=prometheus --timeout=180s
for n in $(kubectl get nodes -l topology.kubernetes.io/zone=ap-southeast-1b -o name); do kubectl uncordon ${n#node/}; done
```
Đích cần đạt: **Grafana 1a, Prometheus 1c** → cả hai đều ngoài vùng bắn.

### 2.2. Load-generator nằm đâu

Nếu `load-generator` ở 1b thì tải tự dừng giữa bài → số liệu vô nghĩa.
```bash
kubectl -n techx-tf3 get pod -l opentelemetry.io/name=load-generator -o wide
```
Nếu ở 1b: cordon 1b rồi xoá pod cho nó nhảy sang AZ khác (như §2.1).

### 2.3. Không phụ thuộc một nguồn bằng chứng duy nhất

Xếp theo khả năng sống sót — **luôn chạy cả 3**:

| Nguồn | Sống sót khi mất 1b? | Vai trò |
|---|---|---|
| **Vòng lặp curl từ máy ngoài** | ✅ luôn sống | **Bằng chứng mạnh nhất** — đúng góc nhìn khách hàng |
| **CloudWatch ALB metrics** | ✅ phía AWS | Số liệu độc lập, mentor kiểm chứng được |
| Grafana / Prometheus | ⚠️ chỉ khi đã xử §2.1 | Panel SLO đẹp để trình bày |

---

## 3. Preflight (T-30 phút)

```bash
export AWS_PROFILE=techx-new
SP=./drill-evidence && mkdir -p $SP

# 3.1 Bản đồ node -> AZ (BASELINE)
kubectl get nodes -o custom-columns='NODE:.metadata.name,ZONE:.metadata.labels.topology\.kubernetes\.io/zone,CAP:.metadata.labels.karpenter\.sh/capacity-type' | tee $SP/00-nodes-before.txt

# 3.2 Pod nào đang ở 1b (đây là thứ sẽ bị cắt)
kubectl get pods -A -o wide | grep -F "$(kubectl get nodes -l topology.kubernetes.io/zone=ap-southeast-1b -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | head -1)" | tee $SP/01-pods-in-1b.txt

# 3.3 Phân bố luồng ra tiền theo AZ
kubectl -n techx-tf3 get pods -o custom-columns='SVC:.metadata.labels.opentelemetry\.io/name,POD:.metadata.name,NODE:.spec.nodeName' --no-headers | sort | tee $SP/02-revenue-placement-before.txt

# 3.4 PDB + trạng thái
kubectl -n techx-tf3 get pdb | tee $SP/03-pdb-before.txt

# 3.5 Storefront khoẻ
curl -s -o /dev/null -w "before / -> %{http_code}\n" https://d2tn71186d7ilz.cloudfront.net/ | tee $SP/04-storefront-before.txt
```

**Chốt trước khi đi tiếp:** mỗi service ra tiền phải có **≥1 replica NGOÀI 1b**. Nếu có service nào 100% nằm trong 1b → **dừng, sửa placement trước**, vì bài test sẽ fail vì lý do đã biết trước.

---

## 4. T-5 phút — bật thu thập

**Terminal A — vòng lặp curl ghi log liên tục (để chạy suốt bài):**
```bash
while true; do
  printf '%s %s %s\n' "$(date -u +%FT%TZ)" \
    "$(curl -s -o /dev/null -w '%{http_code} %{time_total}' --max-time 10 https://d2tn71186d7ilz.cloudfront.net/)" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://d2tn71186d7ilz.cloudfront.net/api/products)"
  sleep 2
done | tee ./drill-evidence/10-external-probe.log
```

**Terminal B — tải:** bật load-generator (hoặc Locust) ở mức ổn định, ghi lại mức user.

**Terminal C — lệnh dừng khẩn, gõ sẵn KHÔNG Enter:**
```bash
aws fis stop-experiment --id <EXPERIMENT_ID> --region ap-southeast-1
```

**Terminal D — quay màn hình Grafana** (Request rate, Success rate, p95, Node count).

---

## 5. T-0 — Bắn

```bash
aws fis start-experiment \
  --experiment-template-id "$TPL" \
  --region ap-southeast-1 \
  --tags Name=m17-az1b-drill \
  | tee ./drill-evidence/20-experiment-start.json

EXP=$(jq -r '.experiment.id' ./drill-evidence/20-experiment-start.json)
echo "EXPERIMENT_ID=$EXP"   # dán ngay vào Terminal C
```

Ghi lại **giờ UTC chính xác lúc bắn** — mọi mốc sau đối chiếu theo nó.

---

## 6. Trong lúc chạy (5 phút)

```bash
# trạng thái experiment
watch -n 15 "aws fis get-experiment --id $EXP --region ap-southeast-1 --query 'experiment.state' --output json"
```

Quan sát và ghi nhận:

| Thời điểm | Cần thấy gì |
|---|---|
| ~30–60s | Pod ở 1b chuyển `NotReady`; endpoint bị gỡ khỏi Service |
| 1–3 phút | Traffic dồn về replica ở AZ còn lại; **`10-external-probe.log` vẫn toàn `200`** |
| 1–3 phút | Grafana: request rate giữ, success rate không sụt dưới SLO |
| suốt bài | `checkout` success ≥ 99%, browse/cart ≥ 99.5%, p95 < 1s |

**Chụp trong lúc chạy** (không đợi xong):
```bash
kubectl get nodes -o wide | tee ./drill-evidence/30-nodes-during.txt
kubectl -n techx-tf3 get pods -o wide | tee ./drill-evidence/31-pods-during.txt
kubectl -n techx-tf3 get endpoints | tee ./drill-evidence/32-endpoints-during.txt
```

---

## 7. Tiêu chí ABORT — dừng ngay, không hỏi thêm

| Dấu hiệu | Hành động |
|---|---|
| `10-external-probe.log` xuất hiện **5xx liên tiếp > 30s** | `stop-experiment` |
| checkout success < 99% kéo dài > 1 phút | `stop-experiment` |
| Alarm `tf3-fis-stop-storefront-5xx` chuyển `ALARM` | FIS tự dừng — xác nhận đã rollback |
| Bất kỳ datastore nào (RDS/MSK/ElastiCache) báo lỗi failover | `stop-experiment` + báo leader |
| Mất kết nối `kubectl` (không quan sát được) | `stop-experiment` — không chạy mù |

---

## 8. Sau khi kết thúc (T+5 → T+20)

```bash
# 8.1 Experiment đã completed/stopped chưa
aws fis get-experiment --id $EXP --region ap-southeast-1 | tee ./drill-evidence/40-experiment-final.json

# 8.2 Hồi phục: node/pod trở lại
kubectl get nodes -o wide | tee ./drill-evidence/41-nodes-after.txt
kubectl -n techx-tf3 get pods -o wide | tee ./drill-evidence/42-pods-after.txt

# 8.3 Không còn pod lỗi
kubectl -n techx-tf3 get pods --no-headers | awk '$3!="Running" && $3!="Completed"' | tee ./drill-evidence/43-abnormal-after.txt

# 8.4 Storefront
curl -s -o /dev/null -w "after / -> %{http_code}\n" https://d2tn71186d7ilz.cloudfront.net/ | tee $SP/44-storefront-after.txt

# 8.5 Network ACL đã được FIS trả lại nguyên trạng chưa (quan trọng!)
aws ec2 describe-network-acls --region ap-southeast-1 \
  --filters Name=association.subnet-id,Values=<subnet-1b-id> \
  --query 'NetworkAcls[].{Id:NetworkAclId,Default:IsDefault}' --output table | tee ./drill-evidence/45-nacl-after.txt
```

**Chốt hồi phục:** mọi pod `Running`, storefront `200`, network ACL trở lại bản gốc (FIS tự rollback — nhưng **phải xác nhận bằng mắt**, không tin mặc định).

---

## 9. Bảng evidence cần thu

| Mã | Nội dung | Nguồn | Bắt buộc |
|---|---|---|---|
| EV-01 | Bản đồ node → AZ trước/sau | `00-nodes-before.txt`, `41-nodes-after.txt` | ✅ |
| EV-02 | Phân bố luồng ra tiền theo AZ (chứng minh ≥1 replica ngoài 1b) | `02-revenue-placement-before.txt` | ✅ |
| EV-03 | **Log probe ngoài suốt bài** — không có 5xx | `10-external-probe.log` | ✅ **quan trọng nhất** |
| EV-04 | JSON experiment (thời điểm, trạng thái, stop condition) | `20-…json`, `40-…json` | ✅ |
| EV-05 | Video/ảnh Grafana: request rate + success rate + p95 xuyên suốt | quay màn hình | ✅ |
| EV-06 | Pod/endpoint trong lúc fault (thấy 1b rụng) | `31-…`, `32-…` | ✅ |
| EV-07 | CloudWatch ALB 5xx quanh cửa sổ bắn | Console CloudWatch | ✅ |
| EV-08 | Xác nhận hồi phục + NACL trả nguyên trạng | `43-…`, `45-…` | ✅ |

---

## 10. Khung report nghiệm thu

> Lưu tại `docs/evidence/mandate-17/mandate-17-az-drill-<ngày>.md`

```markdown
# Mandate 17 req#2 — Biên bản diễn tập mất AZ bằng AWS FIS

**Ngày / giờ (UTC):**            **Người chủ trì:** CDO-02
**AZ mục tiêu:** ap-southeast-1b **Thời lượng:** PT5M
**Experiment ID:**               **Template ID:**
**Stop condition:** tf3-fis-stop-storefront-5xx (trạng thái cuối: …)

## 1. Kết luận điều hành
(1 đoạn: giữ được SLO hay không, số liệu chốt)

## 2. Vì sao dùng FIS thay vì cordon/drain
Directive #17 đòi "chết bất ngờ"; cordon/drain là bảo trì có kế hoạch (Directive #3).
FIS `aws:network:disrupt-connectivity` cắt traffic vào/ra AZ đúng như sự cố thật.

## 3. Chuẩn bị
- Phân bố trước drill (bảng service → AZ)
- Đã dời Prometheus khỏi 1b (nếu có), lý do
- Mức tải áp dụng

## 4. Diễn biến theo mốc thời gian
| Giờ UTC | Sự kiện | Quan sát |
|---|---|---|
| T-0 | start-experiment | |
| T+1m | | |
| T+5m | fault tự hết | |
| T+15m | xác nhận hồi phục | |

## 5. Kết quả so với SLO
| Chỉ tiêu | Ngưỡng | Đo được | Đạt? |
|---|---|---|---|
| checkout success | ≥ 99% | | |
| browse/cart success | ≥ 99.5% | | |
| storefront p95 | < 1s | | |
| Request rớt (probe ngoài) | 0 | | |

## 6. Bằng chứng đính kèm
(EV-01 … EV-08)

## 7. Hạn chế đã biết — nói thẳng
- **Chỉ diễn tập trên 1b, chưa diễn tập 1a.** Toàn bộ VPC hiện dùng **một NAT Gateway
  đặt ở 1a**, và cả ba private subnet chung một route table trỏ vào nó. Mất 1a thật sẽ
  đứt egress toàn cluster: tunnel cloudflared rớt (khách mất storefront) và không pull
  được ECR (pod không khởi động được ở bất kỳ AZ nào). Ngoài ra ba VPC endpoint SSM
  cũng chỉ nằm ở 1a. Đây là phát hiện của bản rà soát hệ thống 29/07, **đã ghi nhận
  và đề xuất xử lý riêng**, không giấu.
- **REL-17-05:** luồng ra tiền vẫn tập trung trên số ít node spot; mất 1 AZ thì sống
  nhưng replica còn lại dồn về một node.

## 8. Việc phát sinh sau drill
| # | Việc | Chủ | Hạn |
```

---

## 11. Nếu drill FAIL

Không sửa vội. Ghi lại **chính xác cái gì gãy và vào lúc nào**, rồi:
1. Xác nhận đã rollback sạch (§8).
2. Phân loại: lỗi **thiết kế** (thiếu replica/AZ) hay lỗi **cấu hình** (probe, PDB, DNS)?
3. Mở finding có mã (`REL-17-xx`), sửa, **diễn tập lại** — mentor đánh giá cao chuỗi *phát hiện → sửa → diễn tập lại* hơn là một lần chạy đẹp.
