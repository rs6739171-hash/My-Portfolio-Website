from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

from .schema import LoanApplication


ARTIFACT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "credit_risk.joblib"


class CreditRiskModel:
    def __init__(self):
        payload = joblib.load(ARTIFACT_PATH)
        self.preprocessor = payload["preprocessor"]
        self.model = payload["model"]
        self.threshold = float(payload["threshold"])
        self.metrics = payload["metrics"]
        self.feature_names = payload["feature_names"]
        self.background = payload["background"]
        self.raw_features = payload["raw_features"]
        self.numeric_features = payload["numeric_features"]
        self.categorical_features = payload["categorical_features"]
        self.explainer = shap.LinearExplainer(self.model, self.background)

    def _to_frame(self, application: LoanApplication) -> pd.DataFrame:
        return pd.DataFrame([application.model_dump()])[self.raw_features]

    def _raw_feature_for_transformed(self, transformed: str) -> str:
        if transformed.startswith("num__"):
            return transformed.removeprefix("num__")
        if transformed.startswith("cat__"):
            remainder = transformed.removeprefix("cat__")
            for feature in sorted(self.categorical_features, key=len, reverse=True):
                prefix = feature + "_"
                if remainder.startswith(prefix):
                    return feature
        return transformed

    def _group_shap(self, values: np.ndarray, application: LoanApplication) -> list[dict]:
        grouped = defaultdict(float)
        for transformed_name, value in zip(self.feature_names, values):
            grouped[self._raw_feature_for_transformed(transformed_name)] += float(value)

        payload = application.model_dump()
        rows = []
        for feature, contribution in grouped.items():
            rows.append({
                "feature": feature,
                "value": payload.get(feature),
                "shap_value": round(contribution, 5),
                "direction": "increases risk" if contribution > 0 else "reduces risk",
                "magnitude": round(abs(contribution), 5),
            })
        rows.sort(key=lambda x: x["magnitude"], reverse=True)
        return rows

    def score(self, application: LoanApplication) -> dict:
        frame = self._to_frame(application)
        transformed = self.preprocessor.transform(frame)
        probability = float(self.model.predict_proba(transformed)[0, 1])
        explanation = self.explainer(transformed)
        shap_values = np.asarray(explanation.values)[0]
        drivers = self._group_shap(shap_values, application)

        if probability >= self.threshold:
            tier = "higher risk"
        elif probability >= self.threshold * 0.62:
            tier = "moderate risk"
        else:
            tier = "lower risk"

        return {
            "default_probability": round(probability, 6),
            "risk_tier": tier,
            "review_threshold": round(self.threshold, 6),
            "above_threshold": probability >= self.threshold,
            "top_drivers": drivers[:6],
            "all_drivers": drivers,
            "explanation_space": "SHAP contributions to the model's linear log-odds score",
            "disclaimer": "Synthetic educational model only; not for real lending or underwriting decisions.",
        }

    def scenario(self, baseline: LoanApplication, scenario: LoanApplication) -> dict:
        before = self.score(baseline)
        after = self.score(scenario)
        delta = after["default_probability"] - before["default_probability"]
        return {
            "baseline_probability": before["default_probability"],
            "scenario_probability": after["default_probability"],
            "probability_delta": round(delta, 6),
            "direction": "higher" if delta > 0 else ("lower" if delta < 0 else "unchanged"),
            "baseline_tier": before["risk_tier"],
            "scenario_tier": after["risk_tier"],
            "scenario_drivers": after["top_drivers"],
            "disclaimer": before["disclaimer"],
        }


_model: CreditRiskModel | None = None


def get_model() -> CreditRiskModel:
    global _model
    if _model is None:
        _model = CreditRiskModel()
    return _model
