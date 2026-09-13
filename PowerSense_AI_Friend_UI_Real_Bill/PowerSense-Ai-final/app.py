import os
import streamlit as st

from rag_utils import (
    GROQ_MODEL,
    extract_bill_text,
    build_or_load_vectorstore,
    retrieve_relevant_chunks,
    extract_bill_fields_with_llm,
    analyze_and_verify_bill,
    generate_complaint_package,
)

NEPRA_COMPLAINT_URL = "https://www.nepra.org.pk/Complaint.php"
DISCOS = ["Auto-detect", "FESCO", "LESCO", "GEPCO", "MEPCO", "IESCO", "PESCO", "HESCO", "SEPCO", "QESCO", "K-Electric", "Other"]
CONSUMER_CATEGORIES = ["Residential", "Commercial", "Industrial", "Other"]
LANGUAGES = ["English", "Urdu", "Roman Urdu"]
DISCLAIMER = ("PowerSense AI provides informational bill analysis based on the uploaded bill and "
              "available official reference documents. It does not replace official tariff "
              "determinations or legal advice. Charges marked for verification should be confirmed "
              "with the relevant electricity provider or regulatory authority.")
STATUS_ICONS = {"Explained":"🟢", "Applicable":"🟢", "Requires Verification":"🟡", "Potential Billing Issue":"🔴"}

st.set_page_config(page_title="PowerSense AI", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
#MainMenu, footer {visibility:hidden;}
.stApp {background: radial-gradient(circle at 10% 0%, rgba(99,102,241,.10), transparent 28%), radial-gradient(circle at 90% 10%, rgba(16,185,129,.08), transparent 25%);}
.ps-header{padding:.25rem 0 1rem;border-bottom:1px solid rgba(128,128,128,.2);margin-bottom:1.2rem}
.ps-title{font-size:2rem;font-weight:750;margin:0}.ps-subtitle{color:#8a8f98;margin-top:2px}
.kpi{border:1px solid rgba(128,128,128,.18);border-radius:15px;padding:1rem;background:rgba(128,128,128,.05);height:100%}
.kpi-label{font-size:.78rem;color:#8a8f98}.kpi-value{font-size:1.5rem;font-weight:750;margin-top:3px}
.card{border:1px solid rgba(128,128,128,.18);border-radius:14px;padding:1rem 1.1rem;background:rgba(128,128,128,.04);margin-bottom:.8rem}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:.78rem;font-weight:650;margin-right:4px}
.green{background:rgba(16,185,129,.14);color:#10b981}.yellow{background:rgba(234,179,8,.14);color:#ca8a04}.red{background:rgba(239,68,68,.14);color:#ef4444}
.disclaimer{border-left:3px solid #eab308;background:rgba(234,179,8,.07);padding:.75rem;border-radius:8px;color:#c9c9c9;font-size:.82rem}
</style>
""", unsafe_allow_html=True)

def init():
    for k,v in {"bill_text":"","bill_data":None,"analysis":None,"complaint":None,"context_chunks":[],"signature":"","errors":[],"page":"🏠 Dashboard"}.items():
        st.session_state.setdefault(k,v)
init()

api_key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))

with st.sidebar:
    st.markdown("## ⚡ PowerSense AI")
    st.caption("Electricity Bill Transparency & Complaint Assistant")
    st.markdown(f'<div class="disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)
    st.markdown("### Navigation")
    pages=["🏠 Dashboard","🧾 Bill Analyzer","📊 Bill Breakdown","⚠️ Attention","💡 Why Is My Bill High?","📢 Complaint Assistant","📚 Sources","ℹ️ About"]
    st.session_state.page=st.radio("",pages,index=pages.index(st.session_state.page),label_visibility="collapsed")
    st.divider()
    st.caption(f"AI model: `{GROQ_MODEL}`")
    if not api_key:
        st.warning("GROQ_API_KEY is not configured. Add it in Streamlit Secrets to run AI extraction and analysis.")

page=st.session_state.page

if page=="🏠 Dashboard":
    st.markdown('<div class="ps-header"><div class="ps-title">⚡ PowerSense AI</div><div class="ps-subtitle">Understand your electricity bill clearly — from the bill you actually upload.</div></div>',unsafe_allow_html=True)
    data=st.session_state.bill_data
    analysis=st.session_state.analysis
    if not data or not analysis:
        st.info("Upload an electricity bill to activate your real bill dashboard. No demo bill or synthetic values are used.")
        a,b,c=st.columns(3)
        a.markdown('<div class="kpi"><div class="kpi-label">STEP 1</div><div class="kpi-value">Upload Bill</div><div>PDF, JPG, JPEG or PNG</div></div>',unsafe_allow_html=True)
        b.markdown('<div class="kpi"><div class="kpi-label">STEP 2</div><div class="kpi-value">AI + RAG</div><div>Extract, retrieve and verify</div></div>',unsafe_allow_html=True)
        c.markdown('<div class="kpi"><div class="kpi-label">STEP 3</div><div class="kpi-value">Get Answers</div><div>Breakdown, issues and complaint help</div></div>',unsafe_allow_html=True)
    else:
        s=analysis.get("bill_summary",{})
        c1,c2,c3,c4=st.columns(4)
        vals=[("Provider",s.get("provider") or data.get("provider") or "—"),("Billing Month",s.get("billing_month") or data.get("billing_month") or "—"),("Units",s.get("units_consumed") if s.get("units_consumed") is not None else data.get("units_consumed") or "—"),("Amount Payable",s.get("total_bill") if s.get("total_bill") is not None else data.get("amount_payable") or "—")]
        for col,(lab,val) in zip([c1,c2,c3,c4],vals): col.markdown(f'<div class="kpi"><div class="kpi-label">{lab}</div><div class="kpi-value">{val}</div></div>',unsafe_allow_html=True)
        st.write("")
        st.success("This dashboard is populated from the uploaded bill and the completed AI analysis.")
        if data.get("previous_reading") is not None and data.get("current_reading") is not None:
            diff=float(data["current_reading"])-float(data["previous_reading"])
            st.metric("Reading Difference",f"{diff:g} units")

elif page=="🧾 Bill Analyzer":
    st.markdown(
        '<div class="ps-header">'
        '<div class="ps-title">🧾 Bill Analyzer</div>'
        '<div class="ps-subtitle">Upload your electricity bill and PowerSense AI will automatically perform the complete analysis.</div>'
        '</div>',
        unsafe_allow_html=True
    )

    provider_choice = st.selectbox(
        "Electricity Provider / DISCO",
        DISCOS,
        index=0
    )

    category = st.selectbox(
        "Consumer Category",
        CONSUMER_CATEGORIES,
        index=0
    )

    language = st.selectbox(
        "Response Language",
        LANGUAGES,
        index=0
    )

    question = st.text_area(
        "Your question (optional)",
        placeholder="Why is my bill high? Explain the extra charges.",
        height=80
    )

    uploaded = st.file_uploader(
        "Upload your electricity bill",
        type=["jpg", "jpeg", "png", "pdf"]
    )

    # ==========================================================
    # COMPLETE AUTOMATIC WORKFLOW
    # Upload itself starts the complete PowerSense AI pipeline
    # ==========================================================

    if uploaded:

        sig = f"{uploaded.name}:{uploaded.size}"

        # Run only when a NEW bill is uploaded
        if sig != st.session_state.signature:

            st.session_state.signature = sig
            st.session_state.analysis = None
            st.session_state.complaint = None
            st.session_state.context_chunks = []
            st.session_state.bill_data = None
            st.session_state.errors = []

            # --------------------------------------------------
            # STEP 1 — READ BILL
            # --------------------------------------------------
            with st.status(
                "⚡ PowerSense AI is analyzing your bill...",
                expanded=True
            ) as status:

                st.write("📄 Reading uploaded bill...")

                text = extract_bill_text(uploaded)

                st.session_state.bill_text = text

                if not text or len(text.strip()) < 15:

                    status.update(
                        label="❌ Bill could not be read",
                        state="error",
                        expanded=True
                    )

                    st.error(
                        "PowerSense AI could not confidently read this bill. "
                        "Please upload a clearer image/PDF. "
                        "No demo data will be inserted."
                    )

                    st.session_state.bill_data = None

                elif not api_key:

                    status.update(
                        label="⚠️ Groq API key required",
                        state="error",
                        expanded=True
                    )

                    st.warning(
                        "The bill was successfully read, but "
                        "GROQ_API_KEY is required for AI extraction and analysis."
                    )

                    st.session_state.bill_data = None

                else:

                    # --------------------------------------------------
                    # STEP 2 — BILL EXTRACTION AGENT
                    # --------------------------------------------------
                    st.write(
                        "🤖 Bill Extraction Agent is extracting actual bill values..."
                    )

                    bill_data = extract_bill_fields_with_llm(
                        api_key,
                        text
                    )

                    st.session_state.bill_data = bill_data

                    if not bill_data:

                        status.update(
                            label="❌ Bill extraction failed",
                            state="error",
                            expanded=True
                        )

                        st.error(
                            "PowerSense AI could not extract the bill details "
                            "confidently. Please upload a clearer bill."
                        )

                    else:

                        # --------------------------------------------------
                        # STEP 3 — RAG KNOWLEDGE RETRIEVAL
                        # --------------------------------------------------
                        st.write(
                            "📚 RAG Agent is checking official/reference knowledge..."
                        )

                        query = (
                            f"{bill_data.get('provider') or provider_choice} "
                            f"{bill_data.get('tariff_category') or ''} "
                            f"tariff "
                            f"units {bill_data.get('units_consumed') or ''} "
                            f"FCA QTA taxes surcharges "
                            f"electricity bill verification "
                            f"{question}"
                        )

                        try:
                            vectorstore = build_or_load_vectorstore()

                            chunks = retrieve_relevant_chunks(
                                query,
                                vectorstore
                            )

                            st.session_state.context_chunks = chunks

                        except Exception as e:

                            st.session_state.context_chunks = []

                            st.warning(
                                f"Knowledge-base retrieval could not be completed: {e}"
                            )

                        # --------------------------------------------------
                        # STEP 4 — BILL VERIFICATION + AI ANALYSIS
                        # --------------------------------------------------
                        st.write(
                            "🔍 Verification Agents are checking charges and consumption..."
                        )

                        resolved_provider = (
                            bill_data.get("provider")
                            if provider_choice == "Auto-detect"
                            else provider_choice
                        )

                        result = analyze_and_verify_bill(
                            api_key,
                            bill_data,
                            resolved_provider or "Unknown",
                            category,
                            language,
                            st.session_state.context_chunks
                        )

                        if result:

                            st.session_state.analysis = result

                            # --------------------------------------------------
                            # STEP 5 — AUTOMATIC COMPLAINT PACKAGE
                            # --------------------------------------------------
                            st.write(
                                "📢 Complaint Assistant is preparing guidance..."
                            )

                            try:

                                complaint = generate_complaint_package(
                                    api_key,
                                    bill_data,
                                    result,
                                    resolved_provider or "Unknown",
                                    language
                                )

                                st.session_state.complaint = complaint

                            except Exception as e:

                                st.session_state.complaint = None

                                st.warning(
                                    f"Complaint package could not be generated: {e}"
                                )

                            status.update(
                                label="✅ Complete Bill Analysis Finished",
                                state="complete",
                                expanded=False
                            )

                        else:

                            status.update(
                                label="❌ AI analysis failed",
                                state="error",
                                expanded=True
                            )

                            st.error(
                                "AI analysis failed. Please check your "
                                "Groq API key/model availability."
                            )

        # ----------------------------------------------------------
        # SHOW UPLOADED BILL
        # ----------------------------------------------------------

        if uploaded.type.startswith("image"):
            st.image(
                uploaded,
                caption="Uploaded electricity bill",
                use_container_width=True
            )

        # ----------------------------------------------------------
        # SHOW EXTRACTED TEXT
        # ----------------------------------------------------------

        if st.session_state.bill_text:

            with st.expander("🔎 View Extracted Bill Text"):
                st.text(
                    st.session_state.bill_text[:8000]
                )

        # ----------------------------------------------------------
        # SHOW ACTUAL EXTRACTED BILL DATA
        # ----------------------------------------------------------

        data = st.session_state.bill_data

        if data:

            st.success(
                "✅ Bill uploaded and processed successfully. "
                "All results below are based on this uploaded bill."
            )

            st.subheader("📋 Extracted Bill Information")

            preview_fields = [
                ("Provider", "provider"),
                ("Billing Month", "billing_month"),
                ("Previous Reading", "previous_reading"),
                ("Current Reading", "current_reading"),
                ("Units Consumed", "units_consumed"),
                ("Amount Payable", "amount_payable"),
                ("Tariff Category", "tariff_category"),
            ]

            cols = st.columns(4)

            for i, (label, field) in enumerate(preview_fields):

                value = data.get(field)

                if value is None or value == "":
                    value = "—"

                cols[i % 4].metric(
                    label,
                    value
                )

            # ------------------------------------------------------
            # AUTOMATIC RESULT SUMMARY
            # ------------------------------------------------------

            analysis = st.session_state.analysis

            if analysis:

                st.divider()

                st.subheader("⚡ Analysis Complete")

                summary = analysis.get(
                    "bill_summary",
                    {}
                )

                c1, c2, c3, c4 = st.columns(4)

                c1.metric(
                    "Provider",
                    summary.get("provider")
                    or data.get("provider")
                    or "—"
                )

                c2.metric(
                    "Billing Month",
                    summary.get("billing_month")
                    or data.get("billing_month")
                    or "—"
                )

                c3.metric(
                    "Units",
                    summary.get("units_consumed")
                    if summary.get("units_consumed") is not None
                    else data.get("units_consumed")
                    or "—"
                )

                c4.metric(
                    "Amount Payable",
                    summary.get("total_bill")
                    if summary.get("total_bill") is not None
                    else data.get("amount_payable")
                    or "—"
                )

                st.success(
                    "🎯 Your complete bill analysis is ready. "
                    "Use the sidebar to view Bill Breakdown, Attention Items, "
                    "Why Your Bill Is High, Complaint Assistant and Sources."
                )
elif page=="📊 Bill Breakdown":
    st.markdown('<div class="ps-header"><div class="ps-title">📊 Bill Breakdown</div><div class="ps-subtitle">Actual values extracted from your uploaded bill.</div></div>',unsafe_allow_html=True)
    a=st.session_state.analysis
    if not a: st.info("Run analysis after uploading a bill.")
    else:
        s=a.get("bill_summary",{}); d=st.session_state.bill_data or {}
        c1,c2,c3,c4=st.columns(4)
        for col,lab,val in zip([c1,c2,c3,c4],["Provider","Billing Month","Units","Total Bill"],[s.get("provider") or d.get("provider") or "—",s.get("billing_month") or d.get("billing_month") or "—",s.get("units_consumed") if s.get("units_consumed") is not None else d.get("units_consumed") or "—",s.get("total_bill") if s.get("total_bill") is not None else d.get("amount_payable") or "—"]): col.metric(lab,val)
        st.caption(f"Due date: {s.get('due_date') or d.get('due_date') or '—'}")
        rows=a.get("charge_breakdown",[])
        if rows:
            st.dataframe([{ "Component":r.get("component"),"Amount (PKR)":r.get("amount"),"Status":f"{STATUS_ICONS.get(r.get('status',''),'')} {r.get('status','—')}","Explanation":r.get("explanation","—")} for r in rows],use_container_width=True,hide_index=True)
        cons=a.get("consumption_analysis",{})
        if cons:
            x,y,z,w=st.columns(4); x.metric("Previous Units",cons.get("previous_units") or "—"); y.metric("Current Units",cons.get("current_units") or "—"); z.metric("Difference",cons.get("difference") or "—"); w.metric("% Change",cons.get("percent_change") or "—"); st.caption(cons.get("note",""))

elif page=="⚠️ Attention":
    st.title("⚠️ Charges That Need Your Attention")
    a=st.session_state.analysis
    if not a: st.info("Run analysis first.")
    else:
        items=a.get("attention_items",[])
        if not items: st.success("🟢 No charges were flagged as unclear or requiring verification.")
        for item in items:
            icon=STATUS_ICONS.get(item.get("status"),"🟡")
            with st.expander(f"{icon} {item.get('charge_name','Unknown')} — PKR {item.get('amount','—')}"):
                st.write(f"**Status:** {item.get('status','—')}"); st.write(f"**Why flagged:** {item.get('flag_reason','—')}"); st.write(f"**Source:** {item.get('source_used') or 'No specific source matched'}"); st.write(f"**Verify:** {item.get('what_to_verify','—')}")

elif page=="💡 Why Is My Bill High?":
    st.title("💡 Why Is My Bill High?")
    a=st.session_state.analysis
    if not a: st.info("Run analysis first.")
    else: st.write(a.get("why_bill_is_high","No explanation was generated."))

elif page=="📢 Complaint Assistant":
    st.title("📢 Complaint Assistant")
    a=st.session_state.analysis; d=st.session_state.bill_data
    if not a or not d: st.info("Run analysis first so the complaint assistant has the actual bill context.")
    else:
        if st.button("📢 Prepare Complaint Package",type="primary"):
            if not api_key: st.error("GROQ_API_KEY is required.")
            else:
                with st.spinner("Complaint Assistant Agent is preparing your package..."):
                    provider=d.get("provider") or "Unknown"
                    st.session_state.complaint=generate_complaint_package(api_key,d,a,provider,"English")
        c=st.session_state.complaint
        if c:
            st.subheader("Should you consider a complaint?"); st.write("Yes" if c.get("should_consider_complaint") else "Not clearly necessary right now"); st.write(c.get("reason_summary",""))
            st.subheader("Likely Complaint Category"); st.write(c.get("likely_complaint_category","—"))
            st.subheader("Evidence to Keep"); [st.write("- "+x) for x in c.get("evidence_to_keep",[])]
            st.subheader("Draft Complaint"); st.text_area("Editable draft",value=c.get("draft_complaint_text", ""),height=160)
            st.subheader("Provider First"); st.write(c.get("contact_provider_first_note","Contact the relevant electricity provider first where appropriate."))
            st.link_button("🔗 Open Official NEPRA Complaint Portal",NEPRA_COMPLAINT_URL)

elif page=="📚 Sources":
    st.title("📚 Sources Used")
    chunks=st.session_state.context_chunks
    a=st.session_state.analysis
    sources=set(a.get("sources_used",[]) if a else [])
    sources.update(c.get("source") for c in chunks if c.get("source"))
    if not sources: st.warning("No knowledge-base sources were retrieved for the current analysis.")
    else:
        for s in sorted(sources): st.write("📄 "+s)
    with st.expander("Retrieved context"):
        for c in chunks: st.markdown(f"**{c.get('source','Source')}**\n\n{c.get('text','')[:700]}\n\n---")

elif page=="ℹ️ About":
    st.title("ℹ️ About PowerSense AI")
    st.markdown("""**PowerSense AI** is a Pakistan-focused hackathon project for electricity-bill transparency.

**Workflow:** Upload a real bill → OCR/PDF extraction → Bill Extraction Agent → RAG/FAISS retrieval → Groq analysis → charge verification → high-bill explanation → complaint assistance.

**Important:** The app does not use a demo bill, synthetic consumption history, or fabricated tariff rate. If a value cannot be confidently extracted from the uploaded bill, it remains unavailable and should be corrected by the user rather than invented.
""")
    st.markdown(f'<div class="disclaimer">{DISCLAIMER}</div>',unsafe_allow_html=True)
