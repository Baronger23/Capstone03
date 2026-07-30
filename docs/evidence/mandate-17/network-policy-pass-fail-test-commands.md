# Mandate 17 - NetworkPolicy fail test commands

Namespace: `techx-tf3`
Test case: `frontend -> payment:8080` bi chan
Muc tieu: chung minh NetworkPolicy/default-deny-all dang chan lateral movement khong hop le.

## Ly do chon case nay

- Khong can tao pod moi tren production.
- Khong dung `kubectl debug`, nen khong bi PSA/Kyverno/VAP chan ephemeral debug image.
- Dung chinh container `frontend` dang chay that.
- Image `frontend` co san `sh` va `nc`, du de test ket noi TCP.
- Ket qua de giai thich: `payment` chi nen nhan traffic tu service hop le nhu `checkout`, khong nen nhan truc tiep tu `frontend`.

## Dieu kien truoc khi test

Chay cac lenh nay trong PowerShell, trong tab da cau hinh kubeconfig/SSM tunnel toi EKS.

Kiem tra namespace truy cap duoc:

```powershell
kubectl -n techx-tf3 get ns techx-tf3
```

Ky vong:

```text
techx-tf3   Active
```

Kiem tra `frontend` va `payment` dang co pod running:

```powershell
kubectl -n techx-tf3 get pods | Select-String "frontend|payment"
```

Ky vong:

```text
frontend...   Running
payment...    Running
```

Kiem tra `default-deny-all` dang ton tai:

```powershell
kubectl -n techx-tf3 get netpol default-deny-all
```

Ky vong:

```text
NAME               POD-SELECTOR   AGE
default-deny-all   <none>         ...
```

## Buoc 1 - Kiem tra DNS van hoat dong

Muc dich: loai tru kha nang fail do DNS. Neu DNS phan giai duoc `payment` nhung ket noi TCP van timeout/fail thi bang chung nghieng ve NetworkPolicy.

```powershell
kubectl -n techx-tf3 exec deploy/frontend -- nslookup payment
```

Ky vong:

```text
Name: payment.techx-tf3.svc.cluster.local
Address: ...
```

Neu image `frontend` khong co `nslookup`, co the bo qua buoc nay va chay truc tiep buoc 2.

## Buoc 2 - FAIL case: frontend khong duoc goi payment

Chay:

```powershell
kubectl -n techx-tf3 exec deploy/frontend -- sh -c 'nc -w 5 -z payment 8080; echo exit=$?'
```

Ky vong:

```text
exit=1
```

Giai thich:

- `frontend` thu mo ket noi TCP den `payment:8080`.
- Policy cua `payment` khong cho phep caller truc tiep tu `frontend`.
- `default-deny-all` va allowlist hien co se drop traffic nay.
- `nc` cho den het timeout 5 giay roi tra `exit=1`.

Day la ket qua PASS cho test deny, vi muc tieu cua test la chung minh traffic khong hop le bi chan.

## Buoc 3 - Doi chung nhanh: frontend van goi duoc service duoc phep

Muc dich: chung minh cluster/app khong bi hong chung, chi chan dung duong khong duoc phep.

```powershell
kubectl -n techx-tf3 exec deploy/frontend -- sh -c 'nc -w 5 -z product-catalog 8080; echo exit=$?'
```

Ky vong:

```text
exit=0
```

Giai thich:

- `frontend -> product-catalog:8080` la dependency hop le.
- Neu lenh nay thanh cong trong khi `frontend -> payment:8080` fail, co the noi policy dang phan tach dung traffic hop le va khong hop le.

## Buoc 4 - Cau tong ket de dua vao bao cao

```text
PASS: frontend -> product-catalog:8080 duoc phep, exit=0.
PASS: frontend -> payment:8080 bi chan dung ky vong, exit=1 sau timeout.

Ket luan: default-deny-all + allow NetworkPolicy dang chan lateral movement tu frontend sang payment, trong khi van giu duong hop le frontend sang product-catalog.
```

## Luu y khi demo

- `exit=1` trong FAIL case la ket qua dung, khong phai loi test.
- Neu thay `Connection refused` ngay lap tuc thi khong dung lam bang chung NetworkPolicy; luc do co the service/port khong lang nghe.
- Bang chung NetworkPolicy manh hon la ket noi bi treo den timeout roi fail.
- Khong dung `kubectl debug`/`nicolaka/netshoot` cho case nhanh nay vi admission restricted co the chan ephemeral container.
