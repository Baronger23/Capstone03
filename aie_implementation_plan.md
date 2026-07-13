# Kế hoạch Thực thi & Kiểm chứng AI Engineering (AIE) - Tuần 1

Bản kế hoạch chi tiết dành cho nhóm **AIO02** để triển khai, cấu hình và nghiệm thu tính năng tóm tắt review bằng AI (AIE) trong Tuần 1.

---

## 🎯 1. Mục tiêu AIE Tuần 1
- **Kết nối LLM thật**: Thay thế AI Mock bằng mô hình **OpenAI (gpt-4o-mini)** qua OpenAI API (nhất quán với ADR-001 và file values cấu hình Tuần 1. Lộ trình nâng cấp lên Bedrock Gateway lùi sang Tuần 2-3).
- **Tối ưu Latency & Cost**: Triển khai bộ nhớ đệm **In-Memory Dict Cache** với TTL 1 giờ.
- **Chống chịu lỗi (Resiliency)**: Xử lý lỗi 429 (Rate Limit) và Timeout bằng cơ chế **Retry (Backoff + Jitter)** kết hợp **Fallback hiển thị**.
- **Guardrail an toàn**: Chặn không cho lưu cache các tóm tắt sai lệch khi BTC kích hoạt flag sự cố.

---

## 📋 2. Kế hoạch từng Bước Triển khai & Xác minh

### 📍 Bước 1: Deploy Hệ thống lên AWS EKS (Thực hiện cùng CDO)
1. Cấu hình file `phase3/deploy/values-aio-llm.yaml` giữ nguyên mặc định trỏ vào OpenAI API với model `gpt-4o-mini` (đã cấu hình sẵn).
2. Tạo Secret chứa OpenAI API Key trong K8s (sử dụng tên key chính xác là `key`):
   ```bash
   kubectl create secret generic llm-api-key \
     --from-literal=key=<YOUR_OPENAI_API_KEY> \
     -n techx-tf3
   ```
3. Chạy lệnh deploy Helm của TF3 (phối hợp cùng CDO):
   ```bash
   helm upgrade --install techx-tf3 ./phase3/techx-corp-chart \
     -f phase3/deploy/values-flagd-sync.yaml \
     -f phase3/deploy/values-aio-llm.yaml \
     -n techx-tf3
   ```

---

### 📍 Bước 2: Kiểm chứng luồng chạy bình thường (Happy Path & Cache)
1. Thực hiện port-forward về máy local:
   ```bash
   kubectl -n techx-tf3 port-forward svc/frontend-proxy 8080:8080
   ```
2. Mở trình duyệt truy cập một trang sản phẩm và xem phần tóm tắt AI.
3. **Xác minh Cache MISS (Lần đầu load)**:
   - Check log của pod `product-reviews`:
     `kubectl logs -n techx-tf3 -l app=product-reviews-server -c server`
   - Log phải hiển thị: `Cache MISS for product <ID>. Calling LLM...`
4. **Xác minh Cache HIT (F5 load lại trang)**:
   - Tải lại trang sản phẩm.
   - Log của pod phải hiển thị: `Cache HIT for product <ID>. Returning cached summary.`
   - Thời gian load khối AI giảm xuống $<50ms$.

---

### 📍 Bước 3: Diễn tập sự cố 1 - LLM bị lỗi 429 Rate Limit
1. Kích hoạt flag lỗi bằng cách cập nhật flagd (hoặc qua console của BTC): Bật flag `llmRateLimitError` thành `true`.
2. Truy cập trang sản phẩm mới (chưa có cache) khoảng 5-10 lần để bao phủ cả hai nhánh ngẫu nhiên trong code.
3. **Xác minh cơ chế Xử lý Lỗi (Retry & Fallback)**:
   - Check log của pod `product-reviews`. Do logic code phân nhánh ngẫu nhiên 50/50 đối với mock rate-limit error, bạn sẽ thấy 2 hành vi:
     - **Nhánh 1 (50% request)**: Lời gọi rơi vào mock model `techx-llm-rate-limit` $\rightarrow$ Ném exception lập tức $\rightarrow$ Trả về thông báo Fallback tiếng Việt ngay không qua retry.
     - **Nhánh 2 (50% request)**: Đi qua normal path gọi OpenAI API $\rightarrow$ Gặp lỗi 429 thật $\rightarrow$ Kích hoạt cơ chế **Retry lần 1 $\rightarrow$ Retry lần 2** (chờ với exponential backoff + jitter). Nếu vẫn lỗi $\rightarrow$ Trả về thông báo Fallback tiếng Việt.
   - **Đầu ra cho khách hàng**: Trang web vẫn hiển thị đẹp, phần tóm tắt AI ẩn đi một cách an toàn và hiện thông báo tiếng Việt: `"Tóm tắt tạm thời không khả dụng. Vui lòng tham khảo các đánh giá chi tiết bên dưới."` (Không bị treo trang hoặc hiện lỗi đỏ).
   - **Metric**: Metric `app_ai_assistant_counter` tăng 1 đơn vị với nhãn `status: error`.

---

### 📍 Bước 4: Diễn tập sự cố 2 - Tóm tắt sai lệch (Hallucination)
1. Kích hoạt flag lỗi của BTC: Bật flag `llmInaccurateResponse` thành `true` đối với sản phẩm `L9ECAV7KIM`.
2. Gửi request tóm tắt cho sản phẩm này.
3. **Xác minh Guardrail chặn cache**:
   - Log của pod phải hiển thị: `Flag llmInaccurateResponse is active. Skipping caching for this summary to prevent database poisoning.`
   - Điều này đảm bảo sau khi BTC tắt flag sự cố, khách hàng tải lại trang sẽ nhận được tóm tắt đúng từ LLM thật, không bị lưu cấu trúc sai lệch trong bộ nhớ đệm.

---

### 📍 Bước 5: Chạy Script Đánh giá Chất lượng (Evaluation Script)
1. Truy cập trang sản phẩm trên trình duyệt và sao chép (copy) đoạn văn tóm tắt tiếng Việt thực tế được tạo ra bởi OpenAI.
2. Thực thi script đánh giá bằng cách truyền đoạn tóm tắt đó qua đối số CLI `--summary`:
   ```bash
   cd eval
   python eval_summarization.py --summary "Dán đoạn tóm tắt thực tế của bạn vào đây"
   ```
3. Script sẽ tính toán độ chính xác và tính điểm độ tin cậy dựa trên tập review mẫu tiếng Việt.
4. **Kết quả**: Đầu ra phải đạt điểm Faithfulness $\ge 0.6$ (ngưỡng thực tế được quy định trong code do sự hạn chế của word-overlap precision đối với các từ đồng nghĩa). Ghi lại điểm số này để đưa vào Slide Pitching.

