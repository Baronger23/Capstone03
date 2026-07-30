output "vpc_id" {
  value = module.network.vpc_id
}

output "private_subnet_ids" {
  value = module.network.private_subnet_ids
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "cluster_name" {
  value = module.eks_platform.cluster_name
}

output "cluster_endpoint" {
  value = module.eks_platform.cluster_endpoint
}

output "cluster_oidc_provider_arn" {
  value = module.eks_platform.oidc_provider_arn
}

output "cluster_autoscaler_role_arn" {
  value = module.eks_platform.cluster_autoscaler_role_arn
}

output "karpenter_controller_role_arn" {
  value = module.eks_platform.karpenter_controller_role_arn
}

output "karpenter_node_role_name" {
  value = module.eks_platform.karpenter_node_role_name
}

output "karpenter_interruption_queue_name" {
  value = module.eks_platform.karpenter_interruption_queue_name
}

output "lb_controller_role_arn" {
  value = module.eks_platform.lb_controller_role_arn
}

output "external_secrets_role_arn" {
  value = module.eks_platform.external_secrets_role_arn
}

output "product_reviews_bedrock_role_arn" {
  value = module.eks_platform.product_reviews_bedrock_role_arn
}

output "product_reviews_sts_vpc_endpoint_id" {
  description = "Private STS endpoint used by Product Reviews IRSA."
  value       = aws_vpc_endpoint.product_reviews_sts.id
}

output "product_reviews_sts_vpc_endpoint_network_interface_ids" {
  description = "STS endpoint ENIs used to derive exact NetworkPolicy ipBlocks after rollout."
  value       = aws_vpc_endpoint.product_reviews_sts.network_interface_ids
}

output "product_reviews_sts_vpc_endpoint_dns_entries" {
  description = "Explicit private STS hostnames for the Product Reviews runtime migration."
  value       = aws_vpc_endpoint.product_reviews_sts.dns_entry
}

output "product_reviews_sts_vpc_endpoint_private_ips" {
  description = "Static STS endpoint ENI IPs allowed by the staged Product Reviews NetworkPolicy."
  value = [
    for endpoint_subnet in values(local.product_reviews_ai_endpoint_subnets) :
    endpoint_subnet.sts_ipv4
  ]
}

output "product_reviews_sts_endpoint_url_parameter_name" {
  description = "SSM parameter synchronized into the Product Reviews runtime Secret."
  value       = aws_ssm_parameter.product_reviews_sts_endpoint_url.name
}

output "product_reviews_bedrock_runtime_vpc_endpoint_id" {
  description = "Private Bedrock Runtime endpoint used by Product Reviews."
  value       = aws_vpc_endpoint.product_reviews_bedrock_runtime.id
}

output "product_reviews_bedrock_runtime_vpc_endpoint_network_interface_ids" {
  description = "Bedrock Runtime endpoint ENIs used to derive exact NetworkPolicy ipBlocks after rollout."
  value       = aws_vpc_endpoint.product_reviews_bedrock_runtime.network_interface_ids
}

output "product_reviews_bedrock_runtime_vpc_endpoint_dns_entries" {
  description = "Explicit private Bedrock Runtime hostnames for the Product Reviews runtime migration."
  value       = aws_vpc_endpoint.product_reviews_bedrock_runtime.dns_entry
}

output "product_reviews_bedrock_runtime_vpc_endpoint_private_ips" {
  description = "Static Bedrock Runtime endpoint ENI IPs allowed by the staged Product Reviews NetworkPolicy."
  value = [
    for endpoint_subnet in values(local.product_reviews_ai_endpoint_subnets) :
    endpoint_subnet.bedrock_ipv4
  ]
}

output "product_reviews_bedrock_runtime_endpoint_url_parameter_name" {
  description = "SSM parameter synchronized into the Product Reviews runtime Secret."
  value       = aws_ssm_parameter.product_reviews_bedrock_runtime_endpoint_url.name
}

output "flagd_sync_secret_name" {
  value = module.eks_platform.flagd_sync_secret_name
}

output "configure_kubectl" {
  description = "Run this to configure kubectl for the production cluster."
  value       = "aws eks update-kubeconfig --name ${module.eks_platform.cluster_name} --region ${var.region}"
}

output "bastion_instance_id" {
  description = "SSM Session Manager target for private EKS API access."
  value       = module.access.bastion_instance_id
}

output "ssm_tunnel_command" {
  description = "Open the private EKS API tunnel on localhost:8443."
  value       = module.access.ssm_tunnel_command
}

# ---------- Mandate #8: managed datastores ----------
output "rds_endpoint_address" {
  description = "RDS PostgreSQL host (Mandate #8). Null khi enable_managed_datastores=false."
  value       = module.datastores.rds_endpoint_address
}

output "rds_master_user_secret_arn" {
  description = "ARN secret master RDS tự quản (ESO đọc). Null khi tắt."
  value       = module.datastores.rds_master_user_secret_arn
}

output "elasticache_primary_endpoint" {
  description = "ElastiCache Valkey primary endpoint (Mandate #8). Null khi tắt."
  value       = module.datastores.elasticache_primary_endpoint
}

output "msk_bootstrap_brokers_sasl_scram" {
  description = "MSK bootstrap SASL/SCRAM (cổng 9096). Null khi tắt."
  value       = module.datastores.msk_bootstrap_brokers_sasl_scram
}

output "cloudfront_domain_name" {
  description = "Public HTTPS address for the storefront."
  value       = module.edge.cloudfront_domain_name
}

output "cloudfront_distribution_id" {
  description = "Primary CloudFront distribution ID."
  value       = module.edge.cloudfront_distribution_id
}

output "internal_alb_security_group_id" {
  description = "Terraform-managed security group for the internal frontend ALB."
  value       = module.edge.internal_alb_security_group_id
}

output "cloudfront_vpc_origin_id" {
  description = "CloudFront VPC Origin ID after the internal origin phase begins."
  value       = module.edge.cloudfront_vpc_origin_id
}

output "cloudflare_tunnel_token" {
  description = "REL-17: paste into the cloudflared Kubernetes Secret (never commit). Empty when enable_cloudflare_access = false."
  value       = try(module.cloudflare_access[0].tunnel_token, null)
  sensitive   = true
}

output "cloudflare_client_access_command" {
  description = "REL-17: what each team member runs locally instead of `aws ssm start-session`. Empty when enable_cloudflare_access = false."
  value       = try(module.cloudflare_access[0].client_access_command, null)
}

output "cloudflare_ui_urls" {
  description = "REL-17: direct browser URLs for Grafana/Jaeger/ArgoCD, no kubectl/IAM needed. Empty when enable_cloudflare_access = false."
  value       = var.enable_cloudflare_access ? { for k, v in module.cloudflare_access[0].internal_ui_routes : k => "https://${v.hostname}" } : null
}

output "audit_detection_trails" {
  description = "Mandate 11 CloudTrail trail names."
  value = {
    ap_southeast_1 = module.audit_detection_ap_southeast_1.trail_name
    us_east_1      = module.audit_detection_us_east_1.trail_name
  }
}

output "audit_detection_sns_topics" {
  description = "Mandate 11 SNS topics used for audit alerts."
  value = {
    ap_southeast_1 = module.audit_detection_ap_southeast_1.sns_topic_arn
    us_east_1      = module.audit_detection_us_east_1.sns_topic_arn
  }
}
