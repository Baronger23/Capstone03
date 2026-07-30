from pathlib import Path
import json
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]
HPA = ROOT / "gitops/infrastructure/hpa-hotpath.yaml"
FRONTEND_HEADLESS_SERVICE = (
    ROOT / "gitops/infrastructure/frontend-headless-service.yaml"
)
VALUES = ROOT / "phase3 - information/deploy/values-prod.yaml"
CHART_VALUES = ROOT / "phase3 - information/techx-corp-chart/values.yaml"
ENVOY = (
    ROOT
    / "phase3 - information/techx-corp-platform/src/frontend-proxy/envoy.tmpl.yaml"
)
ENVOY_DOCKERFILE = (
    ROOT
    / "phase3 - information/techx-corp-platform/src/frontend-proxy/Dockerfile"
)
ENVOY_ENTRYPOINT = (
    ROOT
    / "phase3 - information/techx-corp-platform/src/frontend-proxy/entrypoint.sh"
)
PROFILE = (
    ROOT
    / "phase3 - information/techx-corp-platform/src/load-generator/mandate19_locustfile.py"
)
DASHBOARD = (
    ROOT
    / "phase3 - information/techx-corp-chart/grafana/provisioning/dashboards/slo-dashboard.json"
)


def _block(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end, text.index(start))]


def _res(block: str, kind: str, key: str = "cpu"):
    """Đọc resources.<kind>.<key> bỏ qua dòng comment xen giữa.

    values-prod.yaml có comment giải thích NGAY GIỮA `requests:` và `cpu:`, nên
    regex hai dòng liền kề sẽ trượt.
    """
    m = re.search(rf"{kind}:\n((?:\s*#.*\n|\s*\w+:\s*\S+\n)+)", block)
    if not m:
        return None
    m2 = re.search(rf"^\s*{key}:\s*(\S+)\s*$", m.group(1), re.M)
    return m2.group(1) if m2 else None


def test_frontend_hpa_packs_existing_nodes_and_has_replica_headroom():
    text = HPA.read_text(encoding="utf-8")
    block = _block(text, "name: frontend-hpa", "name: product-catalog-hpa")
    # maxReplicas 8 -> 16: bước "capacity step" mà annotation cũ đã hẹn, giờ đã có
    # số đo. Đo exact-window trên node-set cố định 9 node (hash 54755c311f1a64b9),
    # generator ngoài cluster: frontend đứng ở 8/8 replica với utilization
    # 112%/65% tại trần 1000 user và 128%/65% tại stage vỡ 1400 user, trong khi
    # CPU node cao nhất chỉ 60% và hai node gần rỗng. Trần bị chặn bởi maxReplicas
    # chứ không bởi capacity node, nên nới replica là cách nâng trần mà KHÔNG thêm node.
    assert "maxReplicas: 16" in block
    assert "averageUtilization: 65" in block
    assert "staged PR" in block and "capacity step" in block
    # Giữ ràng buộc: bước này chỉ nới replica, không được lặng lẽ đổi target.
    assert "minReplicas: 2" in block


def test_hotpath_replica_caps_match_measured_capacity_step():
    """Trần replica của hot path phải khớp số đo 30/07, không đặt tuỳ ý.

    Mỗi giá trị dưới đây có căn cứ trong docs/evidence/mandate-19/real-2026-07-30/:
      frontend        8 -> 16  (112%/65% ở 8/8 tại trần; nút thắt số một)
      checkout        8 -> 14  (89%/65% ở 8/8; nguồn của 504 mà người dùng thấy)
      frontend-proxy  8 -> 12  (70%/65% ở 7/8; nút thắt kế tiếp)
      product-catalog 8 -> 12  (65%/65% ở 6/8; downstream của product-detail)
    """
    text = HPA.read_text(encoding="utf-8")
    expected = {
        ("name: frontend-hpa", "name: product-catalog-hpa"): "maxReplicas: 16",
        ("name: product-catalog-hpa", "name: cart-hpa"): "maxReplicas: 12",
        ("name: checkout-hpa", "name: currency-hpa"): "maxReplicas: 14",
        ("name: frontend-proxy-hpa", "name: frontend-hpa"): "maxReplicas: 12",
    }
    for (start, end), want in expected.items():
        block = _block(text, start, end)
        assert want in block, f"{start}: mong đợi {want}"


def test_checkout_slo_is_measured_at_the_user_facing_edge():
    """SLO checkout phải đo ở biên, không ở span nội bộ của service checkout.

    Vì sao: span nội bộ chỉ tồn tại khi request ĐÃ tới được checkout. Request bị
    timeout ở tầng trên không sinh span đó, nên chúng vô hình với SLI. Đo 30/07:
    ở 2400 user, 8.875/8.877 đơn trả 504 Gateway Timeout trong khi panel SLO cũ
    vẫn báo checkout_success = 100%. Đó là mù trên đúng luồng ra tiền.
    """
    dash = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    slo_panel_ids = {13, 41, 52}          # gauge SLO, trend, error budget
    diagnostic_ids = {40, 42}             # request rate + latency nội bộ
    seen = {}

    def walk(node):
        if isinstance(node, dict):
            pid = node.get("id")
            if pid in slo_panel_ids | diagnostic_ids and node.get("targets"):
                exprs = [t["expr"] for t in node["targets"] if t.get("expr")]
                seen[pid] = exprs
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(dash)

    for pid in slo_panel_ids:
        assert pid in seen, f"thiếu panel SLO checkout id={pid}"
        joined = " ".join(seen[pid])
        assert 'span_name="POST /api/checkout"' in joined, (
            f"panel {pid} phải đo ở biên frontend"
        )
        assert "oteldemo.CheckoutService/PlaceOrder" not in joined, (
            f"panel {pid} không được dùng span nội bộ làm SLI"
        )

    for pid in diagnostic_ids:
        joined = " ".join(seen.get(pid, []))
        assert "oteldemo.CheckoutService/PlaceOrder" in joined, (
            f"panel {pid} là panel chẩn đoán, phải giữ span nội bộ"
        )


def test_frontend_cpu_request_matches_measured_usage_denominator():
    text = VALUES.read_text(encoding="utf-8")
    block = _block(text, "  frontend:", "  product-catalog:")
    assert re.search(r"requests:\s+#[\s\S]*?cpu: 200m", block)
    assert re.search(r"limits:\s+cpu: 500m", block)


def test_frontend_headless_service_publishes_ready_frontend_pod_ips():
    service = yaml.safe_load(
        FRONTEND_HEADLESS_SERVICE.read_text(encoding="utf-8")
    )

    assert service["apiVersion"] == "v1"
    assert service["kind"] == "Service"
    assert service["metadata"] == {
        "name": "frontend-headless",
        "namespace": "techx-tf3",
    }
    assert service["spec"]["clusterIP"] == "None"
    assert service["spec"]["selector"] == {
        "opentelemetry.io/name": "frontend",
    }
    assert service["spec"].get("publishNotReadyAddresses", False) is False
    assert service["spec"]["ports"] == [
        {
            "name": "http",
            "protocol": "TCP",
            "port": 8080,
            "targetPort": 8080,
        }
    ]


def test_production_frontend_proxy_uses_headless_discovery_only():
    chart = yaml.safe_load(CHART_VALUES.read_text(encoding="utf-8"))
    prod = yaml.safe_load(VALUES.read_text(encoding="utf-8"))

    chart_env = {
        item["name"]: item.get("value")
        for item in chart["components"]["frontend-proxy"]["env"]
    }
    prod_overrides = {
        item["name"]: item.get("value")
        for item in prod["components"]["frontend-proxy"]["envOverrides"]
    }

    assert chart_env["FRONTEND_HOST"] == "frontend"
    assert prod_overrides["FRONTEND_HOST"] == "frontend-headless"


def test_browse_shadow_mode_and_checkout_funnel_precedes_catch_all():
    text = ENVOY.read_text(encoding="utf-8")
    checkout = text.index("name: checkout_protected")
    cart = text.index("name: cart_protected")
    detail = text.index("name: product_detail_protected")
    browse = text.index("name: browse_shedable")
    assert checkout < browse and cart < browse and detail < browse

    browse_block = _block(text, "name: browse_shedable", "http_filters:")
    assert "max_tokens: ${BROWSE_RATE_LIMIT_MAX_TOKENS}" in browse_block
    assert (
        "tokens_per_fill: ${BROWSE_RATE_LIMIT_TOKENS_PER_FILL}" in browse_block
    )
    assert re.search(
        r"filter_enabled:[\s\S]*?numerator:\s+"
        r"\$\{BROWSE_RATE_LIMIT_ENABLED_PERCENT\}",
        browse_block,
    )
    assert re.search(
        r"filter_enforced:[\s\S]*?numerator:\s+"
        r"\$\{BROWSE_RATE_LIMIT_ENFORCED_PERCENT\}",
        browse_block,
    )
    assert "x-techx-load-shed" in browse_block


def test_browse_rate_limit_yaml_indentation_is_valid():
    lines = ENVOY.read_text(encoding="utf-8").splitlines()
    expected_indents = {
        "token_bucket:": 30,
        "max_tokens: ${BROWSE_RATE_LIMIT_MAX_TOKENS}": 32,
        "tokens_per_fill: ${BROWSE_RATE_LIMIT_TOKENS_PER_FILL}": 32,
        "fill_interval: ${BROWSE_RATE_LIMIT_FILL_INTERVAL}": 32,
        "filter_enabled:": 30,
        "runtime_key: browse_rate_limit_enabled": 32,
        "filter_enforced:": 30,
        "runtime_key: browse_rate_limit_enforced": 32,
        "response_headers_to_add:": 30,
    }
    browse_start = next(
        index for index, line in enumerate(lines) if "name: browse_shedable" in line
    )
    filter_end = next(
        index
        for index, line in enumerate(lines[browse_start:], browse_start)
        if line.strip() == "http_filters:"
    )
    browse_lines = lines[browse_start:filter_end]
    for marker, expected in expected_indents.items():
        matching = [line for line in browse_lines if line.strip() == marker]
        assert len(matching) == 1, f"expected one {marker!r} in browse config"
        actual = len(matching[0]) - len(matching[0].lstrip())
        assert actual == expected, f"{marker!r} indent={actual}, expected={expected}"


def test_rate_limit_promotion_knobs_are_explicit_and_build_validated():
    prod = VALUES.read_text(encoding="utf-8")
    proxy = prod[prod.index("  frontend-proxy:") :]
    expected_prod_values = {
        # Hiệu chỉnh 30/07: bucket là PER-REPLICA nên budget tổng = giá trị này x số
        # replica proxy. PR #649 nới proxy 8 -> 12 đã nâng budget 400 -> 600 và làm
        # MẤT khả năng shed ở 2400 user (baseline 3.641 x 429 -> tuned 0 x 429, thay
        # bằng 1.713 x HTTP 500). 33 x 12 = 396 ~ 50 x 8 = 400: quay về đúng điểm bảo
        # vệ đã kiểm chứng bằng thực nghiệm.
        "BROWSE_RATE_LIMIT_MAX_TOKENS": "66",
        "BROWSE_RATE_LIMIT_TOKENS_PER_FILL": "33",
        "BROWSE_RATE_LIMIT_FILL_INTERVAL": "1s",
        "BROWSE_RATE_LIMIT_ENABLED_PERCENT": "100",
        "BROWSE_RATE_LIMIT_ENFORCED_PERCENT": "100",
        "LOCAL_RATE_LIMIT_ENABLED_PERCENT": "100",
        "LOCAL_RATE_LIMIT_ENFORCED_PERCENT": "0",
    }
    dockerfile = ENVOY_DOCKERFILE.read_text(encoding="utf-8")
    entrypoint = ENVOY_ENTRYPOINT.read_text(encoding="utf-8")
    for name, value in expected_prod_values.items():
        yaml_pair = rf"name:\s+{name}\s+value:\s+[\"']{re.escape(value)}[\"']"
        assert re.search(yaml_pair, proxy)
        assert f"{name}={value}" in dockerfile
        assert f'${{{name}:={value}}}' in entrypoint
    assert "envoy --mode validate" in dockerfile
    assert "envoy --mode validate" in entrypoint
    assert 'ENTRYPOINT ["./entrypoint.sh"]' in dockerfile


def test_overload_profile_separates_shedable_and_protected_streams():
    text = PROFILE.read_text(encoding="utf-8")
    assert "class BrowseOverloadUser" in text
    assert "class ProtectedCheckoutUser" in text
    assert '"/api/products"' in text
    assert '"/api/checkout"' in text
    assert "protected checkout was load-shed" in text


def test_email_is_treated_as_the_throughput_bottleneck():
    """email quyết định trần checkout — khoá cả HPA lẫn CPU của nó.

    Đo 30/07 (docs/evidence/mandate-19/real-2026-07-30/), stage 1400 user:
      span CLIENT `POST` checkout -> email  p95 = 15000 ms (= route timeout Envoy)
      span SERVER email                     p95 =   391 ms
    Chênh 14,6s là hàng đợi, không phải xử lý. checkout gọi email ĐỒNG BỘ
    (src/checkout/main.go:473) nên hàng đợi đó ăn trọn budget request -> 504:
    3.432/5.431 đơn hỏng, 82% toàn bộ lỗi client của stage.

    Trước bản vá: 1 replica, Ruby/Sinatra+Puma (GIL) với limit CPU 100m = 0,1 core.
    Hạ bất kỳ giá trị nào dưới đây là dựng lại nút thắt.
    """
    hpa = HPA.read_text(encoding="utf-8")
    block = hpa[hpa.index("name: email-hpa"):]
    assert "minReplicas: 2" in block
    assert "maxReplicas: 8" in block

    values = VALUES.read_text(encoding="utf-8")
    email = _block(values, "\n  email:", "\n  fraud-detection:")
    assert "replicasManagedExternally: true" in email
    assert _res(email, "requests") == "75m", "request phải sát usage (đo 100m)"
    assert _res(email, "limits") == "600m", "limit 100m CHÍNH LÀ trần cũ"


def test_grpc_deadlines_are_not_hair_triggers_under_load():
    """Deadline 500ms là nguồn của toàn bộ lỗi browse ở stage vỡ.

    Log frontend @1400 user: "4 DEADLINE_EXCEEDED: Deadline exceeded after 0.500s".
    product-catalog p95 server-side chỉ 6,9ms, nhưng đuôi dưới tải vượt 500ms và
    KHÔNG có retry -> lỗi cứng: 311 x HTTP 500 (/api/products/[id]) + 431 x HTTP 503
    (/api/product-reviews/[id]) = 742 lỗi, đúng phần kéo browse xuống 99,06%.

    Giữ deadline (REL-17-02 chặn treo vô hạn — gRPC-js không có deadline mặc định)
    nhưng nới ngưỡng. Trần 3000ms vì cổng SLO browse p95 < 1000ms.
    """
    values = VALUES.read_text(encoding="utf-8")
    frontend = _block(values, "\n  frontend:", "\n  product-catalog:")
    for var in ("PRODUCT_CATALOG_DEADLINE_MS", "PRODUCT_REVIEWS_DEADLINE_MS"):
        m = re.search(rf'name: {var}\n\s+value: "(\d+)"', frontend)
        assert m, f"{var} phải được đặt tường minh"
        assert 900 <= int(m.group(1)) <= 3000, f"{var}={m.group(1)} ngoài khoảng an toàn"


def test_cpu_requests_track_measured_usage_not_guesses():
    """"Resource request sát usage" theo cả HAI chiều, đo ở stage 1400 user.

    Thiếu (throttle) -> nới:  accounting 86,1% throttle (consumer MSK duy nhất ghi
    đơn vào RDS; throttle = đơn đã đặt nằm chờ trong topic), recommendation 18,1%
    (nằm trong mẫu số SLI browse).
    Thừa (giữ chỗ) -> trả:   ad giữ 100m nhưng chỉ dùng 17-21m, throttle 0%. Request
    là thứ scheduler chia node, nên phần thừa là phần email/accounting không xin được
    trên chính node đó.
    """
    values = VALUES.read_text(encoding="utf-8")

    accounting = _block(values, "\n  accounting:", "\n  email:")
    assert _res(accounting, "requests") == "150m"
    assert _res(accounting, "limits") == "600m"

    ad = _block(values, "\n  ad:", "\n  frontend:")
    assert int(_res(ad, "requests").rstrip("m")) <= 30, "ad phải thôi giữ chỗ 100m"
    assert _res(ad, "limits") == "500m", "vẫn cho ad burst, chỉ thôi giữ chỗ"

    reco = _block(values, "\n  recommendation:", "\n  accounting:")
    assert _res(reco, "requests") == "150m"
    assert _res(reco, "limits") == "700m"
