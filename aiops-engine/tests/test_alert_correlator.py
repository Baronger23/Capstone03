"""
TDD Test Suite for AlertCorrelator — 2 bug fixes:
  - Bug 1: Time Window Clustering (alerts trong cùng window phải gộp chung)
  - Bug 2: Upstream Graph Traversal (select_rca_candidate phải duyệt upstream)

Chạy:  python -m pytest aiops-engine/tests/test_alert_correlator.py -v
"""
import time
import sys
import os
import pytest

# Đưa thư mục aiops-engine vào sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alert_correlator import AlertCorrelator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SERVICES_JSON = os.path.join(os.path.dirname(__file__), "..", "services.json")


def make_alert(service: str, alertname: str = "HighLatency",
               severity: str = "critical", trace_id: str = "trace-abc",
               fired_at_override: float = None) -> dict:
    return {
        "labels": {"service": service, "alertname": alertname, "severity": severity},
        "annotations": {"trace_id": trace_id},
        "fired_at": fired_at_override if fired_at_override is not None else time.time(),
    }


# ===========================================================================
# BUG 1 — Time Window Clustering
# ===========================================================================

class TestTimeWindowClustering:
    """
    Alert của product-catalog (t=0) và checkout (t+10s) phải được gộp vào
    CÙNG 1 cluster khi chênh lệch thời gian <= window_seconds.
    """

    def test_two_alerts_within_window_produce_one_cluster(self):
        """
        Khi product-catalog và checkout đến trong cùng time window (10s < 60s),
        correlator phải trả về ĐÚNG 1 cluster, không phải 2.
        """
        corr = AlertCorrelator(config_path=SERVICES_JSON, window_seconds=60)
        t0 = time.time()

        alert1 = make_alert("product-catalog", fired_at_override=t0)
        alert2 = make_alert("checkout", fired_at_override=t0 + 10)

        clusters = corr.correlate_alerts_windowed([alert1, alert2])

        assert len(clusters) == 1, (
            f"Mong đợi 1 cluster (cascade), nhận được {len(clusters)}. "
            "Bug 1: correlator đang tạo 2 incident riêng biệt thay vì gộp chung."
        )

    def test_alerts_outside_window_produce_separate_clusters(self):
        """
        Khi 2 alert cách nhau > window_seconds và không liên quan topology,
        chúng phải được xử lý thành 2 cluster riêng.
        """
        corr = AlertCorrelator(config_path=SERVICES_JSON, window_seconds=60)
        t0 = time.time()

        alert1 = make_alert("product-catalog", fired_at_override=t0)
        alert2 = make_alert("accounting",      fired_at_override=t0 + 300)

        clusters = corr.correlate_alerts_windowed([alert1, alert2])

        assert len(clusters) == 2, (
            f"Mong đợi 2 clusters (cách nhau 300s, không liên quan), nhận {len(clusters)}."
        )

    def test_three_cascade_alerts_within_window_become_one_cluster(self):
        """
        frontend → checkout → product-catalog đều bị alert trong 30s
        phải gộp thành 1 cluster duy nhất.
        """
        corr = AlertCorrelator(config_path=SERVICES_JSON, window_seconds=60)
        t0 = time.time()

        alerts = [
            make_alert("product-catalog", fired_at_override=t0),
            make_alert("checkout",        fired_at_override=t0 + 10),
            make_alert("frontend",        fired_at_override=t0 + 20),
        ]

        clusters = corr.correlate_alerts_windowed(alerts)

        assert len(clusters) == 1, (
            f"3 alert cascade trong 30s phải cho 1 cluster, nhận {len(clusters)}."
        )


# ===========================================================================
# BUG 2 — Upstream Graph Traversal
# ===========================================================================

class TestUpstreamGraphTraversal:
    """
    Khi chỉ có checkout trong alert list nhưng product-catalog đang anomalous
    (biết qua anomalous_services), RCA phải trả về product-catalog (upstream culprit),
    không phải checkout (victim).
    """

    def test_select_rca_candidate_picks_upstream_over_downstream(self):
        """
        Topo: product-catalog (upstream) → checkout (downstream).
        Khi cả 2 có trong cluster, culprit phải là product-catalog (upstream gốc),
        không phải checkout (xa frontend hơn theo thuật toán cũ).
        """
        corr = AlertCorrelator(config_path=SERVICES_JSON, window_seconds=60)
        t0 = time.time()

        # Cả 2 service xuất hiện trong cùng cluster
        # product-catalog: started_at = t0 (first drift)
        # checkout:         started_at = t0 + 10 (cascade sau)
        alerts = [
            make_alert("product-catalog", fired_at_override=t0),
            make_alert("checkout",        fired_at_override=t0 + 10),
        ]

        clusters = corr.correlate_alerts_windowed(alerts)
        assert len(clusters) == 1
        culprit = clusters[0]["culprit_service"]

        assert culprit == "product-catalog", (
            f"Culprit phải là 'product-catalog' (upstream, first-drift sớm hơn), "
            f"nhưng nhận được '{culprit}'. "
            "Bug 2: thuật toán đang chọn downstream sâu nhất thay vì upstream first-drift."
        )

    def test_first_drift_time_breaks_tie(self):
        """
        Khi 2 service cùng khoảng cách upstream, service có first-drift
        sớm hơn (fired_at nhỏ hơn) phải được chọn làm culprit.
        """
        corr = AlertCorrelator(config_path=SERVICES_JSON, window_seconds=60)
        t0 = time.time()

        # payment và shipping đều là downstream của checkout — cùng depth
        # payment fired trước → payment là culprit
        alerts = [
            make_alert("payment",  fired_at_override=t0),
            make_alert("shipping", fired_at_override=t0 + 5),
        ]

        clusters = corr.correlate_alerts_windowed(alerts)
        assert len(clusters) == 1
        culprit = clusters[0]["culprit_service"]

        assert culprit == "payment", (
            f"Khi cùng depth, service có first-drift sớm hơn (payment) phải là culprit, "
            f"nhưng nhận '{culprit}'."
        )

    def test_single_service_always_culprit(self):
        """
        Khi chỉ có 1 service trong cluster, nó luôn là culprit (edge case).
        """
        corr = AlertCorrelator(config_path=SERVICES_JSON, window_seconds=60)
        alerts = [make_alert("recommendation")]
        clusters = corr.correlate_alerts_windowed(alerts)

        assert len(clusters) == 1
        assert clusters[0]["culprit_service"] == "recommendation"
