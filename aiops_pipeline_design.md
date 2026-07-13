# TF3-AIOps-Engine: Closed-loop Multi-layer Diagnostics & Remediation (CMDR)

Bản thiết kế thuật toán và kiến trúc đường ống xử lý (Pipeline) nâng cao dành riêng cho nhóm **AIO02 / TF3**, kết nối chặt chẽ giữa mã nguồn dịch vụ với các cam kết hạ tầng trong bộ hợp đồng **C1 đến C6**.

---

## 🏗️ Tổng quan Pipeline CMDR (5 Giai đoạn)

CMDR Pipeline kết nối dữ liệu giám sát (Telemetry) để tự động hóa phát hiện, chẩn đoán (RCA) và đưa ra hành động khắc phục có kiểm soát thông qua 5 giai đoạn:

```
                  [ GIAI ĐOẠN 1: DUAL-LAYER DETECTION (C2) ]
                   (Dự phòng Alertmanager chạy song song)
                                      │
                                      ▼ (Alert Fired)
               [ GIAI ĐOẠN 2: GRAPH-BASED RCA LOCALIZATION (C3) ]
                                      │
                                      ▼ (Xác định Culprit Service + Change Log)
                 [ GIAI ĐOẠN 3: EVIDENCE PACK GENERATOR (C3) ]
                                      │
                                      ▼ (Logs + Traces Packaged)
                  [ GIAI ĐOẠN 4: LLM DIAGNOSTIC ENGINE (C4, C5) ]
                                      │
                                      ▼ (Validation Gate: Grounded & Whitelist Check)
               [ GIAI ĐOẠN 5: HUMAN-IN-THE-LOOP REMEDIATION (C6) ]
```

---

## 🛠️ Thuật toán chi tiết từng Giai đoạn

### 📊 GIAI ĐOẠN 1: DUAL-LAYER DETECTION (Cảnh báo 2 lớp)
CMDR sử dụng hai thuật toán chạy song song để tối ưu hóa độ chính xác và chống "nhiễu cảnh báo" (Alert Fatigue):

#### **Lớp 1: Deterministic SLO Burn-rate Monitor (Google SRE Standard)**
* **Mục đích**: Phát hiện sự cố nghiêm trọng ảnh hưởng trực tiếp tới khách hàng (đốt cháy ngân sách lỗi - Error Budget).
* **Giải thuật**: Theo dõi đồng thời 2 cửa sổ thời gian (Multi-window Multi-burn-rate):
  - **Short Window ($5m$)**: Phản ứng nhanh với các lỗi đột biến.
  - **Long Window ($1h$ hoặc $6h$)**: Đảm bảo lỗi kéo dài và thực sự đe dọa SLO.
* **Công thức kích hoạt Alert**:
  $$\text{Alert Fired} \iff \left(\text{Burn Rate}_{5m} \ge K\right) \land \left(\text{Burn Rate}_{1h} \ge K\right)$$
  *(Với $K = 14.4$ cho sự cố Critical, tương đương đốt $2\%$ Error Budget trong 1 giờ).*

#### **Lớp 2: ML-based Saturation & Lag Monitor**
* **Mục đích**: Phát hiện sớm các tín hiệu cảnh báo trước khi SLO bị vỡ (ví dụ: Kafka consumer lag tăng, nghẽn CPU/Memory).
* **Giải thuật**: Tính toán ngưỡng động (Dynamic Threshold) sử dụng công thức Z-Score sửa đổi trên cửa sổ trượt 7 ngày (rolling 7-day baseline):
  $$Z = \frac{x_t - \mu_{7d}}{\sigma_{7d}}$$
  *(Kích hoạt cảnh báo mức `warning` khi $|Z| > 3.0$ liên tục trong 5 chu kỳ quét).*

#### **🚨 Lớp Dự Phòng Độc Lập (Alertmanager Redundancy - C2 §Failure modes)**
Để đảm bảo cam kết dữ liệu ngay cả khi AI Engine chính bị sập (Crash/OOM):
- **Cấu hình**: Alert rules và recording rules PromQL cơ bản chạy trực tiếp trên Prometheus Server do CDO host.
- **Hành vi**: Khi AI Engine chính chết, Prometheus/Alertmanager tự động gửi các cảnh báo SLO thô (mất tính năng chẩn đoán thông minh và RCA).
- **Cảnh báo meta**: Tự động phát sinh alert `ai_engine_blind` (Severity: warning) thông báo cho người trực biết bộ não AIOps đang ngừng hoạt động.

---

### 🕸️ GIAI ĐOẠN 2: GRAPH-BASED RCA LOCALIZATION (Định vị Nút lỗi)
Khi Giai đoạn 1 kích hoạt cảnh báo tại thời điểm $t$, Engine sẽ chuyển sang định vị nguyên nhân gốc bằng cách duyệt đồ thị dependency:

```python
def locate_culprit_node(trace_data):
    # 1. Reconstruct DAG (Directed Acyclic Graph) from Jaeger Spans
    dag = build_dependency_graph(trace_data)
    
    # 2. Traverse from Root (frontend) to Leaf nodes
    error_nodes = []
    for node in dag.nodes:
        if node.status == "ERROR" or node.latency > node.p95_baseline * 3:
            error_nodes.append(node)
            
    # 3. Find the lowest node in the graph (deepest dependency)
    # Culprit is the leaf-most error node
    culprit = find_deepest_node(error_nodes)
    return culprit
```

* **Kết hợp Change Log (C3 §33)**: Kiểm tra chéo thời điểm $t$ với kênh `#tf3-changes`. Nếu phát hiện có `[change]` trước sự cố $\le 10$ phút (ví dụ: `helm upgrade`), gắn thẻ sự kiện thay đổi này làm nghi phạm số 1.

---

### 📄 GIAI ĐOẠN 3: EVIDENCE PACK GENERATOR (Đóng gói Bằng chứng)
Engine tự động đóng gói hồ sơ sự cố (`evidence-pack.md`) trong vòng 30 phút mà không cần con người can thiệp:

1. **Metrics Snapshots**: Chụp ảnh biểu đồ Prometheus quanh mốc $t \pm 30m$ làm bằng chứng.
2. **Exemplar Traces**: Trích xuất 3 Trace ID lỗi nặng nhất và 1 Trace ID thành công tiêu biểu từ Jaeger để làm đối chứng.
3. **Log Miner & Clustering**: Thực hiện query OpenSearch tìm các log lỗi có nhãn `ERROR` hoặc `CRITICAL` của culprit service tại khoảng thời gian $[t - 30s, t + 30s]$.
   - *Thuật toán Log Clustering (Tuần 1)*: Sử dụng thư viện **Drain3** (Python) để phân tích cấu trúc log thời gian thực và gom nhóm các dòng log thô có chung template (constant và variable parts). Ví dụ: gộp 1000 dòng log `Connection refused to host: 10.0.x.x` giống nhau thành 1 template `Connection refused to host: <IP>` kèm theo counter count, giúp tối ưu kích thước prompt gửi LLM và tránh bão log.

---

### 🧠 GIAI ĐOẠN 4: LLM DIAGNOSTIC ENGINE (AWS Bedrock Gateway)
Engine chuyển đổi Evidence Pack thô thành ngôn ngữ tự nhiên sử dụng AWS Bedrock.

#### **Tích Hợp Tri Thức Lịch Sử (Retrieval-Augmented Diagnostics - RAD)**
Để LLM không đưa ra các chẩn đoán mơ hồ, Engine tự động nạp file [INCIDENT_HISTORY.md](file:///d:/Xbrain/Read_Capstone03/phase3/onboarding/INCIDENT_HISTORY.md) và các file Postmortem quá khứ trong thư mục `TF3/incidents/*/postmortem.md` vào ngữ cảnh (In-Context Learning).

* **Thuật toán đối chiếu (Matching Algorithm)**:
  - **Tuần 1 (Quyết định chọn)**: Sử dụng **Keyword Matching** đơn giản dựa trên bộ từ khóa định nghĩa sẵn (`INCIDENT_PATTERNS`) để đảm bảo deterministic, zero-dependency và phản hồi nhanh:
    ```python
    INCIDENT_PATTERNS = {
        "INC-1": ["connection pool", "pool exhausted", "timeout waiting", "too many clients"],
        "INC-2": ["pod restart", "rescheduled", "state lost", "cart empty", "single-replica"],
        "INC-3": ["readiness", "not ready", "deploy", "rollout", "readiness probe"]
    }
    ```
  - **Tuần 2-3 (Lộ trình phát triển)**: Nâng cấp lên **Vector Similarity (Embeddings)** nếu dữ liệu Postmortem phình to.

* **Sửa đổi Logic Mapping đối chiếu mẫu sự cố lịch sử**:
  - **INC-1 (Nghẽn DB)**: Lỗi cạn connection pool $\rightarrow$ Đề xuất tăng connection pool và timeouts.
  - **INC-2 (Mất State do Pod Rescheduled)**: **Lưu ý đặc biệt**: Đây là lỗi mất dữ liệu do Pod không có persistence và chạy Single-replica, **KHÔNG PHẢI LỖI OOM**. Tránh đề xuất tự động restart bừa bãi vì việc restart chính là nguyên nhân gây mất dữ liệu. Đề xuất: Cảnh báo điểm chết đơn lẻ (SPOF) cho SRE và đề xuất CDO cấu hình replica/persistence.
  - **INC-3 (Lỗi Deploy chập chờn)**: Lỗi thiếu readiness probe khi rollout. Do hành động `rollout-undo` (Rollback) có blast radius lớn và chưa nằm trong whitelist v1 của **C6**, Engine chỉ được phép đưa ra gợi ý `rollout-undo` dưới dạng **văn bản khuyến nghị** để người trực tự chạy tay, **tuyệt đối không cho phép tự động thực thi hoặc Approve qua nút bấm tự động ở Tuần 1**.

* **Prompt cấu trúc nâng cao (C4, C5)**:
  ```
  [HISTORICAL REFERENCE]
  Dưới đây là lịch sử các sự cố đã từng xảy ra và cách xử lý thành công:
  <Nội dung file INCIDENT_HISTORY.md>

  [CURRENT INCIDENT CONTEXT]
  Metric Anomaly: Checkout Success Rate dropped to 94.1%
  Trace Culprit Node: valkey-cart (Latency: 2.1s)
  Raw Log: "OOM command not allowed when used memory > 'maxmemory'"
  Recent Change: CDO02 scaled down valkey-cart Memory Limit to 20Mi at 09:35.

  [TASK]
  1. Phân tích nguyên nhân gốc (RCA). Đối chiếu với các sự cố lịch sử (INC-1, INC-2, INC-3) dựa trên bộ từ khóa INCIDENT_PATTERNS xem có trùng khớp hành vi không.
  2. Đề xuất hành động khắc phục từ whitelist của C6 (scale/restart/toggle flag/flush cache).
  3. Tính toán ước tính chi phí token LLM đã tiêu thụ (theo C5).
  ```

* **Kết quả**: LLM sẽ nhận diện chính xác: *"Sự cố hiện tại là lỗi OOM do memory limit vượt ngưỡng, khác với lỗi mất state do rescheduled của INC-2. Khuyến nghị chạy action scale memory hoặc restart có kiểm soát."*

#### **💰 Quản lý Chi phí Token (C5 Cost Integration)**
Mỗi lần Giai đoạn 4 kích hoạt chẩn đoán, tổng kích thước Prompt (bao gồm metrics, logs, traces và historical reference) ước tính đạt **3000 - 5000 tokens** (~$0.012/incident đối với Claude Haiku). Lượng chi phí này bắt buộc phải được ghi nhận vào báo cáo tuần của **C5** với nhãn `feature: rca-assistant` để CDO Cost pillar nắm bắt và quản lý.

#### **🛡️ Validation Gate (Chống Hallucination & Bypass - C4 §69)**
Trước khi đẩy đề xuất (RCA + Action) sang Giai đoạn 5 để hiển thị lên Slack/Discord, Engine thực hiện 2 lớp kiểm duyệt tự động:
1. **RCA Grounded Validation**: Kiểm tra xem phần giải nghĩa của LLM có bịa đặt ra các service/component không hề xuất hiện trong Evidence Pack hay không (ví dụ: cấm mention đến `payment` nếu trace/log không hề có `payment`).
2. **Action Whitelist Enforcement**: Đề xuất action của LLM bắt buộc phải khớp 100% với danh mục whitelist trong **C6** (scale/restart/toggle-tf-flag/cache-flush/breaker-force). Nếu LLM đề xuất lệnh lạ (ví dụ: `rm -rf`, hoặc đổi config `flagd` của BTC), Validation Gate sẽ lập tức chặn lại và tự động chuyển về chế độ gợi ý bán tự động.

---

### 🛡️ GIAI ĐOẠN 5: POLICY / SAFETY ENGINE & REMEDIATION (Khắc phục an toàn)
Quy trình thực thi hành động khắc phục tuân thủ nghiêm ngặt **Cơ chế đánh giá rủi ro (Risk Assessment)** và các quy tắc bất biến của **C6**:

```
                        [ AI Engine đề xuất Action ]
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │  POLICY & SAFETY ENGINE          │
                    │  1. Dry-run kiểm tra cú pháp    │
                    │  2. Ước tính Blast Radius        │
                    │  3. Phân loại Risk Level         │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
               [LOW RISK]  [MEDIUM RISK]  [HIGH RISK]
            (Tự động chạy) (Chờ Approve) (Tự động từ chối)
                    │            │            │
                    ▼            ▼            ▼
             [Thực thi     [Gửi Button    [Chặn &
              ngay lập tức] Card Slack]   Log từ chối]
                    │            │
                    │     ┌──────┴──────┐
                    │  [Reject]      [Approve]
                    │     │          (Con người bấm)
                    │     ▼               │
                    │  [Hủy & Log]        │
                    │                    │
                    └────────┬───────────┘
                             │
                             ▼
                  [ Kiểm tra Rate-Limit Invariant ]
                  (Tối đa 3 actions / incident / giờ)
                             │
                ┌────────────┴────────────────┐
          (Hợp lệ) ▼                          ▼ (Quá rate limit)
      [ 1. Đọc Rollback Plan ]          [ Tự khóa & Alert ]
                 │
                 ▼
      [ 2. Thực thi lệnh K8s API ]
        (Bắt đầu Timer: Max 5 phút)
                 │
                 ▼
      [ 3. Quét Telemetry 5 phút ]
        ┌────────┴──────────┐
(Fail / │                   │ (Success &
Timeout)▼                   ▼  No Timeout)
  [ Chạy Rollback ]    [ Hoàn thành & Log ]
        │
        ▼
 [ Rollback thành công? ]
   ┌────┴────┐
   ▼ (Yes)  ▼ (No — Rollback thất bại)
 [Log &   [ 🚨 ESCALATE: Gửi alert khẩn ]
  Đóng]   [ cấp tới kỹ sư on-call qua   ]
          [ PagerDuty / kênh TF3 với     ]
          [ đầy đủ: incident_id, action, ]
          [ rollback_plan, trạng thái.   ]
          [ Chuyển sang Manual Mode.     ]
```

#### **🔍 Bộ lọc an toàn — Policy & Safety Engine**

Trước khi phân loại rủi ro, mọi action phải qua 2 bước kiểm tra:

1. **Dry-run (Kiểm tra cú pháp)**: Gọi K8s API ở chế độ `--dry-run=server` để xác minh lệnh hợp lệ về mặt cú pháp và authorization, không thực thi thật.
2. **Blast Radius Estimation (Ước tính vùng ảnh hưởng)**: Tính toán xem action tác động tới bao nhiêu service phụ thuộc và bao nhiêu % traffic hiện tại, dựa trên đồ thị dependency từ Giai đoạn 2.

#### **⚖️ Phân loại rủi ro 3 mức (Risk Assessment)**

| Mức | Điều kiện | Hành vi Engine | Ví dụ |
|---|---|---|---|
| 🟢 **LOW** | Action trong whitelist C6 + Blast Radius < 10% traffic + không phải `restart`/`scale` | **Tự động chạy ngay** — không cần approval của con người | `cache-flush`, `breaker-force` |
| 🟡 **MEDIUM** | Action trong whitelist C6 + Blast Radius 10–50% hoặc là `restart`/`scale` | **Gửi button card Slack** chờ người trực approve | `scale deployment`, `restart pod` |
| 🔴 **HIGH** | Action ngoài whitelist C6, hoặc động đến `flagd` BTC, hoặc Blast Radius > 50% | **Tự động từ chối** — ghi log và thông báo | Bất kỳ lệnh lạ, sửa config flagd |

> **Lưu ý**: Quyết định mức LOW (tự động chạy không cần approval) chỉ áp dụng cho `cache-flush` và `breaker-force`. Mọi action có thể thay đổi trạng thái pod/replica đều tối thiểu là MEDIUM và phải qua approval của con người — đúng tinh thần C6 §Invariant 1.

#### **🔒 Quy tắc Bất biến C6 (Invariants)**

- **Timeout Control**: Mỗi lệnh thực thi (K8s API call) được gắn timer tối đa **5 phút**. Quá 5 phút → Tự động hủy lệnh, kích hoạt Rollback Plan và ghi log trạng thái `result: timeout` (Invariant 3).
- **Rate Limit**: Engine tự động đếm số lần chạy hành động cho mỗi incident. Nếu vượt quá **3 actions/incident/giờ** → Engine tự động khóa, ngừng gửi button card và gửi alert yêu cầu con người vào xử lý trực tiếp (Invariant 4).
- **Lưu vết Audit (C6 §50)**: Ghi tự động mọi thao tác vào file `TF3/incidents/<incident_id>/actions.jsonl` (append-only) chứa đầy đủ thông tin: định danh người duyệt, lệnh chạy, kết quả đo lường sau **5 phút**, và phương án rollback.
- **Rollback thất bại → Escalate**: Nếu Rollback Plan chạy mà vẫn thất bại (K8s API lỗi, timeout, hoặc telemetry vẫn xấu sau 5 phút) → Engine chuyển về **Manual Mode** và gửi alert khẩn cấp tới kỹ sư on-call kèm đầy đủ context: `incident_id`, lệnh đã thực thi, kết quả rollback, và link Evidence Pack. Người kỹ sư toàn quyền xử lý từ đây.

---

## 🎯 Tiêu chí nghiệm thu CMDR Pipeline (Definition of Done)

- [ ] **DoD 1: Alert Fire-drill**: Chạy thử kịch bản giả lập bắn alert đúng schema JSON theo đúng hợp đồng **C2 §DoD** vào kênh chat. Người trực CDO nhận được và hiểu được thông tin.
- [ ] **DoD 2: Evidence Pack generation**: Evidence pack tự động sinh đúng format trong vòng 30 phút theo **C3 §DoD** khi giả lập incident.
- [ ] **DoD 3: Auditability verification**: Chạy script `audit-check.sh` của CDO Audit pillar quét và trả lời `PASS` cho các hành động diễn tập (không có hành động nào chạy thiếu approval hoặc thiếu rollback plan - **C6 §DoD**).
- [ ] **DoD 4: Alert Meta `ai_engine_blind`**: Giả lập tắt AI Engine chính, Alertmanager của Prometheus tự động phát hiện và kích hoạt cảnh báo warning `ai_engine_blind` lên kênh chat.
