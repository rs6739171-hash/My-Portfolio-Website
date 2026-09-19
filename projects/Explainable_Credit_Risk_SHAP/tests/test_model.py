import unittest

from app.model_service import get_model
from app.schema import LoanApplication


def low_profile():
    return LoanApplication(
        person_age=42,
        person_income=120000,
        person_home_ownership="OWN",
        person_emp_length=12,
        loan_intent="HOMEIMPROVEMENT",
        loan_grade="A",
        loan_amnt=5000,
        loan_int_rate=6.5,
        loan_percent_income=0.0417,
        cb_person_default_on_file="N",
        cb_person_cred_hist_length=18,
    )


def high_profile():
    return LoanApplication(
        person_age=28,
        person_income=32000,
        person_home_ownership="RENT",
        person_emp_length=2,
        loan_intent="DEBTCONSOLIDATION",
        loan_grade="F",
        loan_amnt=18000,
        loan_int_rate=21.0,
        loan_percent_income=0.5625,
        cb_person_default_on_file="Y",
        cb_person_cred_hist_length=4,
    )


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = get_model()

    def test_threshold_valid(self):
        self.assertGreater(self.model.threshold, 0)
        self.assertLess(self.model.threshold, 1)

    def test_explanation_present(self):
        result = self.model.score(low_profile())
        self.assertGreaterEqual(len(result["top_drivers"]), 4)
        self.assertTrue(all("shap_value" in row for row in result["top_drivers"]))

    def test_high_profile_scores_higher(self):
        low = self.model.score(low_profile())["default_probability"]
        high = self.model.score(high_profile())["default_probability"]
        self.assertGreater(high, low)

    def test_protected_attributes_absent(self):
        forbidden = {"gender", "sex", "race", "religion", "marital_status", "disability"}
        self.assertTrue(forbidden.isdisjoint(set(self.model.raw_features)))


if __name__ == "__main__":
    unittest.main()
