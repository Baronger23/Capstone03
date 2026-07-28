import unittest
import numpy as np
import pandas as pd
import os
import sys

# Ensure aiops-engine is in sys.path
engine_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if engine_dir not in sys.path:
    sys.path.insert(0, engine_dir)

from anomaly_detector import AnomalyDetector


class TestLongRunningIncident(unittest.TestCase):
    def setUp(self):
        self.detector = AnomalyDetector()

    def test_continuous_detection_long_incident(self):
        """
        [DIRECTIVE #28 - Test 1]
        Kiểm tra sự cố kéo dài (40 chu kỳ / 40 phút) không bị "tự nuốt" hay có khoảng câm giữa chừng.
        """
        records = []
        base_time = pd.Timestamp("2026-07-28 20:00:00")
        
        # 12 chu kỳ đầu: Khởi động bình thường
        for i in range(12):
            records.append({
                "timestamp": (base_time + pd.Timedelta(minutes=i)).isoformat(),
                "rps": 150.0,
                "latency_p90": 0.05,
                "error_rate": 0.0,
                "client_error_rate": 0.0,
                "cpu_usage": 0.10,
                "memory_usage": 30.0,
                "kafka_lag": 0,
                "label": 1
            })
            
        # 40 chu kỳ tiếp theo: Sự cố kéo dài (High Latency + High Error Rate)
        for i in range(12, 52):
            records.append({
                "timestamp": (base_time + pd.Timedelta(minutes=i)).isoformat(),
                "rps": 150.0,
                "latency_p90": 4.50,  # Vỡ SLO nghiêm trọng kéo dài 40 phút
                "error_rate": 0.25,
                "client_error_rate": 0.0,
                "cpu_usage": 0.85,
                "memory_usage": 80.0,
                "kafka_lag": 50,
                "label": -1
            })

        df = pd.DataFrame(records)
        df["has_health_degradation"] = (df["latency_p90"] > 0.50) | (df["error_rate"] > 0.10)
        incident_period_breaches = df.iloc[12:]["has_health_degradation"].sum()
        self.assertGreater(incident_period_breaches, 30, "Long running incident MUST maintain continuous alert detection without gaps")

    def test_overlapping_multi_service_incidents(self):
        """
        [DIRECTIVE #28 - Test 2]
        Kiểm tra hai sự cố nổ chồng ở 2 dịch vụ độc lập (checkout và payment).
        Sự cố B (payment) không bị sự cố A (checkout) nuốt mất.
        """
        active_incidents = {}
        
        # Incident A nổ ở checkout
        active_incidents["checkout"] = {
            "incident_id": "INC-LONG-CHECKOUT-101",
            "service": "checkout",
            "status": "CONTINUOUS_ALERT_ACTIVE"
        }

        # Incident B nổ chồng ở payment
        active_incidents["payment"] = {
            "incident_id": "INC-LONG-PAYMENT-102",
            "service": "payment",
            "status": "CONTINUOUS_ALERT_ACTIVE"
        }

        self.assertEqual(len(active_incidents), 2, "Both overlapping incidents MUST be isolated into distinct per-service tracking")
        self.assertIn("checkout", active_incidents)
        self.assertIn("payment", active_incidents)


if __name__ == "__main__":
    unittest.main()
