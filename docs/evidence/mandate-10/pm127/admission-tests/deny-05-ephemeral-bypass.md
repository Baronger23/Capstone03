# deny-05 — ephemeral container không được thành đường lách

## Vì sao case này tách riêng, không phải file YAML

`ephemeralContainers` **không đặt được lúc tạo pod** — Kubernetes chỉ nhận chúng qua subresource `pods/ephemeralcontainers`, tức phải thêm vào một pod **đang chạy**. Nên không thể viết thành một manifest `kubectl apply` như 4 case kia.

## Vì sao vẫn phải test

Đây không phải trường hợp giả định. Ngày 28/07, pod `fraud-detection-7555fcd4d8-nnhg7` bị phát hiện có **3 ephemeral container `nicolaka/netshoot`** ai đó để lại từ một phiên `kubectl debug` — image ngoài, pin bằng tag, không có trong catalog.

Nếu policy chỉ soi `containers` mà bỏ `ephemeralContainers` thì bất kỳ ai có quyền `kubectl debug` đều đưa được image tuỳ ý vào namespace production, và toàn bộ việc pin digest trở nên vô nghĩa.

Policy có phủ cả 3 danh sách — `containers`, `initContainers`, `ephemeralContainers` — và đã có test khoá điều đó (`test_external_policy_defers_every_first_party_form_to_the_signature_policy`).

## Cách chạy

Cần một pod bất kỳ đang chạy trong `techx-tf3` để bám vào:

```sh
POD=$(kubectl get pods -n techx-tf3 --field-selector=status.phase=Running \
  -o jsonpath='{.items[0].metadata.name}')

kubectl debug -n techx-tf3 "$POD" --image=nicolaka/netshoot --target=<container> -- sleep 60
```

## Kỳ vọng sau khi Enforce

Lệnh **bị từ chối**, message nêu rõ `External images must match the reviewed exact-digest catalog.`

Kiểm tra không có gì được thêm vào:

```sh
kubectl get pod "$POD" -n techx-tf3 -o jsonpath='{.spec.ephemeralContainers}'
```

Phải trả **rỗng**.

## Thay đổi hành vi cần báo trước cho team

Sau khi Enforce, **`kubectl debug` trên pod trong `techx-tf3` sẽ không dùng được nữa** với image tuỳ ý.

Ai cần troubleshoot có hai lựa chọn:

1. Dùng image đã có trong catalog (ví dụ `busybox@sha256:73aaf090…`)
2. Thêm image debug muốn dùng vào catalog qua PR — CI drift gate sẽ kiểm tra

Đây là hệ quả **có chủ đích**, không phải tác dụng phụ: một đường đưa image tuỳ ý vào production thì đúng ra phải đóng.
