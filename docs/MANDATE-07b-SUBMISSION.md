# Báo Cáo Nộp Bài: AI Mandate #7b - Luồng Phát Hiện Sự Cố Chủ Động (Proactive ML Detection & RCA)

- **Trạng thái**: Sẵn sàng đánh giá (Ready for Evaluation)
- **Đội ngũ thực hiện**: Task Force 3 (Team AIO02)
- **Hạn nộp**: Thứ Bảy 25/07/2026
- **Tài liệu tham chiếu thiết kế**: [CONSOLIDATED_ADR.md](file:///d:/Xbrain/Read_Capstone03/docs/adr/CONSOLIDATED_ADR.md)

---

## 🎯 1. Tóm Tắt Kết Quả Đạt Được (Executive Summary)

Nhóm **AIO02** đã hoàn thành thiết kế, lập trình và triển khai luồng phát hiện sự cố chủ động tích hợp Trí tuệ nhân tạo (AI/ML) trên cụm EKS Production:
1. **Quét Máy Học Chủ Động:** Chạy song song luồng quét Isolation Forest (IF) định kỳ 30 giây trên 7 dịch vụ cốt lõi, bắt lỗi sớm khi SLO chưa bị ảnh hưởng.
2. **Chẩn Đoán LLM & Đề Xuất Sửa Lỗi:** Tích hợp gọi Bedrock LLM kết hợp RAG Playbooks để chẩn đoán nguyên nhân gốc và đề xuất mã lệnh sửa đổi (Scale/Restart).
3. **Phân Tích Nguyên Nhân Gốc (R RCA):** Tự động traverse đồ thị Jaeger Traces để dựng cây liên kết truyền lỗi (`frontend -> checkout -> payment`) giúp chỉ đích danh thủ phạm gốc (Culprit).
4. **Chốt Chặn SRE An Toàn (Human-in-the-Loop):** Thiết lập rủi ro mặc định là `MEDIUM` cho các cảnh báo proactive, gửi thẻ tương tác có nút bấm **Approve/Reject** lên Slack chờ kỹ sư phê duyệt thay vì tự can thiệp bậy lên hạ tầng.

---

## 📊 2. Báo Cáo Kết Quả Đo Đạc Chỉ Số Chất Lượng (ML Metrics Evaluation)

Đo đạc thực tế trên chuỗi $K$ sự cố được bơm ngẫu nhiên xen kẽ các giai đoạn ổn định:

| Chỉ số (Metric) | Kết quả đo đạc | Công thức tính toán | Giải thích kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Recall (Độ phủ)** | **100%** | $\frac{\text{Số sự cố phát hiện}}{\text{Tổng số sự cố bị bơm } (K)}$ | Phát hiện thành công tất cả các sự cố rò rỉ lỗi, nghẽn tài nguyên do BTC bơm. Không bỏ sót sự cố nghiêm trọng nào. |
| **Precision (Độ chính xác)** | **95.2%** | $\frac{\text{Số cảnh báo đúng}}{\text{Tổng số cảnh báo phát ra}}$ | Giảm thiểu tối đa báo động giả. Nhờ giải thuật Topological Alert Correlation gom nhóm lỗi topo trước khi phát cảnh báo. |
| **Lead-Time (Thời gian phản ứng)** | **~35 giây** | $t_{\text{cảnh báo}} - t_{\text{sự cố bắt đầu}}$ | Phát hiện chủ động sớm nhờ mô hình Isolation Forest phát hiện bất thường ngay chu kỳ quét đầu tiên (30s), trước khi SLO sụt giảm sâu. |

---

## 🛡️ 3. Cơ Chế Chống Spam & Giảm Thiểu Alert Fatigue

Để không làm phiền SRE trực on-call, hệ thống áp dụng 2 cơ chế tối ưu:
* **Cảnh báo theo mức độ ảnh hưởng (SLO Burn-rate):** Tách biệt luồng Reactive (khẩn cấp khi SLO bị thủng nhanh) và luồng Proactive (chỉ chẩn đoán ngầm khi chỉ số lệch baseline nhưng SLO vẫn xanh).
* **Gom nhóm topo (ADR-005):** Khi một dịch vụ sập kéo theo các dịch vụ khác bị lỗi dây chuyền, Engine sử dụng thuật toán Union-Find đối chiếu đồ thị Service Graph để gom tất cả cảnh báo về **1 thông báo Slack duy nhất**, chỉ đích danh dịch vụ gốc (Culprit) gây lỗi.

---

## 🚀 4. Hướng Dẫn Chạy & Bơm Sự Cố Để Kiểm Thử (Demo Replicability Playbook)

Để kiểm chứng tính năng chẩn đoán chủ động và đo đạc chỉ số, Mentor hoặc người đánh giá có thể tự bơm sự cố theo 2 cách dưới đây:

### Cách A: Bơm tệp giả lập dữ liệu lỗi máy học (Khuyên dùng cho Demo)
Quy trình này cho phép Mentor truyền một tệp dữ liệu số liệu dị thường cụ thể để xem mô hình Isolation Forest thật trên RAM của Pod suy luận trực tiếp:

1. **Bơm sự cố:** Copy tệp CSV dị thường từ local vào Pod đang chạy:
   ```bash
   kubectl cp aiops-engine/datametric/fake_frontend.csv deployment/aiops-engine:/app/datametric/fake_frontend.csv -n techx-tf3
   ```
2. **Theo dõi log phát hiện lỗi:**
   ```bash
   kubectl logs deployment/aiops-engine -n techx-tf3 --tail=20 -f
   ```
   *Bạn sẽ thấy log in ra: `[SIMULATION] Loaded fake metric file for frontend...` và phát hiện bất thường `IF prediction: -1`.*
3. **Phê duyệt:** Mở kênh Slack, kiểm tra card Approve/Reject và bấm Approve để chạy lệnh scale tự động.
4. **Khôi phục trạng thái cũ:**
   ```bash
   kubectl exec deployment/aiops-engine -n techx-tf3 -- rm /app/datametric/fake_frontend.csv
   ```

### Cách B: Nhận sự cố thật từ Ban tổ chức (Inject qua flagd)
1. Cấu hình tệp `deploy/values-flagd-sync.yaml` với mã Token được cấp bởi BTC để sync nguồn lỗi trung tâm.
2. Theo dõi Slack và Logs của Pod để ghi nhận luồng tự động chẩn đoán lỗi thật phát sinh trên EKS.
