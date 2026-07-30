# Shopping Copilot (AIO02 service, deployed the TF3-compliant way by CDO02).
#
# Dedicated IRSA role so the copilot pod can call Bedrock WITHOUT granting Bedrock to the
# shared workload service account - same posture as product-reviews-bedrock.tf. Scoped to
# the exact model / guardrail / knowledge-base / bucket the DEPLOYMENT-SPEC declares; no
# Resource:"*" (the spec's draft policy used "*", we tighten it here).
#
# Model/guardrail/KB IDs come from AIO02's contract (shopping-copilot/contracts/
# DEPLOYMENT-SPEC.md, v1.0.0). If AIO02 rotates the guardrail out of DRAFT or moves the KB,
# update the locals below - these are the only place the IDs live on the infra side.

locals {
  shopping_copilot_namespace       = "techx-tf3"
  shopping_copilot_service_account = "shopping-copilot-sa"

  # Runtime LLM: APAC cross-region inference profile for Nova Lite (ap-southeast-1).
  copilot_bedrock_region       = "ap-southeast-1"
  copilot_inference_profile_id = "apac.amazon.nova-lite-v1:0"
  copilot_foundation_model_id  = "amazon.nova-lite-v1:0"

  # Mandate-23 GenAI semantic cache (added in the AIE2 copilot update): on a Tier-1 miss the
  # app embeds the query with Titan Text Embeddings V2 and compares vectors. TITAN_SEMANTIC_CACHE
  # defaults to "true" in the code, so without this the cache calls InvokeModel on Titan and gets
  # AccessDenied on every miss - the cache silently never works. Embeddings only, no generation.
  copilot_embed_model_id = "amazon.titan-embed-text-v2:0"

  # Guardrail AND the Knowledge Base both live in us-east-1 (verified 2026-07-27:
  # KB UCTITOWFHE / techx-products-kb-v2 is ACTIVE in us-east-1, not ap-southeast-1). The
  # app's kb_client defaults BEDROCK_KB_REGION to us-east-1, so Retrieve() targets us-east-1.
  copilot_guardrail_region = "us-east-1"
  copilot_guardrail_id     = "3ab7r29x59x4"
  # 3ab7r29x59x4 is a CROSS-REGION guardrail: ApplyGuardrail resolves it through a
  # cross-region guardrail-profile (us.guardrail.v1:0), and IAM authorizes against that
  # profile ARN - not just the guardrail ARN. Without it, ApplyGuardrail is AccessDenied and
  # the app fails open (L2 content filter silently bypassed).
  copilot_guardrail_profile = "us.guardrail.v1:0"
  copilot_kb_id             = "UCTITOWFHE"
  copilot_kb_region         = "us-east-1"

  copilot_products_bucket = "techx-products-catalog-2026"
}

data "aws_iam_policy_document" "shopping_copilot_bedrock_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${module.eks.oidc_provider}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${module.eks.oidc_provider}:sub"
      values   = ["system:serviceaccount:${local.shopping_copilot_namespace}:${local.shopping_copilot_service_account}"]
    }
  }
}

resource "aws_iam_role" "shopping_copilot_bedrock" {
  name               = "${var.cluster_name}-shopping-copilot-bedrock"
  assume_role_policy = data.aws_iam_policy_document.shopping_copilot_bedrock_assume_role.json
}

resource "aws_iam_role_policy" "shopping_copilot_bedrock" {
  name = "${var.cluster_name}-shopping-copilot-bedrock"
  role = aws_iam_role.shopping_copilot_bedrock.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeApprovedBedrockModels"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        # Cross-region inference profile + the underlying foundation model in every
        # region the APAC profile can route to (region wildcard on the account-less
        # foundation-model ARN is the documented pattern for inference profiles).
        Resource = [
          "arn:aws:bedrock:${local.copilot_bedrock_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${local.copilot_inference_profile_id}",
          "arn:aws:bedrock:*::foundation-model/${local.copilot_foundation_model_id}",
          # Titan embeddings for the semantic cache (embed-only; not a generation model).
          "arn:aws:bedrock:*::foundation-model/${local.copilot_embed_model_id}",
        ]
      },
      {
        Sid    = "ApplyBedrockGuardrail"
        Effect = "Allow"
        Action = ["bedrock:ApplyGuardrail"]
        Resource = [
          "arn:aws:bedrock:${local.copilot_guardrail_region}:${data.aws_caller_identity.current.account_id}:guardrail/${local.copilot_guardrail_id}",
          "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:guardrail-profile/${local.copilot_guardrail_profile}",
        ]
      },
      {
        Sid      = "RetrieveFromKnowledgeBase"
        Effect   = "Allow"
        Action   = ["bedrock:Retrieve"]
        Resource = ["arn:aws:bedrock:${local.copilot_kb_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/${local.copilot_kb_id}"]
      },
      {
        # Read-only: copilot reads product data for the KB / catalog fallback. PutObject
        # from the spec is intentionally dropped - KB ingestion is a separate sync job,
        # not the request-path pod. Re-add only if AIO02 confirms the runtime writes.
        Sid    = "ReadProductCatalogBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
        ]
        Resource = [
          "arn:aws:s3:::${local.copilot_products_bucket}",
          "arn:aws:s3:::${local.copilot_products_bucket}/*",
        ]
      },
    ]
  })
}
# Note: data.aws_caller_identity.current is declared in main.tf (reused here).
