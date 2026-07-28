from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
HPA = ROOT / "gitops/infrastructure/hpa-hotpath.yaml"
VALUES = ROOT / "phase3 - information/deploy/values-prod.yaml"
ENVOY = (
    ROOT
    / "phase3 - information/techx-corp-platform/src/frontend-proxy/envoy.tmpl.yaml"
)
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
    assert "max_tokens: 100" in browse_block
    assert "tokens_per_fill: 50" in browse_block
    assert re.search(
        r"filter_enabled:[\s\S]*?numerator:\s+100", browse_block
    )
    assert re.search(
        r"filter_enforced:[\s\S]*?numerator:\s+0", browse_block
    )
    assert "x-techx-load-shed" in browse_block


def test_browse_rate_limit_yaml_indentation_is_valid():
    lines = ENVOY.read_text(encoding="utf-8").splitlines()
    expected_indents = {
        "token_bucket:": 30,
        "max_tokens: 100": 32,
        "tokens_per_fill: 50": 32,
        "fill_interval: 1s": 32,
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


def test_overload_profile_separates_shedable_and_protected_streams():
    text = PROFILE.read_text(encoding="utf-8")
    assert "class BrowseOverloadUser" in text
    assert "class ProtectedCheckoutUser" in text
    assert '"/api/products"' in text
    assert '"/api/checkout"' in text
    assert "protected checkout was load-shed" in text
