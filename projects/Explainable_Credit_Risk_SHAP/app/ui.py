from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st


API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(
    page_title="Explainable Credit Risk · SHAP",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Explainable Credit Risk Assessment")
st.caption("Synthetic ML demo with probability scoring, SHAP reason codes, model metrics, and what-if analysis.")
st.warning("Portfolio demonstration only — not a lending product and not for real underwriting or credit decisions.")


@st.cache_data(ttl=300)
def model_card():
    response = requests.get(f"{API_URL}/api/v1/model-card", timeout=10)
    response.raise_for_status()
    return response.json()


try:
    card = model_card()
except Exception as exc:
    st.error(f"Backend unavailable: {exc}")
    st.stop()

metrics = card["metrics"]
metric_cols = st.columns(5)
metric_cols[0].metric("ROC-AUC", f"{metrics['roc_auc']:.3f}")
metric_cols[1].metric("PR-AUC", f"{metrics['pr_auc']:.3f}")
metric_cols[2].metric("F1", f"{metrics['f1']:.3f}")
metric_cols[3].metric("Recall", f"{metrics['recall']:.3f}")
metric_cols[4].metric("Threshold", f"{metrics['threshold']:.3f}")

st.divider()
st.subheader("Score a synthetic application")

left, right = st.columns(2)
with left:
    age = st.slider("Age", 21, 70, 34)
    income = st.number_input("Annual income", min_value=18000.0, max_value=300000.0, value=65000.0, step=1000.0)
    home = st.selectbox("Home ownership", ["RENT", "MORTGAGE", "OWN", "OTHER"])
    emp = st.slider("Employment length (years)", 0.0, float(max(age - 18, 0)), min(6.0, float(max(age - 18, 0))), step=0.5)
    credit_hist = st.slider("Credit history length (years)", 2, max(2, age - 18), min(8, max(2, age - 18)))

with right:
    intent = st.selectbox("Loan intent", ["PERSONAL", "DEBTCONSOLIDATION", "EDUCATION", "MEDICAL", "HOMEIMPROVEMENT", "VENTURE"])
    grade = st.selectbox("Loan grade", ["A", "B", "C", "D", "E", "F", "G"], index=1)
    amount = st.number_input("Loan amount", min_value=1000.0, max_value=40000.0, value=10000.0, step=500.0)
    rate = st.slider("Interest rate (%)", 4.0, 29.0, 10.5, 0.1)
    prior_default = st.selectbox("Prior default on file", ["N", "Y"])
    pct_income = min(amount / max(income, 1), 0.75)
    st.metric("Loan / income ratio", f"{pct_income:.1%}")

payload = {
    "person_age": age,
    "person_income": income,
    "person_home_ownership": home,
    "person_emp_length": emp,
    "loan_intent": intent,
    "loan_grade": grade,
    "loan_amnt": amount,
    "loan_int_rate": rate,
    "loan_percent_income": pct_income,
    "cb_person_default_on_file": prior_default,
    "cb_person_cred_hist_length": credit_hist,
}

if st.button("Score & explain", type="primary", use_container_width=True):
    try:
        response = requests.post(f"{API_URL}/api/v1/score", json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
    except Exception as exc:
        st.error(f"Scoring failed: {exc}")
        st.stop()

    st.session_state["latest_score"] = result
    st.session_state["baseline_payload"] = payload

if "latest_score" in st.session_state:
    result = st.session_state["latest_score"]
    st.divider()
    a, b, c = st.columns(3)
    a.metric("Estimated default probability", f"{result['default_probability']:.1%}")
    b.metric("Risk tier", result["risk_tier"].title())
    c.metric("Review threshold", f"{result['review_threshold']:.1%}")

    st.subheader("Top SHAP drivers")
    drivers = pd.DataFrame(result["top_drivers"])
    display = drivers[["feature", "value", "shap_value", "direction"]].copy()
    st.dataframe(display, use_container_width=True, hide_index=True)

    chart = drivers[["feature", "shap_value"]].set_index("feature")
    st.bar_chart(chart)
    st.caption(result["explanation_space"])

    with st.expander("What-if scenario"):
        baseline = st.session_state["baseline_payload"]
        scenario_amount = st.slider(
            "Scenario loan amount",
            1000.0,
            40000.0,
            float(baseline["loan_amnt"]),
            500.0,
        )
        scenario_rate = st.slider(
            "Scenario interest rate (%)",
            4.0,
            29.0,
            float(baseline["loan_int_rate"]),
            0.1,
        )
        scenario_grade = st.selectbox(
            "Scenario loan grade",
            ["A", "B", "C", "D", "E", "F", "G"],
            index=["A", "B", "C", "D", "E", "F", "G"].index(baseline["loan_grade"]),
            key="scenario_grade",
        )

        if st.button("Compare scenario"):
            scenario_payload = dict(baseline)
            scenario_payload["loan_amnt"] = scenario_amount
            scenario_payload["loan_int_rate"] = scenario_rate
            scenario_payload["loan_grade"] = scenario_grade
            scenario_payload["loan_percent_income"] = min(scenario_amount / max(baseline["person_income"], 1), 0.75)
            try:
                response = requests.post(
                    f"{API_URL}/api/v1/scenario",
                    json={"baseline": baseline, "scenario": scenario_payload},
                    timeout=20,
                )
                response.raise_for_status()
                scenario = response.json()
            except Exception as exc:
                st.error(f"Scenario analysis failed: {exc}")
            else:
                x, y, z = st.columns(3)
                x.metric("Baseline", f"{scenario['baseline_probability']:.1%}")
                y.metric("Scenario", f"{scenario['scenario_probability']:.1%}")
                z.metric("Probability change", f"{scenario['probability_delta']:+.1%}")
                st.caption("Scenario changes are model sensitivity, not causal effects.")

with st.expander("Model card & responsible-use notes"):
    st.json(card)
