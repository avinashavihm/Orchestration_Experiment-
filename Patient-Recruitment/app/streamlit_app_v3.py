import streamlit as st

from .pipeline_v3 import run_pipeline

st.set_page_config(page_title="Patients Eligibility – Version 3", layout="centered")
st.title("Patients Eligibility – Version 3")

with st.expander("Instructions", expanded=True):
    st.write(
        """
Upload the four inputs, then click **Run** to generate the Excel output with 4 sheets:

1) Protocol PDF  
2) Patients.xlsx (no Site_ID)  
3) Patient↔Site mapping.xlsx  
4) Site history.xlsx

Output sheets:
- Site Ranking
- Eligible Patients Roster
- All Patients Roster
- Extracted Criteria
"""
    )

with st.form("v3_form", clear_on_submit=False):
    pdf_file = st.file_uploader("Protocol PDF", type=["pdf"], accept_multiple_files=False)
    patients_file = st.file_uploader("Patients.xlsx (no Site_ID column)", type=["xlsx"], accept_multiple_files=False)
    mapping_file = st.file_uploader("Patient↔Site mapping.xlsx", type=["xlsx"], accept_multiple_files=False)
    site_hist_file = st.file_uploader("Site history.xlsx", type=["xlsx"], accept_multiple_files=False)

    submitted = st.form_submit_button("Run", type="primary")

if submitted:
    if not all([pdf_file, patients_file, mapping_file, site_hist_file]):
        st.error("Please upload all four files.")
        st.stop()

    with st.spinner("Processing..."):
        try:
            xlsx_bytes, meta = run_pipeline(
                pdf_bytes=pdf_file.read(),
                patients_xlsx=patients_file.read(),
                map_xlsx=mapping_file.read(),
                site_hist_xlsx=site_hist_file.read(),
            )
        except Exception as e:
            st.error(f"Run failed: {e}")
            st.stop()

    # Results
    st.success("Done! Download your results below.")
    st.download_button(
        label="Download XLSX results",
        data=xlsx_bytes,
        file_name="eligibility_results_v3.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # Optional summary
    if meta:
        st.subheader("Summary")
        counts = meta.get("counts", {})
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Patients", counts.get("patients", 0))
        col2.metric("Eligible = True", counts.get("eligible_true", 0))
        col3.metric("Inconclusive", counts.get("inconclusive", 0))

        if meta.get("errors"):
            st.warning("Some batches reported errors.")
            with st.expander("Show errors"):
                for e in meta["errors"]:
                    st.code(e)