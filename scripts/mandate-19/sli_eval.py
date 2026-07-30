#!/usr/bin/env python3
"""Đo SLI theo cửa sổ chính xác từ Prometheus, dùng đúng query của slo-dashboard."""
import json, sys, urllib.parse, urllib.request, os

PROM = os.environ.get("PROM", "http://localhost:29090")
SP = os.path.dirname(os.path.abspath(__file__))
Q = json.load(open(os.path.join(SP, "sli_queries.json"), encoding="utf-8"))

def q_at(expr, at_epoch, window):
    e = expr.replace("WINDOW", window)
    url = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": e, "time": str(at_epoch)})
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.load(r)
    res = d.get("data", {}).get("result", [])
    if not res:
        return None
    try:
        return float(res[0]["value"][1])
    except (ValueError, KeyError, IndexError):
        return None

def evaluate(end_epoch, window):
    """end_epoch = cuối stage; window = toàn bộ độ dài stage (vd '5m')."""
    out = {}
    for name, expr in Q.items():
        out[name] = q_at(expr, end_epoch, window)
    # cổng SLO chính thức theo SLO.md
    g = {}
    bs, bp, cs, ks = out.get("browse_success"), out.get("browse_p95"), out.get("cart_success"), out.get("checkout_success")
    g["browse_success>=99.5%"] = (bs is not None and bs >= 0.995, None if bs is None else round(bs*100, 4))
    g["browse_p95<1000ms"]     = (bp is not None and bp < 1000.0, None if bp is None else round(bp, 1))
    g["cart_success>=99.5%"]   = (cs is not None and cs >= 0.995, None if cs is None else round(cs*100, 4))
    g["checkout_success>=99%"] = (ks is not None and ks >= 0.99,  None if ks is None else round(ks*100, 4))
    out["_gates"] = {k: {"pass": v[0], "value": v[1]} for k, v in g.items()}
    out["_verdict"] = "PASS" if all(v[0] for v in g.values()) else "FAIL"
    return out

if __name__ == "__main__":
    end = float(sys.argv[1]); win = sys.argv[2]
    r = evaluate(end, win)
    print(json.dumps(r, indent=1, ensure_ascii=False))
