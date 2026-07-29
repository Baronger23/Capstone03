# Kéo source aiops-engine về repo hạ tầng Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đưa source `aiops-engine` từ repo AIO02 về repo này, dựng CI build có Trivy + Cosign như `shopping-copilot`, để image chạy production đi qua supply-chain gate PM-101.

**Architecture:** Copy sạch source vào `aiops-engine/` ở gốc repo (đúng khuôn `shopping-copilot/`), loại bỏ model binary và rác runtime. Thêm `.github/workflows/build-push-aiops.yml` sao khuôn `build-push-copilot.yml`. Việc repoint manifest sang digest mới **tách thành task riêng có cổng chặn**, vì source ở HEAD mới hơn image đang chạy.

**Tech Stack:** Python 3.10 (FastAPI + scikit-learn), Docker buildx, Trivy, Cosign keyless, GitHub Actions OIDC, ECR `tf-2-ai-engine`.

## Global Constraints

- Account `197826770971`, region `ap-southeast-1`, ECR registry `197826770971.dkr.ecr.ap-southeast-1.amazonaws.com`, repo ảnh `tf-2-ai-engine`.
- AWS profile `default` — **không** `export AWS_PROFILE=techx-new`.
- kubectl qua SSM tunnel: `scripts/kube-tunnel.sh`. Tunnel tự đóng sau ~10–20 phút idle.
- **Không push thẳng `main`.** Branch từ `origin/main` sau `git fetch`, merge qua PR.
- **Không** commit secret thật vào file tracked. Repo có `secret-scan.yml` (gitleaks) chạy trên PR.
- **Không** đụng `flagd` / `values-flagd-sync.yaml` / filter `envoy.filters.http.fault` — disqualify.
- **Không** sửa hay đọc `CLAUDE.md` (quy tắc `CLAUDE.local.md`).
- Commit message **không** kèm `Co-Authored-By` hay chữ ký nền tảng (`.claude/rules/git.md`).
- Subagent **chỉ** chạy kubectl read-only (`get`, `diff`). Mọi mutation cluster và merge PR do controller làm sau khi user duyệt.
- Nguồn source: <https://github.com/DangThao195/AIO02_TF3_Phase3>, commit `d68dd9759491dc03e9a3d83c27393f52851dc8c9` (2026-07-27 20:32:09 +0700). Ghi commit này vào PR để truy vết.
- Spec nền: `docs/superpowers/specs/2026-07-28-aiops-engine-gitops-adoption-design.md`.

---

## Bối cảnh đã kiểm chứng (28/07/2026)

**Vì sao làm việc này:** `grep -rn 'tf-2-ai-engine' .github/workflows/` cho **0 kết quả**. Image chạy production được AIO02 build tay và push thẳng ECR, không qua Trivy release gate hay Cosign signing của PM-101 — khác hẳn `shopping-copilot` (cùng là workload AIO02 nhưng source nằm trong repo này nên có đủ gate).

**Kích thước và rác:**

| Thành phần | Dung lượng | Xử lý |
|---|---|---|
| `models/` (7 file `.joblib`) | 14MB | **Loại.** `.dockerignore` của chính họ đã loại `models/*.joblib` khỏi image; kho model thật là S3 `tf3-aiops-models-197826770971/current/` (kích thước khớp từng byte). |
| `scratch/` (8 script debug) | 384KB | **Loại.** Cũng đã bị `.dockerignore` loại. |
| `audit_log.jsonl` | 22 dòng | **Loại.** State runtime, không phải source. |
| Phần còn lại | ~2.5MB / ~120 file | **Giữ**, gồm test suite 10+ file. |

**Quét secret:** `grep -rInE 'AKIA[0-9A-Z]{16}|xoxb-|hooks\.slack\.com/services/|sk-[A-Za-z0-9]{20,}|BEGIN .*PRIVATE KEY'` trên `AIOps/aiops-engine/` cho **0 kết quả**. Không có file `.env`/`.pem`/credential.

**⚠️ Source ở HEAD mới hơn image đang chạy.** Commit cuối chạm `AIOps/aiops-engine` là `d68dd97` lúc `2026-07-27 20:32:09 +07`; `IF-v63` (đang chạy) push lúc `2026-07-27 15:38:03 +07` — **sớm hơn ~5 tiếng**. Build từ source này ra image **chưa từng chạy production**. Đây là lý do Task 4 (repoint manifest) tách riêng và có cổng chặn.

**Hai vấn đề trong `Dockerfile` của AIO02** — ghi nhận, không sửa trong plan này (code của họ):
- Không có chỉ thị `USER`. Image mặc định chạy root; chỉ nhờ `securityContext.runAsUser: 10001` của pod mới thành non-root. Nếu ai đó chạy ảnh này ngoài cụm, nó là root.
- `curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"` — kéo kubectl **latest** mỗi lần build. Build không tái lập được, và một thay đổi phía upstream lọt thẳng vào ảnh production.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `aiops-engine/` | Source Python + tests + `Dockerfile` + `requirements.txt` (copy sạch, đã lọc) |
| `aiops-engine/.trivyignore` | Danh sách false positive có tài liệu, cho Trivy gate |
| `aiops-engine/README.md` | Ghi rõ nguồn gốc, commit gốc, và những gì đã bị loại |
| `.github/workflows/build-push-aiops.yml` | Build + Trivy gate + push digest + Cosign |
| `gitops/aiops-engine/deployment.yaml` | Repoint sang digest mới (Task 4, có cổng chặn) |
| `gitops/aiops-engine/cronjob.yaml` | Như trên |

---

## Task 1: Import source, đã lọc

**Files:**
- Create: `aiops-engine/**` (copy từ repo AIO02, trừ phần loại bỏ)
- Create: `aiops-engine/README.md`

**Interfaces:**
- Produces: `aiops-engine/Dockerfile` + `aiops-engine/requirements.txt` — Task 2 build từ đây

- [ ] **Step 1: Clone repo nguồn ở đúng commit**

```bash
cd /tmp/claude-1000/-home-tutruong-project-Phase3-TF3-Infra-Sentinel/d9c52943-7bf9-4660-bcd2-1aac31c0cdbd/scratchpad
rm -rf aiops-src
git clone https://github.com/DangThao195/AIO02_TF3_Phase3 aiops-src
cd aiops-src
git checkout d68dd9759491dc03e9a3d83c27393f52851dc8c9
git log -1 --format='%H %ad' --date=iso
```

Expected: in ra đúng `d68dd975...` và `2026-07-27 20:32:09 +0700`.

- [ ] **Step 2: Copy sang repo, loại 3 thứ**

```bash
SRC=/tmp/claude-1000/-home-tutruong-project-Phase3-TF3-Infra-Sentinel/d9c52943-7bf9-4660-bcd2-1aac31c0cdbd/scratchpad/aiops-src/AIOps/aiops-engine
DST=aiops-engine
mkdir -p "$DST"
rsync -a --exclude 'models/' --exclude 'scratch/' --exclude 'audit_log.jsonl' \
      --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude '*.pyc' \
      "$SRC"/ "$DST"/
```

- [ ] **Step 3: Xác nhận đã loại đúng, không sót gì nặng**

```bash
du -sh aiops-engine
find aiops-engine -type f -size +1M -printf '%s %p\n' | sort -rn
ls aiops-engine/models aiops-engine/scratch aiops-engine/audit_log.jsonl 2>&1
```

Expected: tổng ~2.5MB; **không file nào > 1MB**; ba lệnh `ls` cuối đều báo `No such file or directory`.

Nếu còn file > 1MB, dừng lại xem đó là gì trước khi commit — repo hạ tầng không nên chứa binary lớn.

- [ ] **Step 4: Quét secret trước khi commit**

```bash
grep -rInE 'AKIA[0-9A-Z]{16}|xoxb-[0-9A-Za-z-]+|hooks\.slack\.com/services/[A-Za-z0-9/]+|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY' aiops-engine | grep -v Binary
echo "EXIT=$?"
find aiops-engine -iname '*.env*' -o -iname '*.pem' -o -iname '*credential*'
```

Expected: grep không in dòng nào (`EXIT=1` là đúng — grep không tìm thấy gì); `find` không ra file nào.

**Nếu grep in ra bất cứ thứ gì: DỪNG, báo BLOCKED.** Không commit. Repo này có CI gitleaks và luật cấm tuyệt đối về secret.

- [ ] **Step 5: Viết `aiops-engine/README.md`**

```markdown
# aiops-engine

AIOps engine của AIO02: phát hiện bất thường (Isolation Forest), phân tích nguyên nhân
qua Bedrock, và khắc phục có người duyệt qua Slack.

## Nguồn gốc

Source được kéo về từ <https://github.com/DangThao195/AIO02_TF3_Phase3>, thư mục
`AIOps/aiops-engine/`, tại commit `d68dd9759491dc03e9a3d83c27393f52851dc8c9`
(2026-07-27 20:32:09 +0700).

Từ nay repo này là nguồn sự thật: image production build bằng
`.github/workflows/build-push-aiops.yml` (Trivy gate + Cosign keyless), và manifest deploy
nằm ở `gitops/aiops-engine/` do ArgoCD quản.

Lý do chuyển: trước đây ảnh `tf-2-ai-engine` được build tay và push thẳng ECR, không đi qua
supply-chain gate PM-101 — khác với mọi workload khác trên cụm.

## Những gì KHÔNG được kéo về

| Bỏ | Vì sao |
|---|---|
| `models/` (7 file `.joblib`, 14MB) | Kho model thật là S3 `tf3-aiops-models-197826770971/current/`. `.dockerignore` vốn đã loại chúng khỏi ảnh, nên chúng chỉ là dung lượng chết trong git và đổi mỗi lần retrain. |
| `scratch/` | Script debug chạy tay, cũng đã bị `.dockerignore` loại. |
| `audit_log.jsonl` | State runtime, không phải source. |

## Hai điểm cần AIO02 xử lý trong `Dockerfile`

- **Không có chỉ thị `USER`.** Ảnh mặc định chạy root; chỉ nhờ `securityContext.runAsUser: 10001`
  của pod mới thành non-root. Chạy ảnh này ngoài cụm là root.
- **Kéo kubectl `latest` lúc build** (`dl.k8s.io/release/stable.txt`). Build không tái lập được,
  và thay đổi phía upstream lọt thẳng vào ảnh production. Nên ghim phiên bản kubectl.

## Chạy test

```bash
cd aiops-engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install pytest pytest-asyncio
pytest tests/
```
```

- [ ] **Step 6: Commit**

```bash
git add aiops-engine/
git commit -m "feat(aiops): kéo source aiops-engine từ repo AIO02 về repo hạ tầng

Nguồn: DangThao195/AIO02_TF3_Phase3 @ d68dd97, thư mục AIOps/aiops-engine.

Loại 3 thứ: models/ (14MB joblib - kho thật là S3, .dockerignore vốn đã loại),
scratch/ (script debug), audit_log.jsonl (state runtime).

Quét secret trước khi commit: 0 kết quả, không file .env/.pem.

Chưa có CI build - image production vẫn là IF-v63 do AIO02 push tay cho tới
khi workflow ở commit sau chạy được."
```

---

## Task 2: CI build có Trivy gate + Cosign

**Files:**
- Create: `.github/workflows/build-push-aiops.yml`
- Create: `aiops-engine/.trivyignore`

**Interfaces:**
- Consumes: `aiops-engine/Dockerfile` từ Task 1
- Produces: digest ảnh đã ký, in ra `GITHUB_STEP_SUMMARY` — Task 4 ghim digest đó

**Khuôn mẫu bắt buộc:** sao `.github/workflows/build-push-copilot.yml` và đổi cho đúng aiops. **Đọc file đó trước khi viết.** Giữ nguyên mọi action SHA đã ghim trong đó (repo ghim action theo SHA có chủ đích — đừng đổi sang tag).

Khác biệt so với bản copilot:

| | copilot | aiops |
|---|---|---|
| `ECR_REPOSITORY` | `shopping-copilot` | `tf-2-ai-engine` |
| `paths:` trigger | `shopping-copilot/**` | `aiops-engine/**` |
| build context / `--file` | `shopping-copilot` | `aiops-engine` |
| `--ignorefile` | `shopping-copilot/.trivyignore` | `aiops-engine/.trivyignore` |
| tên artifact Trivy | `trivy-copilot-` | `trivy-aiops-` |
| `concurrency.group` | `build-push-copilot-` | `build-push-aiops-` |
| guard file tồn tại | `shopping-copilot/Dockerfile` | `aiops-engine/Dockerfile` |
| dòng summary | `gitops/shopping-copilot/deployment.yaml` | `gitops/aiops-engine/deployment.yaml` **và** `cronjob.yaml` |

- [ ] **Step 1: Đọc khuôn mẫu**

```bash
cat .github/workflows/build-push-copilot.yml
```

- [ ] **Step 2: Viết `.github/workflows/build-push-aiops.yml`**

Sao nguyên cấu trúc, áp bảng khác biệt trên. Giữ nguyên: guard "chỉ dispatch từ main", cách sinh tag `<sha7>-<run_id>` (ECR immutable nên rerun fail-closed thay vì ghi đè), Trivy chạy **hai lần** (một lần xuất JSON đầy đủ làm bằng chứng, một lần làm cổng chặn với `--ignore-unfixed`), push bằng buildx `--metadata-file` rồi lấy digest, Cosign `sign` + `verify` keyless.

Sửa comment đầu file cho đúng ngữ cảnh aiops (đừng để lại chữ "shopping-copilot" hay "docker-compose bake").

Comment trong bước Trivy của bản copilot nhắc `python:3.11-slim`; `Dockerfile` của aiops dùng **`python:3.10-slim`** — sửa comment cho khớp, đừng chép nguyên.

- [ ] **Step 3: Viết `aiops-engine/.trivyignore`**

Tạo file với **chỉ phần header giải thích, chưa có CVE nào**:

```
# Trivy ignore list cho ảnh aiops-engine — chỉ dùng cho false positive CÓ TÀI LIỆU.
#
# Cổng chặn trong build-push-aiops.yml đã chạy với --ignore-unfixed, nghĩa là CVE nền
# Debian chưa có bản vá thì vốn đã không chặn build. File này chỉ dành cho trường hợp
# Trivy báo một CVE CÓ bản vá nhưng nó là false positive thật (ví dụ thư viện vendored
# trong build tooling, không nằm trên đường chạy).
#
# Mỗi mục PHẢI kèm: mã CVE, đường dẫn file bị báo, và một câu vì sao nó không khai thác
# được. Không thêm mục nào chỉ để cho build xanh.
```

Lý do để trống: chưa chạy build lần nào nên chưa biết CVE thật. Thêm mục mà không có bằng chứng là tự bịt mắt mình.

- [ ] **Step 4: Kiểm cú pháp YAML**

```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/build-push-aiops.yml')); print('YAML hợp lệ')"
```

- [ ] **Step 5: Đối chiếu với khuôn mẫu, tìm chỗ chép sót**

```bash
grep -n 'copilot\|shopping\|3\.11' .github/workflows/build-push-aiops.yml
```

Expected: **không dòng nào**. Còn dòng nào là chép sót.

```bash
diff <(grep -oE 'uses: [^ ]+@[a-f0-9]{40}' .github/workflows/build-push-copilot.yml) \
     <(grep -oE 'uses: [^ ]+@[a-f0-9]{40}' .github/workflows/build-push-aiops.yml)
```

Expected: không khác biệt — mọi action phải ghim đúng SHA như bản copilot.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/build-push-aiops.yml aiops-engine/.trivyignore
git commit -m "ci(aiops): build tf-2-ai-engine qua Trivy gate + Cosign

Sao khuôn build-push-copilot.yml: Trivy chặn TRƯỚC khi push, push theo digest vào
ECR immutable, ký Cosign keyless rồi verify lại.

Đóng khoảng trống PM-101: trước đây tf-2-ai-engine là image production duy nhất
không đi qua gate nào - AIO02 build tay và push thẳng ECR.

.trivyignore để trống có chủ đích: chưa chạy build lần nào nên chưa biết CVE thật."
```

---

## Task 3: Chạy build lần đầu và đối chiếu với ảnh đang chạy

**Files:** không tạo file — đây là task kiểm chứng

**Interfaces:**
- Consumes: workflow từ Task 2
- Produces: một digest đã ký + kết luận ảnh mới có tương đương `IF-v63` không

**Đây là task của controller, không giao subagent** — nó cần dispatch workflow lên GitHub và đọc kết quả.

- [ ] **Step 1: Merge PR của Task 1 + 2 trước**

Workflow chỉ dispatch được từ `main` (có guard trong file). Cần merge trước khi chạy.

- [ ] **Step 2: Dispatch build**

```bash
gh workflow run build-push-aiops.yml --ref main
sleep 30
gh run list --workflow=build-push-aiops.yml --limit 1
```

- [ ] **Step 3: Theo dõi tới khi xong**

```bash
gh run watch "$(gh run list --workflow=build-push-aiops.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```

Nếu Trivy gate chặn: đọc report trong artifact, xác định CVE có bản vá nào. Cách xử lý đúng là **ghim phiên bản trong `requirements.txt`**, không phải thêm vào `.trivyignore`. Chỉ thêm `.trivyignore` khi chứng minh được là false positive.

- [ ] **Step 4: Lấy digest mới**

```bash
gh run view "$(gh run list --workflow=build-push-aiops.yml --limit 1 --json databaseId -q '.[0].databaseId')" --log | grep -A3 'Pin this in'
```

- [ ] **Step 5: CỔNG CHẶN — so ảnh mới với ảnh đang chạy**

Ghi lại để so:

```bash
aws ecr describe-images --repository-name tf-2-ai-engine --region ap-southeast-1 \
  --image-ids imageTag=IF-v63 --query 'imageDetails[0].{digest:imageDigest,size:imageSizeInBytes,pushed:imagePushedAt}' --output json
```

`IF-v63` hiện là `sha256:eea1d559d4314d6a840a7de2dd8b0ebb673348bf4732917023cf20f426cab66c`, 202177765 bytes.

**Ảnh mới gần như chắc chắn KHÁC** — source ở `d68dd97` (27/07 20:32) mới hơn lúc `IF-v63` được push (27/07 15:38), và `Dockerfile` kéo kubectl `latest` nên hai lần build khác thời điểm đã cho ảnh khác nhau.

Vì vậy **không tự động repoint**. Báo cáo cho user:
- digest mới
- ảnh mới có qua Trivy gate không, CVE nào bị chặn nếu có
- khẳng định rõ ràng rằng ảnh mới **chưa từng chạy production**

Rồi hỏi user có muốn sang Task 4 không.

---

## Task 4: Repoint manifest sang digest mới (CÓ CỔNG CHẶN — chỉ làm khi user duyệt)

**Files:**
- Modify: `gitops/aiops-engine/deployment.yaml`
- Modify: `gitops/aiops-engine/cronjob.yaml`

**Interfaces:**
- Consumes: digest đã ký từ Task 3

**⚠️ Task này gây restart pod và deploy code mới.** Đổi trường `image` làm đổi pod-template-hash → ReplicaSet mới → pod restart, kể cả khi ảnh giống hệt. Và ở đây ảnh **không** giống hệt: nó là code mới hơn `IF-v63`.

`aiops-engine` chạy 1 replica nên sẽ có khoảng gián đoạn ngắn. Không ảnh hưởng khách hàng (engine không nằm trên đường checkout), nhưng trong lúc đó không có ai phát hiện sự cố.

**Điều kiện bắt buộc trước khi làm:**
1. User duyệt rõ ràng.
2. AIO02 xác nhận code ở `d68dd97` sẵn sàng chạy production.
3. Làm trong giờ ít traffic.

- [ ] **Step 1: Ghi lại trạng thái trước**

```bash
kubectl get deploy aiops-engine -n techx-tf3 \
  -o jsonpath='revision={.metadata.annotations.deployment\.kubernetes\.io/revision}{"\n"}image={.spec.template.spec.containers[0].image}{"\n"}'
kubectl get pod -n techx-tf3 -l app=aiops-engine \
  -o custom-columns=NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount
```

- [ ] **Step 2: Đổi `image` trong `deployment.yaml`**

Từ `...tf-2-ai-engine:IF-v63` sang `...tf-2-ai-engine@sha256:<digest mới>`.
Đồng thời đổi `imagePullPolicy: Always` → `IfNotPresent` (digest đã bất biến, `Always` chỉ tốn băng thông).

- [ ] **Step 3: Đổi `image` trong `cronjob.yaml`**

CronJob đang ở `IF-v25`, lệch 38 bản so với engine. Đưa về **cùng digest** với deployment.

**Chỉ làm bước này nếu AIO02 đã xác nhận `train_anomaly_model_eks.py` ở bản mới còn tương thích.** Nếu chưa xác nhận, giữ nguyên `IF-v25` và ghi rõ trong PR là còn treo.

- [ ] **Step 4: Cập nhật comment trong hai file**

Cả hai file có comment nói "chưa digest-pin, sẽ làm ở Phase 3" — sửa cho khớp thực tế.

- [ ] **Step 5: Kiểm bằng diff có chọn lọc**

```bash
kubectl diff -f gitops/aiops-engine/
```

`kubectl diff` **luôn** hiện nhiễu cố định (`argocd.argoproj.io/tracking-id` như bị xoá, `generation` tăng) trên mọi tài nguyên — đó là hành vi đã biết, không phải lỗi. Chỉ chấp nhận: nhiễu đó **cộng** đúng dòng `image` và `imagePullPolicy`. Bất kỳ dòng lạ nào khác là cảnh báo thật.

Cổng tốt hơn sau khi sync: `kubectl get application aiops-engine -n argocd -o jsonpath='{range .status.resources[*]}{.kind}/{.name}: {.status}{"\n"}{end}'`

- [ ] **Step 6: Commit + PR, chờ user merge**

- [ ] **Step 7: Sau merge — xác minh**

```bash
kubectl get application aiops-engine -n argocd \
  -o jsonpath='sync={.status.sync.status} health={.status.health.status}{"\n"}'
kubectl get deploy aiops-engine -n techx-tf3 \
  -o jsonpath='revision={.metadata.annotations.deployment\.kubernetes\.io/revision}{"\n"}image={.spec.template.spec.containers[0].image}{"\n"}'
kubectl get pod -n techx-tf3 -l app=aiops-engine \
  -o custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount
kubectl logs -n techx-tf3 deploy/aiops-engine --tail=30
```

Expected: revision **tăng 1** (lần này tăng là đúng), pod mới `READY=true`, `image` có `@sha256:`, log không có traceback.

Kiểm engine còn hoạt động:

```bash
kubectl exec -n techx-tf3 deploy/aiops-engine -- \
  python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/remediation/mode').read().decode())"
```

Expected: JSON có `"mode"`.

**Nếu pod không lên hoặc log có traceback:** lui bằng cách revert commit repoint (ArgoCD sẽ tự đưa về `IF-v63`). Không sửa tay trên cluster.

---

## Tiêu chí thành công

| # | Tiêu chí | Cách verify |
|---|---|---|
| 1 | Source ở repo này, không kèm binary nặng | `du -sh aiops-engine` ~2.5MB; `find aiops-engine -size +1M` rỗng |
| 2 | Không secret nào lọt vào | grep pattern rỗng; CI `secret-scan.yml` xanh trên PR |
| 3 | CI build tồn tại và chạy được | `gh run list --workflow=build-push-aiops.yml` có run thành công |
| 4 | Ảnh qua Trivy gate | run xanh ở bước "Scan candidate with Trivy" |
| 5 | Ảnh được ký và verify được | bước Cosign `verify` xanh |
| 6 | (Task 4) Manifest ghim digest | `kubectl get deploy ... -o jsonpath='{...image}'` có `@sha256:` |
| 7 | (Task 4) Engine còn sống sau khi đổi ảnh | pod `READY=true`, `/remediation/mode` trả JSON |

## Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Ảnh build từ HEAD khác `IF-v63` → deploy code chưa kiểm chứng | Cao | Task 4 tách riêng, có cổng chặn, cần AIO02 xác nhận trước |
| Trivy gate chặn vì CVE có bản vá | Trung bình | Ghim phiên bản trong `requirements.txt`; **không** nhét vào `.trivyignore` cho xanh |
| Build không tái lập (kubectl `latest`) | Trung bình | Ghi vào README; đề nghị AIO02 ghim phiên bản kubectl |
| AIO02 vẫn push tay lên `tf-2-ai-engine` | Trung bình | ECR immutable nên không ghi đè được digest; cần thống nhất họ dừng push tay |
| CronJob ở ảnh mới không tương thích | Trung bình | Step 3 Task 4 chỉ làm khi AIO02 xác nhận; nếu chưa thì giữ `IF-v25` |
| Repo AIO02 tiếp tục sửa `AIOps/aiops-engine/` → hai nguồn sự thật | Cao | Đề nghị họ archive thư mục đó và trỏ về repo này (việc phối hợp, ngoài plan) |

## Ngoài phạm vi

- `chaos-engine` (không có manifest, không có image trong ECR, chưa deploy).
- Sửa code Python của engine — kể cả hai vấn đề `Dockerfile` đã nêu. Ghi lại để AIO02 xử lý.
- Phase 2 (IRSA + vô hiệu static admin key) và Phase 3 (NetworkPolicy, Slack qua cloudflared) của spec adoption — vẫn là plan riêng.
