#!/usr/bin/env bash
# run_stage.sh <ARM> <TOTAL_USERS> <TOTAL_SECONDS> <MEASURE_WINDOW_SEC>
# Chạy locust trên toàn bộ bench pod, đo SLI trên cửa sổ cuối (bỏ ramp).
set -uo pipefail
SP="$(cd "$(dirname "$0")" && pwd)"
export KUBECONFIG=$SP/kubeconfig-admin.yaml
ARM=$1; USERS=$2; DUR=$3; WIN=${4:-300}
NS=techx-tf3
OUT="$SP/runs/$ARM/u$USERS"; mkdir -p "$OUT"

PODS=($(kubectl -n $NS get pod -l techx.io/purpose=mandate-19-benchmark -o jsonpath='{range .items[*]}{.metadata.name}{" "}{end}'))
N=${#PODS[@]}
PER=$(( USERS / N ))
SPAWN=$(( PER / 5 )); [ $SPAWN -lt 1 ] && SPAWN=1

echo "[$(date -u +%H:%M:%S)] ARM=$ARM users=$USERS ($N pods x $PER) dur=${DUR}s win=${WIN}s"
T0=$(date +%s)

for p in "${PODS[@]}"; do
  kubectl -n $NS exec "$p" -- sh -c \
    "cd /usr/src/app && rm -f /tmp/st_* && nohup locust -f locustfile.py --headless \
     --host http://frontend-proxy:8080 -u $PER -r $SPAWN -t ${DUR}s --only-summary \
     --csv /tmp/st > /tmp/st.log 2>&1 & echo started" >/dev/null 2>&1 &
done
wait

# chờ hết stage
sleep $(( DUR + 15 ))
T1=$(date +%s)
MEAS_END=$T1

# snapshot hạ tầng
# SUT = node managed (KHÔNG có label techx.io/workload=elastic). Generator bị ghim
# vào tầng elastic nên không nằm trong mẫu số density. Trần cố định-node đòi
# sut_node_set_sha256 GIỐNG NHAU ở mọi stage của cả hai arm.
{
  echo "### sut_nodes (managed, = hệ dưới đo)"
  kubectl get nodes -l '!techx.io/workload' -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | sort
  echo "### sut_node_count"
  kubectl get nodes -l '!techx.io/workload' --no-headers | wc -l
  echo "### sut_node_set_sha256"
  kubectl get nodes -l '!techx.io/workload' -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | sort | sha256sum
  echo "### elastic_nodes (generator + burst, LOẠI khỏi mẫu số)"
  kubectl get nodes -l techx.io/workload=elastic -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | sort
  echo "### elastic_node_count"
  kubectl get nodes -l techx.io/workload=elastic --no-headers 2>/dev/null | wc -l
  echo "### sut_pods_on_elastic (burst — nếu >0 thì đã vượt trần cố định-node)"
  kubectl -n $NS get pods -o json | python3 -c "
import json,sys,subprocess
pods=json.load(sys.stdin)['items']
el=set(subprocess.run(['kubectl','get','nodes','-l','techx.io/workload=elastic','-o','jsonpath={range .items[*]}{.metadata.name} {end}'],capture_output=True,text=True).stdout.split())
n=[p['metadata']['name'] for p in pods
   if p['spec'].get('nodeName') in el
   and p['metadata'].get('labels',{}).get('techx.io/purpose')!='mandate-19-benchmark']
print(len(n)); [print('   ',x) for x in sorted(n)]
"
  echo "### hpa"; kubectl -n $NS get hpa
  echo "### top_nodes"; kubectl top nodes
  echo "### bench_cpu (phải KHÔNG chạm limit, không thì đo trần của generator)"
  kubectl -n $NS top pod -l techx.io/purpose=mandate-19-benchmark --no-headers
} > "$OUT/infra.txt" 2>&1

# gom CSV locust
TOT_RPS=0
for p in "${PODS[@]}"; do
  kubectl -n $NS exec "$p" -- sh -c 'cat /tmp/st_stats.csv 2>/dev/null' > "$OUT/locust_$p.csv" 2>/dev/null
done
python3 - "$OUT" <<'PY' > "$OUT/locust_agg.json"
import csv,glob,json,sys,os
o=sys.argv[1]; rps=0; reqs=0; fails=0; rows=[]
for f in glob.glob(os.path.join(o,'locust_*.csv')):
    try:
        for r in csv.DictReader(open(f)):
            if r.get('Name')=='Aggregated':
                rps+=float(r['Requests/s']); reqs+=int(r['Request Count']); fails+=int(r['Failure Count'])
                rows.append({'pod':os.path.basename(f),'rps':float(r['Requests/s']),'reqs':int(r['Request Count']),'fails':int(r['Failure Count']),'p95':r.get('95%'),'p99':r.get('99%')})
    except Exception as e: rows.append({'pod':f,'err':str(e)})
json.dump({'offered_rps_sum':round(rps,2),'requests':reqs,'failures':fails,
           'failure_pct':round(100*fails/reqs,4) if reqs else None,'per_pod':rows},
          open(os.path.join(o,'_tmp.json'),'w'),indent=1)
print(json.dumps({'offered_rps_sum':round(rps,2),'requests':reqs,'failures':fails,
  'failure_pct':round(100*fails/reqs,4) if reqs else None,'per_pod':rows},indent=1))
PY

# đo SLI cửa sổ chính xác
cd "$SP" && PROM=http://localhost:29090 python3 sli_eval.py "$MEAS_END" "$((WIN/60))m" > "$OUT/sli.json" 2>&1

echo "--- SLI ($ARM u$USERS, window ${WIN}s ending $(date -u -d @$MEAS_END +%H:%M:%SZ)) ---"
python3 -c "
import json;d=json.load(open('$OUT/sli.json'))
print(' verdict:',d['_verdict'])
for k,v in d['_gates'].items(): print(f\"  {'OK ' if v['pass'] else 'FAIL'} {k} = {v['value']}\")
print(' frontend_rps:',round(d.get('frontend_total_rate') or 0,2),' browse_rps:',round(d.get('browse_rate') or 0,2),' checkout_rps:',round(d.get('checkout_rate') or 0,2))
print(' checkout p95/p99 ms:',round(d.get('checkout_p95') or 0,1),'/',round(d.get('checkout_p99') or 0,1))
"
echo "T0=$T0 T1=$T1" > "$OUT/window.txt"
