locals {
  product_reviews_ai_endpoint_parameter_prefix = "/${var.cluster_name}/product-reviews/ai-endpoints"
  # Verified free with DescribeNetworkInterfaces on 2026-07-29. Static endpoint
  # ENI addresses let the staged NetworkPolicy use exact /32 peers before apply.
  product_reviews_ai_endpoint_subnets = {
    ap-southeast-1a = {
      cidr         = "10.0.0.0/20"
      subnet_id    = module.network.private_subnet_ids[index(var.azs, "ap-southeast-1a")]
      sts_ipv4     = "10.0.15.250"
      bedrock_ipv4 = "10.0.15.251"
    }
    ap-southeast-1b = {
      cidr         = "10.0.16.0/20"
      subnet_id    = module.network.private_subnet_ids[index(var.azs, "ap-southeast-1b")]
      sts_ipv4     = "10.0.31.250"
      bedrock_ipv4 = "10.0.31.251"
    }
    ap-southeast-1c = {
      cidr         = "10.0.32.0/20"
      subnet_id    = module.network.private_subnet_ids[index(var.azs, "ap-southeast-1c")]
      sts_ipv4     = "10.0.47.250"
      bedrock_ipv4 = "10.0.47.251"
    }
  }

  product_reviews_ai_inference_profile_ids = [
    "apac.amazon.nova-lite-v1:0",
    "apac.amazon.nova-micro-v1:0",
  ]
  product_reviews_ai_model_ids = [
    "amazon.nova-lite-v1:0",
    "amazon.nova-micro-v1:0",
  ]

  # Verified with GetInferenceProfile on 2026-07-29. IAM must authorize the
  # foundation model in every Region to which the APAC profile can route.
  product_reviews_ai_destination_regions = [
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-northeast-3",
    "ap-south-1",
    "ap-southeast-1",
    "ap-southeast-2",
  ]

  product_reviews_ai_inference_profile_arns = [
    for profile_id in local.product_reviews_ai_inference_profile_ids :
    "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.product_reviews_ai.account_id}:inference-profile/${profile_id}"
  ]
  product_reviews_ai_foundation_model_arns = flatten([
    for region in local.product_reviews_ai_destination_regions : [
      for model_id in local.product_reviews_ai_model_ids :
      "arn:aws:bedrock:${region}::foundation-model/${model_id}"
    ]
  ])
}

data "aws_caller_identity" "product_reviews_ai" {}

# Product Reviews gets dedicated endpoints instead of the shared endpoint SG,
# whose VPC-wide ingress would let unrelated workloads use these private paths.
resource "aws_security_group" "product_reviews_ai_endpoints" {
  name        = "${var.cluster_name}-product-reviews-ai-vpce"
  description = "HTTPS from EKS nodes to Product Reviews STS and Bedrock endpoints"
  vpc_id      = module.network.vpc_id

  # Interface endpoint security groups only need ingress. Return traffic for an
  # accepted connection is stateful, so no broad outbound rule is required.
  egress = []

  tags = {
    Name     = "${var.cluster_name}-product-reviews-ai-vpce"
    workload = "product-reviews"
  }
}

resource "aws_vpc_security_group_ingress_rule" "product_reviews_ai_endpoints_https" {
  security_group_id            = aws_security_group.product_reviews_ai_endpoints.id
  referenced_security_group_id = module.eks_platform.node_security_group_id
  description                  = "HTTPS from Product Reviews EKS nodes"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
}

data "aws_iam_policy_document" "product_reviews_sts_endpoint" {
  statement {
    sid     = "AllowProductReviewsWebIdentity"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    # AssumeRoleWithWebIdentity is unsigned, so the endpoint principal must be
    # wildcard. The exact role and its OIDC trust policy provide both boundaries.
    principals {
      type        = "*"
      identifiers = ["*"]
    }

    resources = [module.eks_platform.product_reviews_bedrock_role_arn]
  }
}

data "aws_iam_policy_document" "product_reviews_bedrock_runtime_endpoint" {
  statement {
    sid    = "InvokeProductReviewsInferenceProfiles"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]

    principals {
      type        = "AWS"
      identifiers = [module.eks_platform.product_reviews_bedrock_role_arn]
    }

    resources = local.product_reviews_ai_inference_profile_arns
  }

  statement {
    sid    = "InvokeProductReviewsModelsViaProfiles"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]

    principals {
      type        = "AWS"
      identifiers = [module.eks_platform.product_reviews_bedrock_role_arn]
    }

    resources = local.product_reviews_ai_foundation_model_arns

    condition {
      test     = "StringLike"
      variable = "bedrock:InferenceProfileArn"
      values   = local.product_reviews_ai_inference_profile_arns
    }
  }
}

resource "aws_vpc_endpoint" "product_reviews_sts" {
  vpc_id            = module.network.vpc_id
  service_name      = "com.amazonaws.${var.region}.sts"
  vpc_endpoint_type = "Interface"
  ip_address_type   = "ipv4"
  subnet_ids = [
    for endpoint_subnet in values(local.product_reviews_ai_endpoint_subnets) :
    endpoint_subnet.subnet_id
  ]
  security_group_ids = [aws_security_group.product_reviews_ai_endpoints.id]
  # Private DNS would redirect STS for every IRSA workload in the VPC through
  # this Product Reviews-only endpoint policy. The runtime instead receives the
  # endpoint-specific DNS name through SSM and External Secrets.
  private_dns_enabled = false
  policy              = data.aws_iam_policy_document.product_reviews_sts_endpoint.json

  dynamic "subnet_configuration" {
    for_each = local.product_reviews_ai_endpoint_subnets

    content {
      subnet_id = subnet_configuration.value.subnet_id
      ipv4      = subnet_configuration.value.sts_ipv4
    }
  }

  lifecycle {
    precondition {
      condition = alltrue([
        for az, endpoint_subnet in local.product_reviews_ai_endpoint_subnets :
        var.private_subnet_cidrs[index(var.azs, az)] == endpoint_subnet.cidr
      ])
      error_message = "Product Reviews endpoint IPs must stay inside the audited production subnet CIDRs."
    }
  }

  tags = {
    Name     = "${var.cluster_name}-product-reviews-sts"
    workload = "product-reviews"
  }
}

resource "aws_vpc_endpoint" "product_reviews_bedrock_runtime" {
  vpc_id            = module.network.vpc_id
  service_name      = "com.amazonaws.${var.region}.bedrock-runtime"
  vpc_endpoint_type = "Interface"
  ip_address_type   = "ipv4"
  subnet_ids = [
    for endpoint_subnet in values(local.product_reviews_ai_endpoint_subnets) :
    endpoint_subnet.subnet_id
  ]
  security_group_ids = [aws_security_group.product_reviews_ai_endpoints.id]
  # Shopping Copilot already calls the regional Bedrock hostname. Keep shared
  # DNS untouched and move only Product Reviews to this endpoint-specific DNS.
  private_dns_enabled = false
  policy              = data.aws_iam_policy_document.product_reviews_bedrock_runtime_endpoint.json

  dynamic "subnet_configuration" {
    for_each = local.product_reviews_ai_endpoint_subnets

    content {
      subnet_id = subnet_configuration.value.subnet_id
      ipv4      = subnet_configuration.value.bedrock_ipv4
    }
  }

  lifecycle {
    precondition {
      condition = alltrue([
        for az, endpoint_subnet in local.product_reviews_ai_endpoint_subnets :
        var.private_subnet_cidrs[index(var.azs, az)] == endpoint_subnet.cidr
      ])
      error_message = "Product Reviews endpoint IPs must stay inside the audited production subnet CIDRs."
    }
  }

  tags = {
    Name     = "${var.cluster_name}-product-reviews-bedrock-runtime"
    workload = "product-reviews"
  }
}

resource "aws_ssm_parameter" "product_reviews_sts_endpoint_url" {
  name        = "${local.product_reviews_ai_endpoint_parameter_prefix}/sts-url"
  description = "Explicit private STS endpoint URL for Product Reviews IRSA"
  type        = "SecureString"
  key_id      = module.eks_platform.eks_kms_key_arn
  value       = "https://${aws_vpc_endpoint.product_reviews_sts.dns_entry[0].dns_name}"

  tags = {
    Name     = "${var.cluster_name}-product-reviews-sts-url"
    workload = "product-reviews"
  }
}

resource "aws_ssm_parameter" "product_reviews_bedrock_runtime_endpoint_url" {
  name        = "${local.product_reviews_ai_endpoint_parameter_prefix}/bedrock-runtime-url"
  description = "Explicit private Bedrock Runtime endpoint URL for Product Reviews"
  type        = "SecureString"
  key_id      = module.eks_platform.eks_kms_key_arn
  value       = "https://${aws_vpc_endpoint.product_reviews_bedrock_runtime.dns_entry[0].dns_name}"

  tags = {
    Name     = "${var.cluster_name}-product-reviews-bedrock-runtime-url"
    workload = "product-reviews"
  }
}

data "aws_iam_policy_document" "external_secrets_product_reviews_ai_endpoints" {
  statement {
    sid    = "ReadProductReviewsAIEndpointParameters"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = [
      aws_ssm_parameter.product_reviews_sts_endpoint_url.arn,
      aws_ssm_parameter.product_reviews_bedrock_runtime_endpoint_url.arn,
    ]
  }

  statement {
    sid       = "DecryptProductReviewsAIEndpointParameters"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [module.eks_platform.eks_kms_key_arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.region}.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:PARAMETER_ARN"
      values = [
        aws_ssm_parameter.product_reviews_sts_endpoint_url.arn,
        aws_ssm_parameter.product_reviews_bedrock_runtime_endpoint_url.arn,
      ]
    }
  }
}

resource "aws_iam_role_policy" "external_secrets_product_reviews_ai_endpoints" {
  name   = "${var.cluster_name}-external-secrets-product-reviews-ai-endpoints"
  role   = module.eks_platform.external_secrets_role_name
  policy = data.aws_iam_policy_document.external_secrets_product_reviews_ai_endpoints.json
}
