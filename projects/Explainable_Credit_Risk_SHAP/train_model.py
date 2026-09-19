from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "credit_risk.joblib"

NUMERIC = [
    "person_age",
    "person_income",
    "person_emp_length",
    "loan_amnt",
    "loan_int_rate",
    "loan_percent_income",
    "cb_person_cred_hist_length",
]
CATEGORICAL = [
    "person_home_ownership",
    "loan_intent",
    "loan_grade",
    "cb_person_default_on_file",
]
FEATURES = NUMERIC + CATEGORICAL


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def generate_synthetic_data(n: int = 9000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    age = rng.integers(21, 70, size=n)
    income = np.clip(rng.lognormal(mean=np.log(62000), sigma=0.55, size=n), 18000, 300000)
    home = rng.choice(["RENT", "MORTGAGE", "OWN", "OTHER"], size=n, p=[0.43, 0.38, 0.16, 0.03])
    max_emp = np.maximum(age - 18, 1)
    emp = np.minimum(np.clip(rng.gamma(2.3, 2.5, size=n), 0, 40), max_emp).round(1)
    intent = rng.choice(
        ["EDUCATION", "MEDICAL", "VENTURE", "PERSONAL", "HOMEIMPROVEMENT", "DEBTCONSOLIDATION"],
        size=n,
        p=[0.16, 0.15, 0.12, 0.24, 0.14, 0.19],
    )
    grade = rng.choice(["A", "B", "C", "D", "E", "F", "G"], size=n, p=[0.22, 0.25, 0.20, 0.14, 0.09, 0.06, 0.04])
    grade_num = pd.Series(grade).map({"A":0, "B":1, "C":2, "D":3, "E":4, "F":5, "G":6}).to_numpy()
    amount = np.clip(rng.gamma(2.5, 4200, size=n), 1000, 40000)
    rate = np.clip(5.5 + grade_num * 2.15 + rng.normal(0, 1.15, size=n), 4.0, 29.0)
    pct_income = np.clip(amount / income, 0.01, 0.75)
    prior_default = rng.choice(["N", "Y"], size=n, p=[0.82, 0.18])
    hist = np.minimum(rng.integers(2, 31, size=n), np.maximum(age - 18, 2))

    intent_risk = pd.Series(intent).map({
        "EDUCATION":0.05, "MEDICAL":0.35, "VENTURE":0.18, "PERSONAL":0.22,
        "HOMEIMPROVEMENT":0.04, "DEBTCONSOLIDATION":0.30,
    }).to_numpy()
    home_risk = pd.Series(home).map({"OWN":-0.35, "MORTGAGE":-0.12, "RENT":0.18, "OTHER":0.12}).to_numpy()

    logit = (
        -3.25
        + 0.58 * grade_num
        + 2.9 * np.maximum(pct_income - 0.18, 0)
        + 0.095 * np.maximum(rate - 10, 0)
        + 1.25 * (prior_default == "Y").astype(float)
        - 0.000006 * np.maximum(income - 50000, 0)
        - 0.035 * np.minimum(emp, 12)
        - 0.018 * np.minimum(hist, 20)
        + home_risk
        + intent_risk
        + rng.normal(0, 0.55, size=n)
    )
    probability = sigmoid(logit)
    target = rng.binomial(1, probability)

    return pd.DataFrame({
        "person_age": age,
        "person_income": income.round(2),
        "person_home_ownership": home,
        "person_emp_length": emp,
        "loan_intent": intent,
        "loan_grade": grade,
        "loan_amnt": amount.round(2),
        "loan_int_rate": rate.round(2),
        "loan_percent_income": pct_income.round(4),
        "cb_person_default_on_file": prior_default,
        "cb_person_cred_hist_length": hist,
        "default": target,
    })


def choose_threshold(y_true, probabilities) -> float:
    candidates = np.linspace(0.15, 0.75, 121)
    scores = [f1_score(y_true, probabilities >= t) for t in candidates]
    return float(candidates[int(np.argmax(scores))])


def main() -> None:
    data = generate_synthetic_data()
    X = data[FEATURES]
    y = data["default"]

    X_train, X_valid, y_train, y_valid = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
    ])

    transformed_train = preprocessor.fit_transform(X_train)
    transformed_valid = preprocessor.transform(X_valid)

    model = LogisticRegression(
        max_iter=1500,
        class_weight="balanced",
        C=0.85,
        solver="lbfgs",
        random_state=42,
    )
    model.fit(transformed_train, y_train)

    probability = model.predict_proba(transformed_valid)[:, 1]
    threshold = choose_threshold(y_valid.to_numpy(), probability)
    prediction = probability >= threshold

    metrics = {
        "roc_auc": round(float(roc_auc_score(y_valid, probability)), 4),
        "pr_auc": round(float(average_precision_score(y_valid, probability)), 4),
        "precision": round(float(precision_score(y_valid, prediction, zero_division=0)), 4),
        "recall": round(float(recall_score(y_valid, prediction, zero_division=0)), 4),
        "f1": round(float(f1_score(y_valid, prediction, zero_division=0)), 4),
        "brier_score": round(float(brier_score_loss(y_valid, probability)), 4),
        "threshold": round(threshold, 4),
        "holdout_size": int(len(y_valid)),
        "holdout_default_rate": round(float(y_valid.mean()), 4),
        "training_rows": int(len(X_train)),
        "data_type": "generated_synthetic",
    }

    feature_names = list(preprocessor.get_feature_names_out())
    background = transformed_train[: min(400, len(transformed_train))]

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "preprocessor": preprocessor,
        "model": model,
        "threshold": threshold,
        "metrics": metrics,
        "feature_names": feature_names,
        "background": background,
        "raw_features": FEATURES,
        "numeric_features": NUMERIC,
        "categorical_features": CATEGORICAL,
    }, ARTIFACT_PATH)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
