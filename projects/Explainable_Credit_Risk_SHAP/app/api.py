from __future__ import annotations

from fastapi import FastAPI

from .model_service import get_model
from .schema import LoanApplication, ScenarioRequest


app = FastAPI(
    title="Explainable Credit Risk Assessment with SHAP",
    version="1.0.0",
    description="Synthetic-data portfolio demo for explainable credit-risk modeling.",
)


@app.get("/health")
def health():
    model = get_model()
    return {
        "status": "ok",
        "artifact_loaded": True,
        "explainability": "SHAP",
        "data": "generated_synthetic",
        "threshold": model.threshold,
    }


@app.get("/api/v1/model-card")
def model_card():
    model = get_model()
    return {
        "model_type": "LogisticRegression",
        "explainability": "SHAP LinearExplainer",
        "data_type": "generated_synthetic",
        "features": model.raw_features,
        "protected_attributes_collected": [],
        "metrics": model.metrics,
        "limitations": [
            "Synthetic training data is not representative of any real lender portfolio.",
            "Excluding protected traits does not prove fairness or regulatory compliance.",
            "SHAP explains this model's behavior; it does not establish causality.",
            "The score must not be used for real lending decisions.",
        ],
    }


@app.post("/api/v1/score")
def score(application: LoanApplication):
    return get_model().score(application)


@app.post("/api/v1/scenario")
def scenario(request: ScenarioRequest):
    return get_model().scenario(request.baseline, request.scenario)
