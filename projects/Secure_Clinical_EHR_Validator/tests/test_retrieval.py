import unittest
from app.retrieval import list_patients, retrieve
from app.service import validate_grounding
from app.models import Evidence


class RetrievalTests(unittest.TestCase):
    def test_demo_patients_exist(self):
        self.assertIn("DEMO-1001", list_patients())

    def test_discharge_medication_retrieval(self):
        rows = retrieve("DEMO-1001", "What medication was recorded at discharge?", top_k=3)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["encounter"]["id"], "E1001-3")

    def test_patient_scope(self):
        rows = retrieve("DEMO-1002", "What liver diagnoses are documented?", top_k=3)
        self.assertTrue(all(row["encounter"]["id"].startswith("E1002-") for row in rows))

    def test_grounding_validator(self):
        evidence = [Evidence(encounter_id="E1", date="2026-01-01", score=1.0, text="Furosemide 40 mg oral daily was recorded at discharge.")]
        score, unsupported = validate_grounding("[E1] Furosemide 40 mg oral daily was recorded at discharge.", evidence)
        self.assertEqual(score, 1.0)
        self.assertEqual(unsupported, [])


if __name__ == "__main__":
    unittest.main()
