locals {
  product_reviews_namespace       = "techx-tf3"
  product_reviews_service_account = "product-reviews-bedrock"
  bedrock_legacy_region           = "us-east-1"
  bedrock_inference_region        = "ap-southeast-1"
  bedrock_summary_model_id        = "amazon.nova-lite-v1:0"
  bedrock_judge_model_id          = "amazon.nova-micro-v1:0"
  bedrock_inference_profile_ids = [
    "apac.amazon.nova-lite-v1:0",
    "apac.amazon.nova-micro-v1:0",
  ]
  bedrock_inference_destination_regions = [
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-northeast-3",
    "ap-south-1",
    "ap-southeast-1",
    "ap-southeast-2",
  ]
  bedrock_inference_profile_arns = [
    for profile_id in local.bedrock_inference_profile_ids :
    "arn:aws:bedrock:${local.bedrock_inference_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${profile_id}"
  ]
  bedrock_inference_model_arns = flatten([
    for region in local.bedrock_inference_destination_regions : [
      for model_id in [local.bedrock_summary_model_id, local.bedrock_judge_model_id] :
      "arn:aws:bedrock:${region}::foundation-model/${model_id}"
    ]
  ])
}

data "aws_iam_policy_document" "product_reviews_bedrock_assume_role" {
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
      values   = ["system:serviceaccount:${local.product_reviews_namespace}:${local.product_reviews_service_account}"]
    }
  }
}

resource "aws_iam_role" "product_reviews_bedrock" {
  name               = "${var.cluster_name}-product-reviews-bedrock"
  assume_role_policy = data.aws_iam_policy_document.product_reviews_bedrock_assume_role.json
}

resource "aws_iam_role_policy" "product_reviews_bedrock" {
  name = "${var.cluster_name}-product-reviews-bedrock"
  role = aws_iam_role.product_reviews_bedrock.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeProductReviewsInferenceProfiles"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = local.bedrock_inference_profile_arns
      },
      {
        Sid    = "InvokeProductReviewsModelsViaProfiles"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = local.bedrock_inference_model_arns
        Condition = {
          StringLike = {
            "bedrock:InferenceProfileArn" = local.bedrock_inference_profile_arns
          }
        }
      },
      {
        # Keep the old ReplicaSet and rollback path working while the APAC
        # profile and private endpoints are being proven in runtime.
        Sid    = "InvokeLegacyUsEast1ModelsDuringMigration"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = [
          "arn:aws:bedrock:${local.bedrock_legacy_region}::foundation-model/${local.bedrock_summary_model_id}",
          "arn:aws:bedrock:${local.bedrock_legacy_region}::foundation-model/${local.bedrock_judge_model_id}",
        ]
      },
    ]
  })
}
