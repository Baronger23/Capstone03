import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Any

logger = logging.getLogger("AIOpsEngine.DriftDetector")

class DataDriftDetector:
    """
    [DIRECTIVE #27 - MLOps Data & Model Drift Detection Engine]
    Phát hiện Data Drift (Shift phân phối đầu vào) và Model Drift (Suy giảm chất lượng output)
    bằng thuật toán Population Stability Index (PSI) và Kolmogorov-Smirnov (KS-Test).
    """
    def __init__(self, num_bins: int = 10):
        self.num_bins = num_bins
        self.baselines: Dict[str, np.ndarray] = {}

    def set_baseline(self, feature_name: str, baseline_data: Any):
        """Thiết lập phân phối baseline chuẩn cho một thuộc tính."""
        arr = np.array(baseline_data, dtype=float)
        arr = arr[~np.isnan(arr)]
        if len(arr) > 0:
            self.baselines[feature_name] = arr
            logger.info(f"[DriftDetector] Baseline established for '{feature_name}' ({len(arr)} samples, mean={arr.mean():.4f}, std={arr.std():.4f})")

    def calculate_psi(self, baseline: np.ndarray, current: np.ndarray) -> float:
        """
        Tính chỉ số Population Stability Index (PSI):
        PSI = sum((Actual% - Expected%) * ln(Actual% / Expected%))
        """
        if len(baseline) == 0 or len(current) == 0:
            return 0.0

        # Xác định khoảng chia Bins từ Baseline
        min_val = min(baseline.min(), current.min())
        max_val = max(baseline.max(), current.max())
        
        if min_val == max_val:
            return 0.0

        bins = np.linspace(min_val, max_val, self.num_bins + 1)
        
        # Đếm số lượng trong mỗi Bin
        baseline_counts, _ = np.histogram(baseline, bins=bins)
        current_counts, _ = np.histogram(current, bins=bins)

        # Chuyển đổi sang tỷ lệ phần trăm (Tỷ lệ xác suất)
        baseline_pct = baseline_counts / len(baseline)
        current_pct = current_counts / len(current)

        # Thêm Epsilon nhỏ để tránh lỗi chia cho 0 hoặc log(0)
        eps = 1e-4
        baseline_pct = np.where(baseline_pct == 0, eps, baseline_pct)
        current_pct = np.where(current_pct == 0, eps, current_pct)

        # Thuật toán công thức PSI
        psi_value = np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct))
        return float(psi_value)

    def calculate_ks_stat(self, baseline: np.ndarray, current: np.ndarray) -> float:
        """
        Tính khoảng cách lớn nhất giữa hai phân phối tích lũy CDF (KS-statistic).
        """
        if len(baseline) == 0 or len(current) == 0:
            return 0.0
            
        data1 = np.sort(baseline)
        data2 = np.sort(current)
        
        n1 = len(data1)
        n2 = len(data2)
        
        data_all = np.concatenate([data1, data2])
        
        cdf1 = np.searchsorted(data1, data_all, side='right') / n1
        cdf2 = np.searchsorted(data2, data_all, side='right') / n2
        
        d_stat = np.max(np.abs(cdf1 - cdf2))
        return float(d_stat)

    def detect_drift(self, current_data: pd.DataFrame, psi_threshold: float = 0.25) -> Dict[str, Any]:
        """
        Quét và phát hiện Data/Model Drift trên tất cả các thuộc tính.
        - PSI < 0.1: No Drift (Phân phối ổn định)
        - 0.1 <= PSI < 0.25: Moderate Shift (Biến động nhẹ)
        - PSI >= 0.25: Significant Drift (Phát hiện Data Drift!)
        """
        drifted_metrics = []
        overall_max_psi = 0.0
        drift_detected = False

        for col in current_data.columns:
            if col in self.baselines:
                baseline_arr = self.baselines[col]
                current_arr = current_data[col].dropna().values.astype(float)
                
                if len(current_arr) == 0:
                    continue

                psi_score = self.calculate_psi(baseline_arr, current_arr)
                ks_stat = self.calculate_ks_stat(baseline_arr, current_arr)

                if psi_score > overall_max_psi:
                    overall_max_psi = psi_score

                if psi_score >= psi_threshold:
                    drift_detected = True
                    drifted_metrics.append({
                        "metric": col,
                        "psi_score": round(psi_score, 4),
                        "ks_statistic": round(ks_stat, 4),
                        "status": "DRIFT_CRITICAL",
                        "message": f"Population Stability Index {psi_score:.4f} >= threshold {psi_threshold}"
                    })
                elif psi_score >= 0.10:
                    drifted_metrics.append({
                        "metric": col,
                        "psi_score": round(psi_score, 4),
                        "ks_statistic": round(ks_stat, 4),
                        "status": "DRIFT_WARNING",
                        "message": f"Moderate distribution shift detected (PSI={psi_score:.4f})"
                    })

        return {
            "drift_detected": drift_detected,
            "overall_max_psi": round(overall_max_psi, 4),
            "psi_threshold": psi_threshold,
            "drifted_metrics": drifted_metrics,
            "total_metrics_scanned": len([c for c in current_data.columns if c in self.baselines])
        }

# Global Instance của DataDriftDetector
drift_detector = DataDriftDetector()
