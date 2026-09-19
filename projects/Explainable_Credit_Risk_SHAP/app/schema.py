from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator


HomeOwnership = Literal["RENT", "MORTGAGE", "OWN", "OTHER"]
LoanIntent = Literal["EDUCATION", "MEDICAL", "VENTURE", "PERSONAL", "HOMEIMPROVEMENT", "DEBTCONSOLIDATION"]
LoanGrade = Literal["A", "B", "C", "D", "E", "F", "G"]
DefaultFlag = Literal["N", "Y"]


class LoanApplication(BaseModel):
    person_age: int = Field(ge=18, le=100)
    person_income: float = Field(gt=0, le=2_000_000)
    person_home_ownership: HomeOwnership
    person_emp_length: float = Field(ge=0, le=80)
    loan_intent: LoanIntent
    loan_grade: LoanGrade
    loan_amnt: float = Field(gt=0, le=1_000_000)
    loan_int_rate: float = Field(ge=0, le=100)
    loan_percent_income: float = Field(gt=0, le=2)
    cb_person_default_on_file: DefaultFlag
    cb_person_cred_hist_length: int = Field(ge=0, le=80)

    @model_validator(mode="after")
    def validate_relationships(self):
        if self.person_emp_length > max(self.person_age - 16, 0):
            raise ValueError("Employment length cannot exceed plausible working years for the supplied age.")
        if self.cb_person_cred_hist_length > max(self.person_age - 16, 0):
            raise ValueError("Credit-history length cannot exceed plausible adult credit years for the supplied age.")
        return self


class ScenarioRequest(BaseModel):
    baseline: LoanApplication
    scenario: LoanApplication
