# Product Reviews NetworkPolicy Runtime Connectivity Evidence

## Result

**PASS** - `product-reviews-business-policy` allows the declared Product
Catalog dependency and blocks an undeclared lateral connection to Payment.

Test window: `2026-07-29T16:20:41Z` to `2026-07-29T16:22:50Z`  
Cluster: `techx-corp-tf3`  
Namespace: `techx-tf3`  
Source pod: `product-reviews-7bb896dfb-f9sxh`

## Preconditions

- Argo CD application `techx-infrastructure-app`: `Synced/Healthy`.
- Applied revision: `632204249f3b2d7107b8b74f93145933f74397f3`.
- Source pod was Ready with zero restarts.
- NetworkPolicy `product-reviews-business-policy` was active.
- AWS VPC CNI generated PolicyEndpoint
  `product-reviews-business-policy-7m9np`.
- Product Catalog Service: `172.20.145.185:8080`.
- Payment Service: `172.20.105.214:8080`.
- Payment had ready endpoints `10.0.33.27:8080` and
  `10.0.8.90:8080`.

## Expected Flows

| Source | Destination | Port | Expected |
|---|---|---:|---|
| product-reviews | product-catalog | 8080/TCP | ALLOW |
| product-reviews | payment | 8080/TCP | DENY |

Product Catalog is an explicit egress dependency in the policy. Payment is
healthy but is not present in the Product Reviews egress allowlist.

## Allowed Flow

Command:

```powershell
kubectl -n techx-tf3 exec product-reviews-7bb896dfb-f9sxh -- `
  python -c "import socket,time; h='product-catalog'; p=8080; t=time.time(); s=socket.create_connection((h,p),5); s.close(); print('PASS ALLOW %s:%d connected in %.3fs'%(h,p,time.time()-t))"
```

Output:

```text
PASS ALLOW product-catalog:8080 connected in 0.092s
```

## Denied Flow

Command:

```powershell
kubectl -n techx-tf3 exec product-reviews-7bb896dfb-f9sxh -- `
  python -c "import socket,time,sys; h='payment'; p=8080; t=time.time(); s=socket.socket(); s.settimeout(5); exec(\"try:\n s.connect((h,p)); s.close(); print('FAIL: unexpectedly connected'); sys.exit(2)\nexcept TimeoutError:\n print('PASS DENY %s:%d timed out after %.3fs'%(h,p,time.time()-t)); sys.exit(0)\")"
```

Output:

```text
PASS DENY payment:8080 timed out after 5.006s
```

The timeout is the expected AWS VPC CNI NetworkPolicy drop behavior.

## Negative-Control Validation

The denied result was not accepted based on timeout alone:

1. Payment had two ready EndpointSlice addresses on port `8080`.
2. A temporary local port-forward confirmed that the Payment listener was
   reachable:

```text
PAYMENT_LISTENER_TCP=True
Forwarding from 127.0.0.1:18080 -> 8080
PORT_FORWARD_STOPPED=True
```

The port-forward was used only to validate the destination listener and was
stopped immediately after the probe.

An earlier probe to `payment:50051` was discarded because the current Payment
Service exposes and targets port `8080`; testing a closed or unused port would
have produced invalid deny evidence.

## Conclusion

The policy behaves as intended for the tested paths:

- Required Product Reviews to Product Catalog traffic remains available.
- Undeclared Product Reviews to Payment lateral traffic is blocked.
- The denied result is attributable to policy enforcement, not a missing
  Payment endpoint or inactive listener.

Only `get`, `exec`, and a temporary `port-forward` were used. No resource was
applied, created, patched, deleted, scaled, or restarted.
