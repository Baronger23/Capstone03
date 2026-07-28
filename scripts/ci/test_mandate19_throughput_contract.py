from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
HPA = ROOT / "gitops/infrastructure/hpa-hotpath.yaml"
VALUES = ROOT / "phase3 - information/deploy/values-prod.yaml"
ENVOY = (
    ROOT
    / "phase3 - information/techx-corp-platform/src/frontend-proxy/envoy.tmpl.yaml"
)
ENVOY_DOCKERFILE = (
    ROOT
    / "phase3 - information/techx-corp-platform/src/frontend-proxy/Dockerfile"
)
CHART_VALUES = ROOT / "phase3 - information/techx-corp-chart/values.yaml"
PROFILE = (
    ROOT
    / "phase3 - information/techx-corp-platform/src/load-generator/mandate19_locustfile.py"
)


def _block(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end, text.index(start))]


def test_frontend_hpa_packs_existing_nodes_and_has_replica_headroom():
    text = HPA.read_text(encoding="utf-8")
    block = _block(text, "name: frontend-hpa", "name: product-catalog-hpa")
    assert "maxReplicas: 8" in block
    assert "averageUtilization: 65" in block
    assert "staged PR" in block and "capacity step" in block


def test_frontend_cpu_request_matches_measured_usage_denominator():
    text = VALUES.read_text(encoding="utf-8")
    block = _block(text, "  frontend:", "  product-catalog:")
    assert re.search(r"requests:\s+#[\s\S]*?cpu: 200m", block)
    assert re.search(r"limits:\s+cpu: 500m", block)


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
        "BROWSE_RATE_LIMIT_MAX_TOKENS": "100",
        "BROWSE_RATE_LIMIT_TOKENS_PER_FILL": "50",
        "BROWSE_RATE_LIMIT_FILL_INTERVAL": "1s",
        "BROWSE_RATE_LIMIT_ENABLED_PERCENT": "100",
        "BROWSE_RATE_LIMIT_ENFORCED_PERCENT": "0",
        "LOCAL_RATE_LIMIT_ENABLED_PERCENT": "100",
        "LOCAL_RATE_LIMIT_ENFORCED_PERCENT": "0",
    }
    chart = CHART_VALUES.read_text(encoding="utf-8")
    dockerfile = ENVOY_DOCKERFILE.read_text(encoding="utf-8")
    for name, value in expected_prod_values.items():
        yaml_pair = rf"name:\s+{name}\s+value:\s+[\"']{re.escape(value)}[\"']"
        assert re.search(yaml_pair, proxy)
        assert re.search(yaml_pair, chart)
        assert f"{name}={value}" in dockerfile
    assert "envoy --mode validate" in dockerfile


def test_overload_profile_separates_shedable_and_protected_streams():
    text = PROFILE.read_text(encoding="utf-8")
    assert "class BrowseOverloadUser" in text
    assert "class ProtectedCheckoutUser" in text
    assert '"/api/products"' in text
    assert '"/api/checkout"' in text
    assert "protected checkout was load-shed" in text
