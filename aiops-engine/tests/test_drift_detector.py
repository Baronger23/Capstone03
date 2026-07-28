import unittest
import numpy as np
import pandas as pd
import os
import sys

# Ensure aiops-engine is in sys.path
engine_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if engine_dir not in sys.path:
    sys.path.insert(0, engine_dir)

from drift_detector import DataDriftDetector


class TestDataDriftDetector(unittest.TestCase):
    def setUp(self):
        self.detector = DataDriftDetector(num_bins=10)
        np.random.seed(42)
        # Baseline: 1000 mẫu phân phối chuẩn với mean=0.05, std=0.01 (Độ trễ bình thường ~50ms)
        self.baseline_latency = np.random.normal(loc=0.05, scale=0.01, size=1000)
        self.baseline_rps = np.random.normal(loc=150.0, scale=10.0, size=1000)

        self.detector.set_baseline("latency_p90", self.baseline_latency)
        self.detector.set_baseline("rps", self.baseline_rps)

    def test_stable_data_no_drift(self):
        """
        [DIRECTIVE #27 - Test 1]
        Kiểm tra dữ liệu ổn định (Normal Traffic) không bị báo giả (PSI < 0.10).
        """
        stable_latency = np.random.normal(loc=0.051, scale=0.01, size=500)
        stable_rps = np.random.normal(loc=149.5, scale=10.0, size=500)

        df_stable = pd.DataFrame({
            "latency_p90": stable_latency,
            "rps": stable_rps
        })

        res = self.detector.detect_drift(df_stable, psi_threshold=0.25)

        self.assertFalse(res["drift_detected"], "Stable data MUST NOT trigger drift alert")
        self.assertLess(res["overall_max_psi"], 0.10, "PSI for stable data MUST be < 0.10")
        self.assertEqual(len(res["drifted_metrics"]), 0, "No metrics should be marked as drifted")

    def test_shifted_data_detects_drift(self):
        """
        [DIRECTIVE #27 - Test 2]
        Kiểm tra dữ liệu bị shift phân phối (Data Drift) phải được kích hoạt cờ FLAG DRIFT (PSI >= 0.25).
        """
        # Data Shift: Độ trễ vọt từ 0.05s lên 0.45s (Thủ phạm gây drift)
        shifted_latency = np.random.normal(loc=0.45, scale=0.05, size=500)
        stable_rps = np.random.normal(loc=150.0, scale=10.0, size=500)

        df_shifted = pd.DataFrame({
            "latency_p90": shifted_latency,
            "rps": stable_rps
        })

        res = self.detector.detect_drift(df_shifted, psi_threshold=0.25)

        self.assertTrue(res["drift_detected"], "Shifted latency distribution MUST trigger drift alert")
        self.assertGreaterEqual(res["overall_max_psi"], 0.25, "PSI for shifted data MUST be >= 0.25")
        
        drifted_names = [m["metric"] for m in res["drifted_metrics"]]
        self.assertIn("latency_p90", drifted_names, "latency_p90 MUST be identified in drifted_metrics")

    def test_ks_statistic(self):
        """
        [DIRECTIVE #27 - Test 3]
        Kiểm tra thuật toán Kolmogorov-Smirnov (KS-statistic) đo khoảng cách CDF.
        """
        d_stat = self.detector.calculate_ks_stat(self.baseline_latency, self.baseline_latency)
        self.assertAlmostEqual(d_stat, 0.0, places=2, msg="KS distance between identical datasets must be ~0")

        shifted_latency = np.random.normal(loc=0.50, scale=0.01, size=1000)
        d_stat_shifted = self.detector.calculate_ks_stat(self.baseline_latency, shifted_latency)
        self.assertGreater(d_stat_shifted, 0.80, "KS distance for distinct distributions must be high")


if __name__ == "__main__":
    unittest.main()
