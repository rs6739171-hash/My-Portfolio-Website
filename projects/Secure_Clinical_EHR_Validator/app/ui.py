from __future__ import annotations

import os
import requests
import streamlit as st

from .config import settings

API_URL = os.getenv("API_URL", settings.api_url).rstrip("/")

st.set_page_config(page_title="Secure Clinical EHR Validator", page_icon="🛡️", layout="wide")

if settings.app_password:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("Secure Clinical EHR Insight Validator")
        entered = st.text_input("Demo password", type="password")
        if st.button("Enter demo", type="primary"):
            if entered == settings.app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect demo password")
        st.stop()

st.title("🛡️ Secure Clinical EHR Insight Validator")
st.caption("Synthetic-data clinical retrieval demo with patient scoping, safety guardrails, redaction, citations, and grounding validation.")
st.warning("Educational portfolio demo only — not a medical device, not HIPAA-certified, and not for real patient care.")

@st.cache_data(ttl=120)
def fetch_patients():
    r = requests.get(f"{API_URL}/api/v1/patients", timeout=8)
    r.raise_for_status()
    return r.json()["patients"]

try:
    patients = fetch_patients()
except Exception as exc:
    st.error(f"Backend unavailable: {exc}")
    st.stop()

with st.sidebar:
    st.subheader("Demo controls")
    patient_id = st.selectbox("Synthetic patient", patients)
    st.caption("Queries are explicitly scoped to this patient. Cross-patient enumeration requests are blocked.")
    st.divider()
    st.markdown("**Try:**")
    st.markdown("- What medications were recorded at discharge?\n- Summarize the last encounter.\n- What liver-related diagnoses are documented?\n- Was the admission urgent or routine?")
    st.markdown("**Blocked example:**")
    st.markdown("- What antibiotic should I prescribe?")

question = st.chat_input("Ask about the selected patient's recorded history...")
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Retrieving scoped evidence and validating the response..."):
            try:
                response = requests.post(
                    f"{API_URL}/api/v1/query",
                    json={"patient_id": patient_id, "question": question},
                    timeout=35,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                st.error(f"Request failed: {exc}")
                st.stop()

        st.write(data["answer"])
        st.caption(data["disclaimer"])
        cols = st.columns(4)
        cols[0].metric("Status", data["status"])
        cols[1].metric("Mode", data["mode"])
        cols[2].metric("Grounding", f"{data['support_score']*100:.0f}%")
        cols[3].metric("Safety", data["safety"]["category"])

        with st.expander("Why this request was allowed or blocked"):
            st.write(data["safety"]["reason"])
        with st.expander("Retrieved evidence"):
            if data["evidence"]:
                for item in data["evidence"]:
                    st.markdown(f"**{item['encounter_id']} · {item['date']} · score {item['score']:.3f}**")
                    st.write(item["text"])
            else:
                st.write("No evidence returned.")
        if data["unsupported_claims"]:
            with st.expander("Validator flags"):
                for claim in data["unsupported_claims"]:
                    st.write("•", claim)
