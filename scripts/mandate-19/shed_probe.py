import sys, collections, concurrent.futures as cf, requests

TARGET = sys.argv[1]           # e.g. 10.0.28.9:8080
N      = int(sys.argv[2])      # total requests
CONC   = int(sys.argv[3])
PATH   = sys.argv[4]

url = f"http://{TARGET}{PATH}"
s = requests.Session()
codes = collections.Counter()
shed_hdr = {}

def one(_):
    try:
        r = s.get(url, timeout=10, allow_redirects=False)
        return r.status_code, dict(r.headers)
    except Exception as e:
        return type(e).__name__, {}

with cf.ThreadPoolExecutor(max_workers=CONC) as ex:
    for code, hdrs in ex.map(one, range(N)):
        codes[code] += 1
        if code == 429 and not shed_hdr:
            shed_hdr = hdrs

print(f"TARGET={url} N={N} CONC={CONC}")
for c, n in sorted(codes.items(), key=lambda kv: str(kv[0])):
    print(f"  {c}: {n}")
if shed_hdr:
    print("  --- headers on a 429 sample ---")
    for k in ("x-techx-load-shed", "x-envoy-ratelimited", "content-length", "server"):
        if k in shed_hdr:
            print(f"  {k}: {shed_hdr[k]}")
else:
    print("  (no 429 captured)")
