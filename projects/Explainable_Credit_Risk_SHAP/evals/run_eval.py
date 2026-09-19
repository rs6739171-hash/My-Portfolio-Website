from __future__ import annotations

import json

from app.model_service import get_model
from app.schema import LoanApplication


CASES = [
    LoanApplication(
        person_age=45, person_income=140000, person_home_ownership="OWN",
        person_emp_length=15, loan_intent="HOMEIMPROVEMENT", loan_grade="A",
        loan_amnt=5000, loan_int_rate=6.0, loan_percent_income=0.0357,
        cb_person_default_on_file="N", cb_person_cred_hist_length=20,
    ),
    LoanApplication(
        person_age=35, person_income=70000, person_home_ownership="MORTGAGE",
        person_emp_length=7, loan_intent="PERSONAL", loan_grade="C",
        loan_amnt=12000, loan_int_rate=11.5, loan_percent_income=0.1714,
        cb_person_default_on_file="N", cb_person_cred_hist_length=9,
    ),
    LoanApplication(
        person_age=27, person_income=30000, person_home_ownership="RENT",
        person_emp_length=2, loan_intent="DEBTCONSOLIDATION", loan_grade="G",
        loan_amnt=19000, loan_int_rate=24.0, loan_percent_income=0.6333,
        cb_person_default_on_file="Y", cb_person_cred_hist_length=4,
    ),
]


def main():
    model = get_model()
    results = [model.score(case) for case in CASES]
    probabilities = [row["default_probability"] for row in results]

    summary = {
        "probabilities": probabilities,
        "ordered_risk_check": probabilities[0] < probabilities[1] < probabilities[2],
        "explanations_present": all(len(row["top_drivers"]) >= 4 for row in results),
        "metrics": model.metrics,
    }
    summary["passed"] = summary["ordered_risk_check"] and summary["explanations_present"]

    print(json.dumps(summary, indent=2))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
