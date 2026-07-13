# Hướng dẫn sử dụng repo `xbrain-learners`

Repo này chứa **tài liệu học tập, đề project và lịch học** của chương trình XBrain — gồm **Phase 1 (Foundation, W1–W7)** và **Phase 2 (Specialization, W8–W11)**. Mỗi tuần là một thư mục `Wx/` tự chứa đầy đủ mọi thứ bạn cần cho tuần đó.

> Mới vào? Đọc lần lượt: **`README.md`** (tổng quan chương trình) → **file này** (cách dùng repo) → mở thư mục tuần hiện tại.

---

## 1. Bản đồ tổng quan

```
xbrain-learners/
├── README.md              # Tổng quan chương trình + bảng tài liệu theo tuần
├── GUIDELINE.md           # File này — cách dùng repo
├── assets/                # Ảnh dùng chung (vd. cost-w5.png)
├── capstone-phase2/       # Đề + data + template cho capstone Phase 2
│   ├── W11_W12_capstone_announcement.md
│   ├── data/  reference/  templates/
│
├── W1 … W7/               # Phase 1 — Foundation (cả lớp học chung)
└── W8 … W11/              # Phase 2 — Specialization (2 track: CDO & AIO)
```

| Phase | Tuần | Đặc điểm |
|-------|------|----------|
| **Phase 1 — Foundation** | W1 → W7 | Nền tảng AWS. Cả lớp chung một lịch. W7 là **Capstone Hackathon 48h**. |
| **Phase 2 — Specialization** | W8 → W11 | Chia **2 track**: **CDO** (Cloud/DevOps) và **AIO** (AIOps). W11 = Final Projects. |

---

## 2. Cấu trúc một thư mục tuần `Wx/`

Không phải tuần nào cũng có đủ tất cả, nhưng quy ước chung như sau:

| Mục | Nội dung | Có ở |
|-----|----------|------|
| `schedule/README.md` | **Lịch học trong tuần** — nội dung theo ngày, hình thức (onsite/online), project | Mọi tuần |
| `Wx_learner_guide.md` | Hướng dẫn học viên: trọng tâm, cách chuẩn bị, deliverable | Phase 1 (W2–W7) |
| `Wx_project_announcement.md` | **Đề project / mission brief** của tuần | Phase 1 (W2–W7) |
| `*_vi.md` | Bản dịch tiếng Việt của learner guide / project announcement | W3–W6 |
| `Wx_phase2_announcement_cloud.md` | Đề/announcement của Phase 2 | W8–W10 |
| `slides/` | Slide bài giảng | Một số tuần |
| `recordings/` | Link/ghi chú bản ghi buổi học | Hầu hết tuần |
| `exercise_submission/README.md` | **Link form nộp bài tập** trong tuần | Phase 2 (W8…) |
| Khác | vd. `W7_hackathon_rules.txt`, `W7_cost_estimates.md`, `W7/starter_apps/`, `Jira_Working_Rules.md`, `W4/data_package/` | Theo tuần |

> **Quy ước tên file:** tiền tố `Wx_` theo số tuần; hậu tố `_vi` = bản tiếng Việt; `_announcement` / `_announcement_cloud` = đề bài; `_learner_guide` = hướng dẫn học.

---

## 3. Luồng sử dụng mỗi tuần (dành cho học viên)

1. **Mở lịch:** `Wx/schedule/README.md` — xem nội dung từng ngày, buổi nào **onsite**/**online**, và tóm tắt project.
2. **Đọc đề project:** `Wx_project_announcement.md` (hoặc `_vi`) / `Wx_phase2_announcement_cloud.md` — nắm rõ "done" chiều thứ 6 trông như thế nào.
3. **Đọc learner guide** (nếu có): cách chuẩn bị, mẹo hands-on, tiêu chí chấm.
4. **Học theo nội dung trong ngày** (Digital Course + Lab) như lịch ghi.
5. **Làm & nộp bài:** theo link form trong `exercise_submission/README.md` (Phase 2).
6. **Thuyết trình thứ 6** theo yêu cầu trong project announcement.

### Phase 1 vs Phase 2 — khác gì?
- **Phase 1 (W1–W7):** cả lớp chung một lịch, không chia track. Mỗi tuần xếp thêm một lớp lên cùng một ứng dụng (W1 dựng kiến trúc → W7 ship sản phẩm thật trong hackathon).
- **Phase 2 (W8–W11):** chia **CDO** và **AIO**. Trong `schedule/README.md` các tuần Phase 2, nội dung self-study/lab tách thành 2 cột **CDO | AIO**.

---

## 4. Hình thức học (onsite / online)

| Tuần | T2–T4 (Mon–Wed) | T5–T6 (Thu–Fri) |
|------|-----------------|-----------------|
| W1, W2 | ONSITE | ONSITE |
| W3 → W6 | ONLINE | ONSITE |
| W7 (Hackathon) | Build remote (tự quản 48h) | Demo Day **onsite** (báo cáo T6) |
| W8 → W11 | Theo lịch từng tuần trong `schedule/` | — |

> Link TEAMS và giờ cụ thể (khi có) nằm trong từng `schedule/README.md`.

---

## 5. Capstone & tài nguyên dùng chung

- **`capstone-phase2/`** — đề capstone (`W11_W12_capstone_announcement.md`), dữ liệu (`data/`), tài liệu tham khảo (`reference/`), template (`templates/`).
- **`W7/starter_apps/`** — 3 starter app chạy được ngay cho hackathon (StudyBot / BudgetBot / DocHub).
- **`assets/`** — ảnh dùng chung trong tài liệu.

---

## 6. Tra cứu nhanh theo tuần

| Tuần | Chủ đề | Lịch |
|------|--------|------|
| W1 | Propose & Map — kiến trúc 3-tier, on-prem → AWS | [W1/schedule](W1/schedule/README.md) |
| W2 | Storage & Identity — S3, EBS, IAM | [W2/schedule](W2/schedule/README.md) |
| W3 | Database & AI — RDS, DynamoDB, Bedrock, Lambda | [W3/schedule](W3/schedule/README.md) |
| W4 | Data Pipelines & ML | [W4/schedule](W4/schedule/README.md) |
| W5 | Networking — VPC, API Gateway, Serverless | [W5/schedule](W5/schedule/README.md) |
| W6 | Operations & Security — CloudWatch, cost, KMS | [W6/schedule](W6/schedule/README.md) |
| W7 | **Capstone Hackathon — Ship AI in 48h** | [W7/schedule](W7/schedule/README.md) |
| W8 | CDO: Terraform/K8s · AIO: Detection & Triage | [W8/schedule](W8/schedule/README.md) |
| W9 | CDO: GitOps/CI-CD · AIO: RCA & Smart Response | [W9/schedule](W9/schedule/README.md) |
| W10 | CDO: Reliability/Security · AIO: Auto-remediation | [W10/schedule](W10/schedule/README.md) |
| W11 | **Phase 2 Final Projects** | [W11/schedule](W11/schedule/README.md) |

---

## 7. Câu hỏi?

Liên hệ mentor nhóm hoặc đăng trong kênh Slack/Teams của chương trình.
