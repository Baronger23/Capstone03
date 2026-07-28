# ADR 0012 - Mandate 13: Rollout Spot + Graviton không tạo SPOF

**Ngày:** 24/07/2026  
**Người quyết định (ký):** Hà Tây Nguyên  
**Trạng thái:** Đã rollout production và đã có evidence interruption + scale-down  
**Phạm vi:** Reliability + Cost Optimization + Operational Excellence cho Mandate 13

## 1. Bối cảnh

Production đã có Spot thật và một phần workload critical path đã chạy trên Spot, nhưng trước khi chốt Mandate 13 vẫn còn ba khoảng trống lớn:

1. Tỷ lệ Spot chưa vượt 50% theo cách nhìn evidence đủ thuyết phục.
2. Chưa có arm64/Graviton chạy live trên production.
3. NodePool Spot trước đó bị khóa khả năng co xuống, nên không thể quay được evidence scale-down đúng yêu cầu.

Một phương án cũ từng thử đưa `recommendation` lên arm64 trên pool Spot riêng đã bị loại bỏ vì không an toàn:

- `recommendation` chỉ có 1 replica
- không có PDB
- mất 1 Spot node sẽ tạo SPOF mới
- pool bị freeze consolidation nên tự làm hỏng yêu cầu scale-down

## 2. Quyết định

Chọn phương án rollout production an toàn hơn, với mục tiêu mở đường cho evidence Mandate 13 nhưng không tạo rủi ro mới trên luồng khách hàng:

1. tắt nodegroup `stateful_1a` đã rỗng trên production
2. hạ baseline managed on-demand nodegroup từ `4 -> 3`
3. bỏ cấu hình freeze consolidation trên NodePool Spot hiện có
4. thêm NodePool `flash-sale-spot-arm64` cho Spot arm64
5. chỉ opt-in `product-catalog` sang arm64
6. right-size `load-generator` và chỉnh request bộ nhớ cho `prometheus` / `opensearch`

## 3. Vì sao chọn `product-catalog`

`product-catalog` được chọn thay vì `recommendation` vì:

- đã có `2 replicas`
- đã có PDB
- đã có topology spread theo zone và hostname
- image đang deploy là OCI image index multi-arch
- không phải frontend ingress point duy nhất
- không tạo SPOF mới khi mất 1 Spot node

Nói ngắn gọn:

> Nếu buộc phải chọn một service để đưa Graviton live trước, `product-catalog` là điểm vào an toàn hơn `recommendation`.

## 4. Vì sao không thêm on-demand arm64 fallback ngay

Trong vòng rollout này, thứ tự ưu tiên là:

- không tạo SPOF
- có Graviton live
- đẩy được Spot share lên cao hơn

Nếu thêm on-demand arm64 fallback ngay, floor cost sẽ tăng và evidence Spot share có nguy cơ xấu đi. Với `product-catalog` đang có 2 replica + PDB + spread, mất 1 Spot node vẫn còn replica còn lại phục vụ, phù hợp hơn phương án 1 replica trước đó.

## 5. Đánh đổi được chấp nhận

- Khi mất 1 Spot node, `product-catalog` vẫn sống nhờ replica còn lại, nhưng replacement pod có thể phải chờ Spot arm64 mới lên rồi mới trở lại trạng thái 2/2.
- Hạ baseline on-demand từ 4 xuống 3 tạo thêm áp lực cho Spot/Karpenter, nhưng vẫn an toàn hơn phương án hạ quá mạnh về 2.
- Việc nâng request cho `prometheus` và `opensearch` làm scheduler chặt hơn trên giấy, nhưng đổi lại giảm rủi ro memory pressure và eviction khi test thật.
- Mục tiêu của thay đổi này là mở đúng hướng để làm evidence, không đồng nghĩa tự động pass toàn bộ Mandate 13.

## 6. Evidence bắt buộc sau rollout

Sau khi merge và sync production, cần khóa các nhóm bằng chứng sau để claim pass hoàn chỉnh:

1. `kubectl get nodes` cho thấy có `arm64` live
2. `kubectl get pods -o wide` cho thấy `product-catalog` đã lên node arm64
3. tỷ lệ Spot > 50% được chốt theo cách đếm đã thống nhất
4. node count có xu hướng co xuống thật sau khi hạ tải
5. diễn tập mất 1 Spot node không làm rớt request khách hàng

## 7. Trạng thái thực tế tính đến ngày 25/07/2026

Đến **25/07/2026**, rollout này đã khóa được các nhóm evidence chính:

- production có Spot node thật
- production có Spot arm64 thật
- `flash-sale-spot` đã mở lên mức `3/3`
- load test đã đi vào thật trên `browse / cart / checkout`
- Grafana đã ghi nhận `Node count` tăng trong cửa sổ test
- interruption demo trên Spot node thật đã được thực hiện bằng `cordon/drain`
- terminal đã ghi nhận `evicting pod`
- sau khi hạ tải, `Node count` đã co từ `10 -> 9`
- Spot ratio tại thời điểm snapshot đạt:
  - `5/9 = 55.6%` nếu tính cả node on-demand exception cho chaos tooling
  - `5/8 = 62.5%` nếu loại node exception khỏi baseline app-tier

Điểm cần trình bày rõ khi bảo vệ là:

- 1 node on-demand hiện tại là **exception tạm thời** phục vụ chaos / fault injection
- node exception này không đại diện cho baseline capacity dài hạn của fleet application

## 8. Rollback

Nếu rollout gây xấu production:

1. bỏ file override liên quan Mandate 13
2. bỏ NodePool `flash-sale-spot-arm64`
3. trả `node_desired_size` / `node_min_size` về 4
4. bật lại `enable_stateful_node_group` nếu thực sự cần

Rollback phải đi qua GitOps / Terraform, không sửa tay trên production.

## 9. Kết luận

ADR này chốt rằng hướng rollout được chọn là:

- tăng Spot nhưng không tạo SPOF mới
- đưa Graviton live bằng service an toàn hơn
- tạo điều kiện để quay evidence production thật

ADR này là quyết định kiến trúc đã ký tên cho hướng rollout Mandate 13. Phần nghiệm thu production được chốt bằng evidence đi kèm trong thư mục `docs/evidence/mandate-13`.
