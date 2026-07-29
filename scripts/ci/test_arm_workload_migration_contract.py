from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[2]
ARM_VALUES = REPO / "phase3 - information/deploy/values-mandate13.yaml"


def scheduling_rules(component: str) -> dict:
    values = yaml.safe_load(ARM_VALUES.read_text(encoding="utf-8"))
    return values["components"][component]["schedulingRules"]


def test_product_reviews_uses_arm_elastic_scheduling_contract():
    rules = scheduling_rules("product-reviews")

    assert rules["nodeSelector"] == {
        "techx.io/workload": "elastic",
        "techx.io/arch": "arm64",
    }
    assert rules["tolerations"] == [
        {
            "key": "techx.io/workload",
            "operator": "Equal",
            "value": "elastic",
            "effect": "NoSchedule",
        },
        {
            "key": "techx.io/arch",
            "operator": "Equal",
            "value": "arm64",
            "effect": "NoSchedule",
        },
    ]


def test_currency_uses_arm_elastic_scheduling_contract():
    assert scheduling_rules("currency") == scheduling_rules("product-reviews")


def test_quote_uses_arm_elastic_scheduling_contract():
    assert scheduling_rules("quote") == scheduling_rules("product-reviews")


def test_shipping_uses_arm_elastic_scheduling_contract():
    assert scheduling_rules("shipping") == scheduling_rules("product-reviews")


def test_cart_uses_arm_elastic_scheduling_contract():
    assert scheduling_rules("cart") == scheduling_rules("product-reviews")


def test_payment_uses_arm_elastic_scheduling_contract():
    assert scheduling_rules("payment") == scheduling_rules("product-reviews")


def test_frontend_uses_arm_elastic_scheduling_contract():
    assert scheduling_rules("frontend") == scheduling_rules("product-reviews")


def test_frontend_proxy_uses_arm_elastic_scheduling_contract():
    assert scheduling_rules("frontend-proxy") == scheduling_rules("product-reviews")
