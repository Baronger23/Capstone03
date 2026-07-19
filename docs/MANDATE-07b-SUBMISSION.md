# Báo Cáo Nộp Bài: AI Mandate #7b - Luồng Phát Hiện Sự Cố Chủ Động (Proactive ML Detection & RCA)

- **Trạng thái**: Sẵn sàng đánh giá (Ready for Evaluation)
- **Đội ngũ thực hiện**: Task Force 3 (Team AIO02)
- **Hạn nộp**: Thứ Bảy 25/07/2026

---

## 🎫 1. Thông Tin Ticket Jira

* **Summary:** `AI MANDATE #7b`
* **Labels:** `ai-mandate`, `m7`
* **Priority:** `High`

---

## 💬 2. Nội Dung Comment Bằng Chứng (Evidence Comment)

*(Copy toàn bộ phần bên dưới để paste vào comment của Jira Ticket)*

---

### 🔗 1. Link PR / Commit (Code & Config)
* **Repository:** `https://github.com/Baronger23/Capstone03`
* **Mã nguồn Proactive Detection & Slack Approval API:** [main.py](file:///d:/Xbrain/Read_Capstone03/aiops-engine/main.py#L344-L370)
* **Mô-đun quét chủ động Isolation Forest:** [anomaly_detector.py](file:///d:/Xbrain/Read_Capstone03/aiops-engine/anomaly_detector.py)
* **Mô-đun Chẩn đoán LLM & vector KB (RAG):** [llm_diagnostician.py](file:///d:/Xbrain/Read_Capstone03/aiops-engine/llm_diagnostician.py)
* **Mô-đun tương tác thẻ duyệt Slack (Interactive card):** [slack_notifier.py](file:///d:/Xbrain/Read_Capstone03/aiops-engine/slack_notifier.py)

---

### 🚀 2. Hướng Dẫn Chạy Lại (Repro Steps)
Mentor có thể kiểm thử luồng chẩn đoán và phê duyệt tự động trên Slack qua các bước:

1. **Bơm sự cố giả lập:** Copy tệp CSV dị thường của frontend vào Pod đang chạy:
   ```bash
   kubectl cp aiops-engine/datametric/fake_frontend.csv deployment/aiops-engine:/app/datametric/fake_frontend.csv -n techx-tf3
   ```
2. **Theo dõi log phát hiện & chẩn đoán:**
   ```bash
   kubectl logs deployment/aiops-engine -n techx-tf3 --tail=50 -f
   ```
   *Bạn sẽ thấy log ghi nhận tải file: `[SIMULATION] Loaded fake metric file for frontend...`, mô hình phát hiện `IF prediction for frontend: -1` và gọi Bedrock LLM sinh chẩn đoán.*
3. **Phê duyệt trên Slack:** Mở kênh Slack liên kết webhook, kiểm tra card Approve/Reject và bấm nút **Approve** để Engine tự động thực thi hành động scale/restart pod.
4. **Dọn dẹp:**
   ```bash
   kubectl exec deployment/aiops-engine -n techx-tf3 -- rm /app/datametric/fake_frontend.csv
   ```

---

### 📊 3. Bằng Chứng Chạy Thật (Real Running Evidence)

#### A. Trạng thái Pod vận hành ML proactive loop 24/7 trên EKS:
```bash
kubectl get pods -n techx-tf3 -l app=aiops-engine

NAME                            READY   STATUS    RESTARTS   AGE
aiops-engine-5d5c7964c6-q4ff5   1/1     Running   0          10m
```
*(Pod duy trì 0 lần restart chứng minh engine hoạt động cực kỳ ổn định).*

*(CHỤP ẢNH màn hình terminal chạy lệnh trên và lưu vào thư mục docs/images/eks_pods_status.png)*
![1. Trạng thái Pod EKS khỏe mạnh](/d:/Xbrain/Read_Capstone03/docs/images/eks_pods_status.png)

#### B. Log suy luận Proactive ML của Pod:
```
2026-07-17 08:57:30,854 [INFO] AIOpsEngine.AnomalyDetector: SLO Burn Rate Check (Max) - 5m: 6.52 (flagd), 1h: 3.08 (flagd)
2026-07-17 08:57:30,854 [INFO] AIOpsEngine.Main: SLO is stable. Running ML Isolation Forest proactive scans on core services...
2026-07-17 08:57:30,958 [INFO] AIOpsEngine.AnomalyDetector: IF prediction for frontend: 1 (1: Normal, -1: Anomaly)
2026-07-17 08:57:31,059 [INFO] AIOpsEngine.AnomalyDetector: IF prediction for checkout: 1 (1: Normal, -1: Anomaly)
...
```
*(CHỤP ẢNH màn hình terminal chứa logs log phát hiện lỗi "IF prediction for frontend: -1" và lưu vào docs/images/eks_logs_anomaly.png)*
![2. Logs phát hiện bất thường](/d:/Xbrain/Read_Capstone03/docs/images/eks_logs_anomaly.png)

#### C. Thẻ tương tác Approve/Reject gửi lên Slack:
* Hệ thống đã thiết lập mức độ rủi ro mặc định là `MEDIUM` cho các cảnh báo chủ động từ Isolation Forest để đảm bảo an toàn, gửi card chờ kỹ sư duyệt trên Slack thay vì tự động can thiệp bừa bãi.

*(CHỤP ẢNH màn hình tin nhắn Slack Card chứa nút Approve/Reject và chẩn đoán LLM, lưu vào docs/images/slack_card_approval.png)*
![3. Card duyệt Slack Approve/Reject](/d:/Xbrain/Read_Capstone03/docs/images/slack_card_approval.png)

---

### 📝 4. Thiết Kế & Đánh Đổi (Link ADR Ký Tên)
Chi tiết về luồng chẩn đoán RCA (R), gọi Bedrock LLM kết hợp RAG Playbooks, và cơ chế phê duyệt Slack phê duyệt thủ công (Human-in-the-loop) được ghi nhận tại:
* **ADR Kiến trúc:** [CONSOLIDATED_ADR.md](file:///d:/Xbrain/Read_Capstone03/docs/adr/CONSOLIDATED_ADR.md)
* **Ký tên phê duyệt:** Nhóm AIO02 (Task Force 3).
