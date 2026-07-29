// IRSA cho AIOps (AIO02): hai role tách biệt cho engine và trainer.
//
// Vì sao cần: pod aiops-engine đang lấy credential AWS từ static access key của IAM user
// `aio2-admin-team` (AdministratorAccess) nhét trong Secret. ServiceAccount có annotation
// trỏ tới role `tf3-aiops-engine-irsa-role` nhưng role đó KHÔNG tồn tại
// (`aws iam get-role` trả NoSuchEntity, kiểm chứng 2026-07-28) - annotation chỉ là trang trí.
//
// Vì sao tách hai role thay vì dùng chung:
//   - trainer KHÔNG cần Bedrock (nó chỉ query Prometheus rồi ghi model lên S3);
//   - trainer KHÔNG cần ghi prefix topology/;
//   - hai role cho hai audit trail riêng trong CloudTrail.
//
// Quyền dưới đây suy ra từ code thật, không phải đoán:
//   anomaly_detector.py       list_objects_v2 + download_file  -> engine ĐỌC current/
//   main.py:/topology/rebuild -> rebuild_topology_from_jaeger.py put_object topology/services.json
//   main.py:/retrain          -> import train_anomaly_model_eks; trainer.main() chạy IN-PROCESS
//                                => engine cũng cần quyền GHI như trainer, nếu không endpoint gãy
//   train_anomaly_model_eks.py head_bucket + upload_file -> cần ListBucket + PutObject

locals {
  aiops_namespace      = "techx-tf3"
  aiops_engine_sa      = "aiops-engine"
  aiops_trainer_sa     = "aiops-trainer"
  aiops_models_bucket  = "tf3-aiops-models-197826770971"
  aiops_bedrock_region = "us-east-1"
  // nova-lite/nova-micro: chẩn đoán RCA và judge (BEDROCK_MODEL_ID).
  // titan-embed-*: llm_diagnostician.py dùng để nhúng vector cho RAG cục bộ; nó thử
  // lần lượt nhiều model embedding nên phải cấp cả hai, thiếu là "All embedding
  // models failed" và phần tra playbook chết im lặng.
  aiops_bedrock_model_ids = [
    "amazon.nova-lite-v1:0",
    "amazon.nova-micro-v1:0",
    "amazon.titan-embed-text-v1",
    "amazon.titan-embed-text-v2:0",
  ]
  aiops_knowledge_base_arn = "arn:aws:bedrock:us-east-1:197826770971:knowledge-base/GH3FUCYVOJ"
}

// ---------------------------------------------------------------------------
// Engine
// ---------------------------------------------------------------------------

data "aws_iam_policy_document" "aiops_engine_assume_role" {
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
      values   = ["system:serviceaccount:${local.aiops_namespace}:${local.aiops_engine_sa}"]
    }
  }
}

resource "aws_iam_role" "aiops_engine" {
  name               = "${var.cluster_name}-aiops-engine"
  assume_role_policy = data.aws_iam_policy_document.aiops_engine_assume_role.json
}

resource "aws_iam_role_policy" "aiops_engine" {
  name = "${var.cluster_name}-aiops-engine"
  role = aws_iam_role.aiops_engine.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        // head_bucket + list_objects_v2(Prefix="current/") cần quyền ở cấp bucket.
        Sid      = "ListModelBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = ["arn:aws:s3:::${local.aiops_models_bucket}"]
      },
      {
        Sid    = "ReadModelArtifacts"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "arn:aws:s3:::${local.aiops_models_bucket}/active_manifest.json",
          "arn:aws:s3:::${local.aiops_models_bucket}/current/*",
          "arn:aws:s3:::${local.aiops_models_bucket}/archive/*",
          "arn:aws:s3:::${local.aiops_models_bucket}/topology/*",
        ]
      },
      {
        // Ghi: /retrain chạy trainer in-process (current/, archive/, active_manifest.json)
        // và /topology/rebuild ghi topology/services.json.
        Sid    = "WriteModelAndTopologyArtifacts"
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = [
          "arn:aws:s3:::${local.aiops_models_bucket}/active_manifest.json",
          "arn:aws:s3:::${local.aiops_models_bucket}/current/*",
          "arn:aws:s3:::${local.aiops_models_bucket}/archive/*",
          "arn:aws:s3:::${local.aiops_models_bucket}/topology/*",
        ]
      },
      {
        Sid    = "InvokeApprovedBedrockModels"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = [
          for model_id in local.aiops_bedrock_model_ids :
          "arn:aws:bedrock:${local.aiops_bedrock_region}::foundation-model/${model_id}"
        ]
      },
      {
        // RAG: llm_diagnostician.py gọi bedrock-agent-runtime Retrieve trên KB này.
        // KB nằm ở us-east-1 (ap-southeast-1 không có KB nào).
        Sid    = "RetrieveFromPlaybookKnowledgeBase"
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate",
        ]
        Resource = [local.aiops_knowledge_base_arn]
      },
    ]
  })
}

// ---------------------------------------------------------------------------
// Trainer (CronJob aiops-anomaly-training)
// ---------------------------------------------------------------------------
//
// Hẹp hơn engine: không Bedrock, không ghi topology/.
// CronJob hiện KHÔNG khai serviceAccountName nên đang chạy bằng SA `default`.
// Phải tạo ServiceAccount `aiops-trainer` trong GitOps và trỏ CronJob vào nó thì
// role này mới có tác dụng.

data "aws_iam_policy_document" "aiops_trainer_assume_role" {
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
      values   = ["system:serviceaccount:${local.aiops_namespace}:${local.aiops_trainer_sa}"]
    }
  }
}

resource "aws_iam_role" "aiops_trainer" {
  name               = "${var.cluster_name}-aiops-trainer"
  assume_role_policy = data.aws_iam_policy_document.aiops_trainer_assume_role.json
}

resource "aws_iam_role_policy" "aiops_trainer" {
  name = "${var.cluster_name}-aiops-trainer"
  role = aws_iam_role.aiops_trainer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        // train_anomaly_model_eks.py gọi head_bucket trước khi upload.
        Sid      = "ListModelBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = ["arn:aws:s3:::${local.aiops_models_bucket}"]
      },
      {
        Sid    = "ReadModelArtifacts"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "arn:aws:s3:::${local.aiops_models_bucket}/active_manifest.json",
          "arn:aws:s3:::${local.aiops_models_bucket}/current/*",
        ]
      },
      {
        Sid    = "WriteModelArtifacts"
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = [
          "arn:aws:s3:::${local.aiops_models_bucket}/active_manifest.json",
          "arn:aws:s3:::${local.aiops_models_bucket}/current/*",
          "arn:aws:s3:::${local.aiops_models_bucket}/archive/*",
        ]
      },
    ]
  })
}

output "aiops_engine_irsa_role_arn" {
  description = "ARN role IRSA cho ServiceAccount techx-tf3:aiops-engine."
  value       = aws_iam_role.aiops_engine.arn
}

output "aiops_trainer_irsa_role_arn" {
  description = "ARN role IRSA cho ServiceAccount techx-tf3:aiops-trainer (CronJob training)."
  value       = aws_iam_role.aiops_trainer.arn
}
