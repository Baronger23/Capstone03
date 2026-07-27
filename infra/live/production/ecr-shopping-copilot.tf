# Shopping Copilot image repository (AIO02 service, PM-101-compliant).
#
# Separate ECR repo from techx-corp because the copilot is a standalone image built by its
# own gated workflow (.github/workflows/build-push-copilot.yml), not part of the techx-corp
# docker-compose bake. Same posture as techx-corp: IMMUTABLE tags (digest-pinned deploys),
# scan-on-push, keep the 10 newest builds.
#
# ⚠️ IMPORT BEFORE APPLY: AIO02 already pushed images to this repo out of band, so it very
# likely pre-exists. Import it into state first, otherwise apply fails on create-existing:
#
#   terraform import aws_ecr_repository.shopping_copilot shopping-copilot
#
# If it was created MUTABLE, this resource flips it to IMMUTABLE on the next apply (existing
# tags stay; only future overwrites are blocked - which is the point).

resource "aws_ecr_repository" "shopping_copilot" {
  name                 = "shopping-copilot"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ecr_lifecycle_policy" "shopping_copilot" {
  repository = aws_ecr_repository.shopping_copilot.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the 10 newest tagged builds"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["*"]
          countType      = "imageCountMoreThan"
          countNumber    = 10
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Expire untagged build artifacts older than 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      },
    ]
  })
}
