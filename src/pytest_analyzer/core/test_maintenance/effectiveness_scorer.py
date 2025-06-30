"""
Test Effectiveness Scorer

Provides scoring logic for test effectiveness as used by TestMaintainer.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class TestEffectivenessScore:
    test_path: Path
    score: float
    details: Dict[str, Any]


class EffectivenessScorer:
    """
    Scores the effectiveness of tests using multiple dimensions.
    """

    def score(
        self,
        test_file: Union[str, Path],
        test_funcs: List[str],
        trace: Dict[str, Any],
        historical_failures: Optional[Dict[str, int]] = None,
        coverage_data: Optional[Dict[str, float]] = None,
        execution_times: Optional[Dict[str, float]] = None,
        maintenance_history: Optional[Dict[str, int]] = None,
        risk_map: Optional[Dict[str, float]] = None,
    ) -> List[TestEffectivenessScore]:
        """
        Returns:
            List of TestEffectivenessScore objects.
        """
        scores = []
        for test_func in test_funcs:
            fail_rate = (historical_failures or {}).get(test_func, 0)
            coverage = (coverage_data or {}).get(test_func, 0.0)
            exec_time = (execution_times or {}).get(test_func, 1.0)
            maintenance = (maintenance_history or {}).get(test_func, 0)
            risk = 0.0
            for src_func in trace.get("test_to_code_map", {}).get(test_func, []):
                risk += (risk_map or {}).get(src_func, 0.0)
            score = (
                0.25 * min(fail_rate, 1.0)
                + 0.25 * coverage
                + 0.2 * (1.0 / max(exec_time, 0.01))
                + 0.15 * (1.0 - min(maintenance / 10, 1.0))
                + 0.15 * min(risk, 1.0)
            )
            scores.append(
                TestEffectivenessScore(
                    test_path=Path(test_file),
                    score=round(score, 3),
                    details={
                        "fail_rate": fail_rate,
                        "coverage": coverage,
                        "exec_time": exec_time,
                        "maintenance": maintenance,
                        "risk": risk,
                    },
                )
            )
        return scores
