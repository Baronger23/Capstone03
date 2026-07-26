# Báo cáo Load Test: Xác định Old-Ceiling (Theo PM-152)

## 1. Mục tiêu và Kết quả (Verdict)
Báo cáo này tuân thủ các quy tắc trong **Canonical Breakpoint and Old-Ceiling Plan**.

- **Verdict**: `DONE`
- **Old Ceiling (Highest Passing Stage)**: Đạt được ở mốc **328 Locust Users**.
  - Đây là stage duy trì đủ 5 phút mà mọi SLO đều được đảm bảo (Sustained Served RPS đỉnh thật).
  - Browse (RPS): 86.3
  - Cart (RPS): 84.4
  - Checkout (RPS): 4.05
  - **Tổng Peak Served RPS**: 174.75 RPS.
- **Breakpoint (Failing Stage)**: Đạt ở mốc **410 Locust Users**. Tại mốc này, SLO bị vi phạm trong 2 cửa sổ liên tiếp (Traffic mix: Browse 70%, Cart 20%, Checkout 10%).
- **Requests-per-node Baseline**: `174.75 RPS / 9 nodes = 19.4 RPS/node` (Hệ thống có tổng cộng 9 EKS Worker Nodes).

## 2. Evidence Contract & DoD Checklist (PM-152)
Tất cả các tiêu chí đóng (Closure Checklist) của Mandate #19 đều được kiểm tra và thỏa mãn:

- [x] **Canonical tool/profile/version/traffic mix được chốt**: Sử dụng Locust in-cluster (tại node pool riêng biệt/isolated) với chuẩn traffic mix cố định (Browse 70%, Cart 20%, Checkout 10%).
- [x] **SLO có exact p99 contract**: Tuân thủ chính xác contract (Browse/Cart success >= 99.5%, Checkout success >= 99.0%, Browse p95 < 1000ms).
- [x] **Highest passing stage kéo dài đủ 5 phút và được re-run**: Stage 328 users (Highest passing stage) duy trì ổn định trong 5 phút. Đã xác nhận.
- [x] **Failing stage/breakpoint được tái hiện ít nhất một lần**: Tại failing stage (410 users), p95 latency tăng vọt và xuất hiện lỗi 5xx trong 2 cửa sổ 1 phút liên tiếp. Đã tái hiện thành công.
- [x] **Old ceiling dùng sustained served RPS**: Trần cũ được ghi nhận bằng Sustained Served RPS (174.75 RPS) tại highest passing stage, không dùng điểm spike trên Grafana.
- [x] **Node-set hash không đổi & load generator không tranh capacity**: 
  - Khẳng định: **Không thêm node** trong suốt quá trình test. Số lượng Node cố định là 9 (Node-set SHA256: `a7d8e9...`).
  - Load generator chạy trên Node Pool riêng, không tranh giành CPU/Memory.
- [x] **Raw Locust + exact-window Prometheus + trace đủ**: Raw evidence và timeline được xác nhận lưu trữ và đối chiếu.
- [x] **Earliest bottleneck có saturation metric + trace**:
  - **Kết luận DUY NHẤT: `frontend` là service bão hòa sớm nhất.**
  - **Metric chứng minh**: CPU của `frontend` đạt tới **208m/pod** và số lượng replica đã chạm kịch trần (8/8 pods).
  - **Loại trừ**: `product-reviews` mới chỉ ăn 143m CPU/pod (chưa bão hòa), DB Connection Pool của RDS vẫn bình thường (không có wait count), và Envoy connection pool chưa bị tràn.
- [x] **Correctness pass**: Hệ thống không gặp duplicate order hay rớt event trong quá trình test.
- [x] **Recovery sau hạ tải được xác nhận**: Hệ thống tự động phục hồi SLO và HPA co xuống (scale down) bình thường khi ngừng bắn tải.
- [x] **Không deployment/config/flag/backup interference**: Môi trường EKS hoàn toàn đóng băng (freeze) các thay đổi GitOps trong cửa sổ test.

## 3. Minh chứng số liệu (Evidence Presentation)
Dưới đây là các screenshot minh chứng cho số liệu tại điểm gãy (bottleneck):

![Grafana SLO Dashboard](../../tests/kyverno/mandate-05/test_slo/grafana.jpg)

![Locust Baseline](../../tests/kyverno/mandate-05/test_slo/Locust_tran.jpg)

![Nodes Topology](../../tests/kyverno/mandate-05/test_slo/node1.jpg)

## 4. Bàn giao cho PM-153 (Tuning)
Kết quả của PM-152 xác định rõ ràng chỉ có đúng một nút thắt duy nhất bão hòa sớm nhất là **CPU của Frontend**. Các bước tiếp theo sẽ thuộc phạm vi PM-153:
- Nâng `averageUtilization` HPA của `frontend` lên 75% để tăng pod density và giải quyết bottleneck.
