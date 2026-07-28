# ADR 0011 — Mandate-19: Route Classification & Graduated Load Shedding

**Status:** Shadow observation; enforcement and runtime verification pending
**Date:** 2026-07-23
**Author:** CDO-01 (TF3)
**Mandate:** Directive #19 — Biết trần của mình và nâng trần bằng hiệu suất
**Depends on:** PM-153 (HPA tuning + circuit_breakers + breakpoint evidence)

> This ADR does not claim that Directive #19 has passed. The before ceiling is
> measured; the new ceiling, density improvement and enforced overload result
> must be signed from `docs/evidence/mandate-19/after-run-template.md`.

---

## Bối cảnh

Directive #19 yêu cầu xác định trần thông lượng thật của hệ, nâng trần bằng hiệu suất (không bằng node), xử nút thắt, và đảm bảo hệ **xuống mềm** (graceful degradation) khi vượt trần — ưu tiên checkout, shed load browse, không sập toàn bộ.

Hiện trạng:
- Mandate-02: 200 user pass (p95 ~46ms, checkout 99.98%), **breakpoint thật chưa được đo**
- Mandate-16: Checkout critical path song song hoá, latency 185ms → ~45ms
- Envoy hiện tại: một catch-all route `/` không phân loại traffic; không có cơ chế shed

---

## Phạm vi ADR này (PM-154)

ADR này chỉ ghi nhận quyết định **route classification** và **local_ratelimit** (Envoy-level load shedding). Các quyết định về:
- HPA CPU target tuning (65%→75%)
- Envoy circuit_breakers max_requests tăng
- Kết quả breakpoint test

→ ghi nhận trong **PM-153** (đã tách sang PR riêng).

---

## Quyết định

### 1. Route classification

Tách catch-all `/` thành 3 class ưu tiên rõ ràng:

| Route | Name | Ưu tiên | Rate limit |
|---|---|---|---|
| `/api/checkout` | `checkout_protected` | Tối cao | Không (global bucket 10 000/s — không bao giờ trigger) |
| `/api/cart` | `cart_protected` | Cao | Không (cùng global bucket) |
| `/api/products/<id>` | `product_detail_protected` | Cao | Không (cùng global bucket) |
| `/` (catch-all) | `browse_shedable` | Thấp | Token bucket per-pod (xem § 2) |

**Tại sao `/api/products/<id>` được bảo vệ:**
Locustfile `add_to_cart()` gọi `GET /api/products/<id>` trước `POST /api/cart`. Nếu product detail bị shed (429) → Locust cart add fail → checkout journey gãy. Prefix `/api/products/` (có trailing slash) chỉ match detail pages; `GET /api/products` (list, không có slash) vẫn rơi vào `browse_shedable`.

**Tại sao `/api/cart` được bảo vệ:**
Cart write operations (add/update/delete item) là bước ngay trước checkout trong user journey. Nếu cart bị shed trong khi checkout được phép, người dùng không thể hoàn thành đơn hàng → checkout protection bị vô nghĩa. Bảo vệ cả hai tạo ra "checkout funnel shield".

**Tại sao browse bị shed trước:**
Browse (homepage, product listing, search) là traffic khối lượng lớn, không phát sinh doanh thu trực tiếp. Đây là traffic đúng đắn để sacrifice khi hệ thống tiếp cận trần.

### 2. Cơ chế load shedding — Envoy `local_ratelimit`

**Lựa chọn:** `envoy.filters.http.local_ratelimit` (in-process token bucket)

**Lý do:**
- In-process trong Envoy → không cần Redis external, không thêm network hop, latency overhead ~0.01ms
- Per-route `typed_per_filter_config` → phân loại độc lập cho từng route class
- Stats counter `browse_rate_limiter.rate_limited` → có thể quan sát shadow mode trước khi enforce
- HTTP 429 + custom header → client và monitoring phân biệt được rate-limit response vs backend error

**Bootstrap token-bucket formula (per-pod; local_ratelimit is in-process):**
```
safe_browse_rps =
  (highest_passing_rps × browse_fraction)
  - (highest_passing_rps × operational_margin)
max_tokens = floor(safe_browse_rps / minimum_ready_proxy_count)
```

- `highest_passing_rps`: 174.75 RPS from PM-152
- `browse_fraction`: 0.70 from the canonical load profile
- `operational_margin`: 0.10 of the highest passing throughput
- `minimum_ready_proxy_count`: 2

Bootstrap calculation:
```
floor(((174.75 × 0.70) - (174.75 × 0.10)) / 2) = 52
```

The deployed configuration rounds this down to **50 RPS/proxy**. It must be
recalibrated from the new-ceiling evidence after the after-run.

### 3. Enforcement state

Shadow mode was the observation stage:
```yaml
filter_enabled:  numerator: 100   # Đếm — stat tăng khi token bucket bị exceed
filter_enforced: numerator: 0     # KHÔNG reject — traffic pass-through 100%
```

The current implementation remains in shadow mode:
```yaml
filter_enabled:  numerator: 100   # Count would-be shedding
filter_enforced: numerator: 0     # Do not reject production traffic
token_bucket:
  max_tokens: 50
```
After shadow counters and protected-route matching are verified, enforcement
must be promoted gradually in a separate reviewed change. Directive #19 is not
considered complete until sustained enforced overload shows intentional browse
429s, zero protected-route 429s, checkout SLO holding and an unchanged node-set.

### 4. Response header

Header `x-techx-load-shed: browse` được thêm vào response khi request bị shed.
- Không dùng `x-local-rate-limit` (tên Envoy-internal, không mang semantic của hệ)
- `x-techx-load-shed: browse` → client và load balancer biết đây là shed decision, không phải lỗi backend
- Header is visible on enforced browse responses and is mandatory evidence.

---

## Runtime acceptance gates

> [!IMPORTANT]
> Enforced configuration is only accepted as verified after all gates below pass:

1. **PM-153 merged và evidence có sẵn:**
   - Breakpoint RPS đã đo (Locust + Prometheus)
   - `frontend-proxy-Ready-count` tại thời điểm test đã ghi lại
   - `max_tokens` đã tính theo công thức trên

2. **PM-154 enforced overload runs live ≥ 5 minutes:**
   - `browse_rate_limiter.rate_limited` and `enforced` counters increase
   - Browse receives intentional 429 responses with both expected headers
   - Checkout/cart receive zero rate-limit responses and retain their SLO

3. **Frontend-proxy image đã được build và validate:**
   - `envoy --validate-config` pass
   - CI build-push-ecr.yml cho `frontend-proxy` thành công
   - `imageOverride` trong `values-prod.yaml` cập nhật tag mới

---

## Evidence cần lưu (mandatory)

| Evidence | Công cụ | Lưu tại |
|---|---|---|
| Locust stats (RPS, error rate, breakpoint) | Locust UI screenshot / CSV | `docs/evidence/mandate-19/` |
| Prometheus metrics (p99, checkout rate, browse rate_limited counter) | Grafana screenshot / promql export | `docs/evidence/mandate-19/` |
| Envoy counter (`browse_rate_limiter.rate_limited`) | `wget -qO- /stats \| grep rate_limit` | `docs/evidence/mandate-19/` |
| Jaeger trace (checkout protected, browse 429 path) | Jaeger screenshot | `docs/evidence/mandate-19/` |
| Node timeline (node count không đổi) | `kubectl get nodes` before/after | `docs/evidence/mandate-19/` |
| Rollback evidence | `kubectl rollout undo deploy/frontend-proxy` output | `docs/evidence/mandate-19/` |

---

## Trade-offs đã chấp nhận

| Trade-off | Lý do |
|---|---|
| Browse user bị 429 khi vượt trần | Mandate yêu cầu shed, không phải sập; checkout được bảo vệ |
| Token bucket per-pod (không global) | local_ratelimit in-process; tổng throughput = max_tokens × pod_count |
| Enforce candidate before final new-ceiling calibration | Bootstrap cap is conservative and derived from measured before data; runtime acceptance and recalibration are mandatory |
| Local bucket scales with proxy count | Record Ready proxy count throughout the run and calculate the effective cluster browse cap |
| `/api/cart` protected (rộng hơn chỉ checkout) | Cart writes là phần của checkout funnel — shed cart = shed checkout gián tiếp |

---

## Không thay đổi

- HPA targets / maxReplicas → PM-153
- Envoy circuit_breakers → PM-153
- flagd, `/flagservice/`, `/otlp-http/` routes
- Stateful services, Karpenter NodePool
- Topology prod (PDB, topologySpreadConstraints)

---

## Tham chiếu

- PM-153 (HPA + circuit_breakers): `feat/pm-153` branch
- [Mandate-02 load test report](../mandate-02-load-test-report.md)
- [Mandate-16 checkout latency](../mandate-16-checkout-latency-optimization.md)
- [envoy.tmpl.yaml](../../phase3%20-%20information/techx-corp-platform/src/frontend-proxy/envoy.tmpl.yaml)
- [hpa-hotpath.yaml](../../gitops/infrastructure/hpa-hotpath.yaml)
