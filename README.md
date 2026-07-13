# XBrain Learners

Weekly learning guides and project announcements for the XBrain AWS DevOps/CloudOps Foundation Program.

## Program Overview

- **Duration:** 7 weeks (Phase 1: Foundation)
- **Focus:** AWS cloud architecture, infrastructure, and operations
- **Format:** Mon-Wed courses + labs, Thu consolidation, Fri group presentations

## Weekly Materials

| Week | Theme | Guide | Announcement | Recordings | Slides |
|------|-------|-------|--------------|------------|--------|
| W1 | Propose & Map — Architecture diagram, on-prem to AWS mapping | — | — | — | — |
| W2 | Storage & Identity — S3, EBS, IAM, VPC | [Learner Guide](W2/W2_learner_guide.md) | [Project Announcement](W2/W2_project_announcement.md) | [Recordings](W2/recordings/) | [Slides](W2/slides/) |
| W3 | Database & AI — RDS, DynamoDB, Bedrock | Coming soon | Coming soon | [Recordings](W3/recordings/) | [Slides](W3/slides/) |
| W4 | Data Pipelines — ETL, analytics, ML pipelines | Coming soon | Coming soon | [Recordings](W4/recordings/) | [Slides](W4/slides/) |
| W5 | Networking — VPC hardening, API Gateway, WAF | Coming soon | Coming soon | — | — |
| W6 | Operations & Security — CloudWatch, auto-scaling, KMS | Coming soon | Coming soon | — | — |
| W7 | **Capstone Hackathon — Ship Production-Ready AI in 48 Hours** | [Learner Guide](W7/W7_learner_guide.md) | [Project Announcement](W7/W7_project_announcement.md) | [Recordings](W7/recordings/) | [Slides](W7/slides/) |

## How to Use

- **Learner Guide**: Read before each week starts. Contains focus areas, hands-on tips, deliverables, and how to prepare for Friday presentations.
- **Project Announcement**: The mission brief for the week. Describes what "done" looks like on Friday and how this week connects to the final W7 demo.

## W7 Capstone Hackathon — extra materials

W7 is a 48-hour hackathon and ships with more student-facing material than other weeks:

- [`W7/W7_project_announcement.md`](W7/W7_project_announcement.md) — full project brief (English)
- [`W7/W7_learner_guide.md`](W7/W7_learner_guide.md) — day-by-day guide (Day 1/2 = suggested rhythm, not contract)
- [`W7/W7_hackathon_rules.txt`](W7/W7_hackathon_rules.txt) — short Vietnamese rules sheet
- [`W7/W7_cost_estimates.md`](W7/W7_cost_estimates.md) — reference cost estimates for 3 starter projects in `ap-southeast-1`
- [`W7/starter_apps/`](W7/starter_apps/) — 3 ready-to-run source codes (pick one or build your own):
  - **StudyBot** (EduTech, RAG over uploaded notes)
  - **BudgetBot** (FinTech, direct LLM transaction classification)
  - **DocHub** (ProductivityTech, multi-tenant RAG)

Each starter app runs locally with zero AWS credentials (SQLite + filesystem + local AI stub) and switches to AWS by flipping env vars. Sample data is sourced from HuggingFace (`wikimedia/wikipedia` for StudyBot, `coastalcph/lex_glue` LEDGAR for DocHub) — citations + licenses in each app's `sample_data/SOURCES.md`. BudgetBot ships with synthetic Vietnamese transactions (CC0).

## Evaluation

You are evaluated on:

- **Group presentation** — Your team's architecture quality, AWS design, and deployment demo
- **Individual QnA** — Your ability to explain decisions when called on randomly during presentations
- **Daily checkpoints** — Kahoot and other games during Mon-Wed
- **Peer evaluation** — Your teammates rate your contribution
- **Classroom participation** — Daily engagement tracked

## Questions?

Reach out to your group mentor or post in the training Slack channel.
