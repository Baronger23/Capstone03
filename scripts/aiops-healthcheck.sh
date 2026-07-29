#!/usr/bin/env bash
# Kiểm tra mọi phụ thuộc runtime của aiops-engine từ BÊN TRONG pod.
#
# Dùng để chạy TRƯỚC và SAU mỗi thay đổi động tới quyền/mạng của AIOps
# (IRSA, NetworkPolicy, secret, image). So hai lần chạy là biết ngay thứ gì gãy
# và gãy vì bước nào — thay vì đoán.
#
# Yêu cầu: kubectl đã trỏ đúng cluster (chạy scripts/kube-tunnel.sh trước).
# Toàn bộ lệnh là read-only, không mutate gì.
#
#   ./scripts/aiops-healthcheck.sh
#
# Cột giá trị mong đợi ở trạng thái khoẻ:
#   pod ready=true, restarts không tăng, /readyz=200, DNS=OK,
#   Prometheus=success, Jaeger=200, OpenSearch=200, S3=7 obj, Bedrock=OK,
#   Slack egress=400 (400 nghĩa là request TỚI được Slack, bị từ chối vì payload rỗng),
#   kube-apiserver trả về tên deployment.
#
# STS whoami cho biết pod đang dùng credential nào:
#   aio2-admin-team              -> vẫn chạy bằng static access key
#   techx-corp-tf3-aiops-engine  -> đã chuyển sang IRSA
set -uo pipefail
export MSYS_NO_PATHCONV=1

NS="${NS:-techx-tf3}"
DEPLOY="${DEPLOY:-deploy/aiops-engine}"

p() { printf '%-34s %s\n' "$1" "$2"; }
kx() { kubectl exec -n "$NS" "$DEPLOY" -- "$@" 2>/dev/null; }

echo "===== aiops healthcheck $(date '+%Y-%m-%d %H:%M:%S') ====="

p "pod ready" "$(kubectl get pod -n "$NS" -l app=aiops-engine \
    -o jsonpath='{.items[0].status.containerStatuses[0].ready}' 2>/dev/null)"
p "restarts" "$(kubectl get pod -n "$NS" -l app=aiops-engine \
    -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}' 2>/dev/null)"
p "/readyz" "$(kx python -c \
    "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/readyz',timeout=5).status)")"

p "DNS" "$(kx python -c \
    "import socket;socket.gethostbyname('prometheus.$NS.svc.cluster.local');print('OK')")"
p "Prometheus" "$(kx python -c \
    "import urllib.request,json;print(json.load(urllib.request.urlopen('http://prometheus.$NS.svc.cluster.local:9090/api/v1/query?query=up',timeout=8))['status'])")"
# Jaeger phục vụ dưới prefix /jaeger/ui — gọi root sẽ 404, không phải lỗi kết nối.
p "Jaeger" "$(kx python -c \
    "import urllib.request;print(urllib.request.urlopen('http://jaeger.$NS.svc.cluster.local:16686/jaeger/ui/api/services',timeout=8).status)")"
p "OpenSearch" "$(kx python -c \
    "import urllib.request;print(urllib.request.urlopen('http://opensearch.$NS.svc.cluster.local:9200/',timeout=8).status)")"

p "S3 list current/" "$(kx python -c \
    "import boto3,os;print(len(boto3.client('s3').list_objects_v2(Bucket=os.environ.get('AIOPS_S3_BUCKET','tf3-aiops-models-197826770971'),Prefix='current/').get('Contents',[])),'obj')")"
p "STS whoami" "$(kx python -c \
    "import boto3;print(boto3.client('sts').get_caller_identity()['Arn'].split('/')[-2] if ':assumed-role/' in boto3.client('sts').get_caller_identity()['Arn'] else boto3.client('sts').get_caller_identity()['Arn'].split('/')[-1])")"
p "Bedrock invoke" "$(kx python -c \
    "import boto3,json,os
c=boto3.client('bedrock-runtime',region_name=os.environ.get('BEDROCK_AWS_REGION','us-east-1'))
c.invoke_model(modelId='amazon.nova-lite-v1:0',body=json.dumps({'messages':[{'role':'user','content':[{'text':'hi'}]}],'inferenceConfig':{'maxTokens':5}}))
print('OK')")"
p "Slack egress" "$(kx python -c \
    "import os,requests;print(requests.post(os.environ['SLACK_WEBHOOK_URL'],json={},timeout=8).status_code,'(400=tới nơi)')")"
p "kube-apiserver" "$(kx kubectl get deploy -n "$NS" aiops-engine -o name 2>/dev/null || echo FAIL)"
