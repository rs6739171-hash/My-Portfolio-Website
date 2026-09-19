# Explainable Credit Risk Assessment with SHAP

**Python · scikit-learn · SHAP · FastAPI · Streamlit · model evaluation · scenario analysis**

A portfolio-grade explainable machine-learning application by **Rishabh Shukla**.

**Live demo:** https://explainable-credit-risk-shap.onrender.com

**Measured synthetic holdout:** ROC-AUC **0.8109** · PR-AUC **0.5686** · Recall **0.6420** · F1 **0.5554** · Brier score **0.1701** · threshold **0.5850** on **2,250** holdout rows. It estimates synthetic credit-risk probabilities, shows the strongest SHAP drivers behind each score, and supports what-if analysis without using protected demographic attributes.

> **Important:** This is an educational portfolio demo using generated synthetic data. It is not a lending product, credit bureau model, underwriting policy, or regulatory-compliance system and must not be used to approve or deny real credit.

## Recruiter quick scan

- **End-to-end ML:** deterministic synthetic data generation, preprocessing, train/validation split, logistic-risk model, threshold selection and persisted artifacts.
- **Explainability:** real SHAP values are aggregated back to business-facing input fields and labeled as risk-increasing or risk-reducing drivers.
- **Model evaluation:** ROC-AUC, PR-AUC, precision, recall, F1, Brier score, threshold and holdout prevalence are exposed by the application.
- **What-if analysis:** compare a baseline application with a modified scenario and measure the probability delta.
- **Responsible design:** no race, gender, religion, marital status, disability or other protected traits are collected; the README explicitly avoids fairness/compliance claims.
- **Delivery:** FastAPI, Streamlit, tests, evaluation checks, GitHub Actions and Render deployment configuration.

## Architecture

~~~text
Synthetic training generator
        │
        ▼
ColumnTransformer
numeric scaling + categorical one-hot encoding
        │
        ▼
Logistic risk model
        │
        ├──► validation metrics + selected threshold
        │
        ▼
SHAP LinearExplainer
        │
        ▼
field-level reason codes
        │
        ├──► FastAPI scoring / scenario endpoints
        └──► Streamlit recruiter demo
~~~

## Why this implementation is different

The public architecture reference contained a notebook, dataset, pickled model and small prediction API, but no visible license or README when reviewed. Its deployed API returned a probability and label but did not expose SHAP explanations. This implementation was independently written, uses generated synthetic data, trains its own model during the build, adds real SHAP explanations, evaluation, scenario analysis, tests, documentation and a new interface.

See [ATTRIBUTION.md](ATTRIBUTION.md).

## Features

- Synthetic dataset generation at build time; no copied borrower dataset is committed.
- Numeric and categorical preprocessing with scikit-learn.
- Logistic regression with balanced class weights.
- Validation-set threshold selection using F1.
- SHAP LinearExplainer over transformed model features.
- Aggregated field-level reason codes, including direction and contribution.
- FastAPI endpoints:
  - `GET /health`
  - `GET /api/v1/model-card`
  - `POST /api/v1/score`
  - `POST /api/v1/scenario`
- Streamlit dashboard for scoring and explanations.
- Unit tests and a deterministic evaluation script.

## Local run

~~~bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python train_model.py
python serve.py
~~~

## Verification

~~~bash
python train_model.py
python -m unittest discover -s tests -v
python -m evals.run_eval
python -m compileall -q app evals train_model.py serve.py
~~~

## Deployment

The Render build command installs dependencies and runs `train_model.py`, so the model artifact is created from the checked-in training code instead of committing a binary model.

## Model-risk notes

This project intentionally does **not** claim that excluding protected attributes makes a model fair. Proxy variables, sample construction, labels, calibration, drift and policy choices can all create disparate outcomes. A real credit system would need legal review, representative production data, fairness testing across legally appropriate groups, monitoring, security, governance and adverse-action compliance.
