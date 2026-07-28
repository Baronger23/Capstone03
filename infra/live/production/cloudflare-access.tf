# REL-17 - see docs/backlog/cdo02-reliability-cost-backlog.md and
# docs/runbooks/cloudflare-zero-trust-access.md. Inert by default (count = 0) until
# enable_cloudflare_access = true and the cloudflare_* variables are filled in.
module "cloudflare_access" {
  source = "../../modules/cloudflare-access"
  count  = var.enable_cloudflare_access ? 1 : 0

  account_id           = var.cloudflare_account_id
  zone_id              = var.cloudflare_zone_id
  zone_name            = var.cloudflare_zone_name
  tunnel_hostname      = var.cloudflare_tunnel_hostname
  eks_cluster_endpoint = module.eks_platform.cluster_endpoint
  allowed_email_domain = var.cloudflare_allowed_email_domain
  allowed_emails       = var.cloudflare_allowed_emails

  # Browser UIs go straight to their in-cluster Service - no kubectl/EKS-API/AWS IAM in
  # this path. argocd-server only serves TLS with its own self-signed cert on :443, so
  # that one route needs no_tls_verify (the leg from cloudflared to the Service stays
  # inside the cluster network either way - Cloudflare Access is the real auth boundary).
  internal_ui_routes = var.enable_cloudflare_access ? {
    grafana = {
      hostname = "grafana.${var.cloudflare_zone_name}"
      service  = "http://grafana.techx-tf3.svc.cluster.local:80"
    }
    jaeger = {
      hostname = "jaeger.${var.cloudflare_zone_name}"
      service  = "http://jaeger.techx-tf3.svc.cluster.local:16686"
    }
    argocd = {
      hostname      = "argocd.${var.cloudflare_zone_name}"
      service       = "https://argocd-server.argocd.svc.cluster.local:443"
      no_tls_verify = true
    }
    # Shopping Copilot UI (/chatbot) behind SSO - customer-facing chat is NOT exposed on
    # the public storefront yet; team/mentor reach it through Cloudflare Access, same auth
    # boundary as the other internal UIs. Plain HTTP inside the cluster; Access is the gate.
    copilot = {
      hostname = "copilot.${var.cloudflare_zone_name}"
      service  = "http://shopping-copilot.techx-tf3.svc.cluster.local:8001"
    }
  } : {}

  # Fence off the copilot's unauthenticated introspection endpoints at the edge: /debug/*
  # (dumps every user's session/cache) and /docs (Swagger). Returns 404 before reaching the
  # pod, even for SSO users. Full in-app disable still tracked as an AIO02 hardening ask.
  blocked_paths = var.enable_cloudflare_access ? [
    {
      hostname = "copilot.${var.cloudflare_zone_name}"
      path     = "^/(debug|docs)"
    },
  ] : []
}
