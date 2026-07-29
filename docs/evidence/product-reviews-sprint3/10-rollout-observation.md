# G9 — Rollout observation

**Kết quả: PASS. Không downtime. Tier-2 write path đã live.**

| | |
|---|---|
| Image bump PR | #593, merge 07:02:06Z |
| Digest mới | `sha256:be5cd78ae229ad036f5695c21c1575b2049931133fe19d25180393caaf6db5bc` |
| Digest cũ (rollback) | `sha256:35f413f43f8840039383f4fe64440e7f06415c6e5fb70591480451ee84d54067` |
| Argo revision sau rollout | `a8c43405f8ee96bea7f3748fdbb18e3812c36041`, `Synced`/`Healthy` |

## Rolling deployment — 45 giây, replicas không bao giờ tụt dưới 2

```
07:06:19  img=old  ready/avail/upd/total=2/2/2/2
07:06:34  img=NEW  2/2/1/3   surge rjhbh@ip-10-0-42-133  Pending
07:06:50  img=NEW  2/2/2/3   rjhbh Running/True, d67zz@ip-10-0-0-54 Pending
07:07:06  img=NEW  2/2/2/2   cả hai pod mới Running/True
```

`readyReplicas` giữ ở 2 suốt quá trình — `maxUnavailable: 0` + PDB `minAvailable: 1` hoạt động đúng.
Pod cuối 0 restart.

### Pod surge xếp được — điều mà G8 dự báo là sẽ KẸT

G8 (đo 06:20) kết luận pod surge hết chỗ. Kết luận đó đúng với trạng thái lúc đó, nhưng đã bị vượt
qua bởi `187c55c feat: migrate product reviews to ARM` của CDO01: `nodeSelector` thêm
`techx.io/arch: arm64` làm số domain của topologySpread **giảm từ 4 node elastic xuống 2 node ARM**,
nên `2,1 → skew 1` thoả `maxSkew=1`.

Thực tế khớp: surge pod `rjhbh` xuống thẳng `ip-10-0-42-133` — **cùng node đã có pod** — và Ready
sau ~16 giây. Không có `FailedScheduling` nào.

ARM nodepool còn headroom (`limits.nodes: 4`, đang dùng 2) nếu Karpenter cần cấp thêm.

## Không downtime — đo bằng probe liên tục

Bắn `GET /api/product-reviews/L9ECAV7KIM` mỗi 8 giây xuyên suốt rollout:
**0 response khác 200.** Baseline trước rollout: 200 @ 0.12–0.31s.

## Không ảnh hưởng lây

| Service | Trạng thái |
|---|---|
| `product-catalog` | 2/2 |
| `accounting` | 1/1 |
| Events `product-reviews` | toàn `Normal`, không `Unhealthy`/`CrashLoop`/`OOMKilled` |

## Tier-2 write path — LIVE

Câu hỏi summary (miss cache) qua storefront:

```
AI_OUTCOME product_id=L9ECAV7KIM stage=runtime_judge outcome=approved provider=bedrock model=amazon.nova-micro-v1:0
[DATABASE] Saved static summary for product_id: L9ECAV7KIM
[DB_SUMMARY] Persisted canonical summary product_id=L9ECAV7KIM version=0c21528a59c7
```

`review_version=0c21528a59c7` được ghi kèm — đúng thứ version guard sẽ so khi fallback.

### Gate `is_summary_request` — không phản hồi sai

| Câu hỏi | Đường đi | Persist? |
|---|---|---|
| "Can you summarize the customer reviews?" | `[CACHE] Hit!` → return sớm, `result=None` ở `finally` | Không (đúng — cache hit không ghi lại) |
| "Is this product waterproof?" | cache miss → Bedrock → `outcome=no_info`, `runtime_judge outcome=skipped` | **Không** |
| "Please give me an overview of what customers say in their reviews" | cache miss → Bedrock → `outcome=approved` | **Có** |

Case "waterproof" bị chặn bởi 3 lý do độc lập (không phải summary request; `judge_status="skipped"`;
kết quả là `NO_INFO_MESSAGE`) nên nó **chưa cô lập được** riêng tác dụng của gate `is_summary_request`.
Gate đó được kiểm riêng bằng unit test có mutation test (`test_narrow_question_approved_is_not_persisted`,
`test_narrow_question_deterministic_is_not_persisted`).

## ⚠️ CÒN OPEN: Tier-2 read path chưa kiểm chứng end-to-end trên production

Mới chứng minh được **ghi**. Việc **đọc** (fallback thật sự trả summary đã lưu với `tier=2`, và rơi
`tier=3` khi `review_version` lệch) đòi bơm lỗi LLM vào production — bật flag `llmRateLimitError`
qua flagd, hoặc gửi metadata `x-force-llm-error`. Đó là thay đổi ảnh hưởng người dùng thật
(`llmRateLimitError` gây lỗi cho ~50% request theo code), nên **chưa làm, chờ quyết định của change
owner**.

Đường đọc hiện được bảo đảm bằng unit test đã mutation-test: bỏ so `review_version` thì
`test_stale_version_falls_through_to_tier3` và `test_null_version_falls_through_to_tier3` đỏ.

Cho tới khi kiểm chứng xong, **không kết luận "Tier-2 đã hoạt động đầy đủ trên production"** — mới
đúng một nửa.
