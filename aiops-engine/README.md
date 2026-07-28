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
