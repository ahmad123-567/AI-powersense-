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

# ============================================================
# CONFIG
# ============================================================

NEPRA_COMPLAINT_URL = "https://www.nepra.org.pk/Complaint.php"

DISCOS = [
    "Auto-detect",
    "FESCO",
    "LESCO",
    "GEPCO",
    "MEPCO",
    "IESCO",
    "PESCO",
    "HESCO",
    "SEPCO",
    "QESCO",
    "K-Electric",
    "Other",
]

CONSUMER_CATEGORIES = [
    "Residential",
    "Commercial",
    "Industrial",
    "Other",
]

LANGUAGES = [
    "English",
    "Urdu",
    "Roman Urdu",
]

DISCLAIMER = (
    "PowerSense AI provides informational bill analysis based on the uploaded bill "
    "and available official reference documents. It does not replace official tariff "
    "determinations or legal advice. Charges marked for verification should be confirmed "
    "with the relevant electricity provider or regulatory authority."
)

STATUS_ICONS = {
    "Explained": "🟢",
    "Applicable": "🟢",
    "Requires Verification": "🟡",
    "Potential Billing Issue": "🔴",
}

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="PowerSense AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>
    #MainMenu, footer {
        visibility: hidden;
    }

    .stApp {
        background:
        radial-gradient(
            circle at 10% 0%,
            rgba(99,102,241,.10),
            transparent 28%
        ),
        radial-gradient(
            circle at 90% 10%,
            rgba(16,185,129,.08),
            transparent 25%
        );
    }

    .ps-header {
        padding: .25rem 0 1rem;
        border-bottom: 1px solid rgba(128,128,128,.2);
        margin-bottom: 1.2rem;
    }

    .ps-title {
        font-size: 2rem;
        font-weight: 750;
        margin: 0;
    }

    .ps-subtitle {
        color: #8a8f98;
        margin-top: 2px;
    }

    .kpi {
        border: 1px solid rgba(128,128,128,.18);
        border-radius: 15px;
        padding: 1rem;
        background: rgba(128,128,128,.05);
        height: 100%;
    }

    .kpi-label {
        font-size: .78rem;
        color: #8a8f98;
    }

    .kpi-value {
        font-size: 1.5rem;
        font-weight: 750;
        margin-top: 3px;
    }

    .card {
        border: 1px solid rgba(128,128,128,.18);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        background: rgba(128,128,128,.04);
        margin-bottom: .8rem;
    }

    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: .78rem;
        font-weight: 650;
        margin-right: 4px;
    }

    .green {
        background: rgba(16,185,129,.14);
        color: #10b981;
    }

    .yellow {
        background: rgba(234,179,8,.14);
        color: #ca8a04;
    }

    .red {
        background: rgba(239,68,68,.14);
        color: #ef4444;
    }

    .disclaimer {
        border-left: 3px solid #eab308;
        background: rgba(234,179,8,.07);
        padding: .75rem;
        border-radius: 8px;
        color: #c9c9c9;
        font-size: .82rem;
    }

    .success-box {
        border: 1px solid rgba(16,185,129,.3);
        background: rgba(16,185,129,.08);
        padding: 1rem;
        border-radius: 12px;
        margin: 1rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# SESSION STATE
# ============================================================

def init():
    defaults = {
        "bill_text": "",
        "bill_data": None,
        "analysis": None,
        "complaint": None,
        "context_chunks": [],
        "signature": "",
        "errors": [],
        "page": "🏠 Dashboard",
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


init()

# ============================================================
# API KEY
# ============================================================

api_key = st.secrets.get(
    "GROQ_API_KEY",
    os.getenv("GROQ_API_KEY", "")
)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## ⚡ PowerSense AI")

    st.caption(
        "Electricity Bill Transparency & Complaint Assistant"
    )

    st.markdown(
        f'<div class="disclaimer">{DISCLAIMER}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Navigation")

    pages = [
        "🏠 Dashboard",
        "🧾 Bill Analyzer",
        "📊 Bill Breakdown",
        "⚠️ Attention",
        "💡 Why Is My Bill High?",
        "📢 Complaint Assistant",
        "📚 Sources",
        "ℹ️ About",
    ]

    st.session_state.page = st.radio(
        "",
        pages,
        index=pages.index(st.session_state.page),
        label_visibility="collapsed",
    )

    st.divider()

    st.caption(f"AI model: `{GROQ_MODEL}`")

    if not api_key:
        st.warning(
            "GROQ_API_KEY is not configured. "
            "Add it in Streamlit Secrets to run AI extraction and analysis."
        )

page = st.session_state.page

# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":

    st.markdown(
        """
        <div class="ps-header">
            <div class="ps-title">⚡ PowerSense AI</div>
            <div class="ps-subtitle">
                Understand your electricity bill clearly —
                from the bill you actually upload.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    data = st.session_state.bill_data
    analysis = st.session_state.analysis

    if not data or not analysis:

        st.info(
            "Upload an electricity bill from the Bill Analyzer page "
            "to activate your real bill dashboard. "
            "No demo bill or synthetic values are used."
        )

        a, b, c = st.columns(3)

        a.markdown(
            """
            <div class="kpi">
                <div class="kpi-label">STEP 1</div>
                <div class="kpi-value">Upload Bill</div>
                <div>PDF, JPG, JPEG or PNG</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        b.markdown(
            """
            <div class="kpi">
                <div class="kpi-label">STEP 2</div>
                <div class="kpi-value">AI + RAG</div>
                <div>Extract, retrieve and verify</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c.markdown(
            """
            <div class="kpi">
                <div class="kpi-label">STEP 3</div>
                <div class="kpi-value">Get Answers</div>
                <div>Breakdown, issues and complaint help</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        s = analysis.get("bill_summary", {})

        c1, c2, c3, c4 = st.columns(4)

        vals = [
            (
                "Provider",
                s.get("provider")
                or data.get("provider")
                or "—",
            ),
            (
                "Billing Month",
                s.get("billing_month")
                or data.get("billing_month")
                or "—",
            ),
            (
                "Units",
                s.get("units_consumed")
                if s.get("units_consumed") is not None
                else data.get("units_consumed")
                or "—",
            ),
            (
                "Amount Payable",
                s.get("total_bill")
                if s.get("total_bill") is not None
                else data.get("amount_payable")
                or "—",
            ),
        ]

        for col, (lab, val) in zip(
            [c1, c2, c3, c4],
            vals,
        ):
            col.markdown(
                f"""
                <div class="kpi">
                    <div class="kpi-label">{lab}</div>
                    <div class="kpi-value">{val}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")

        st.success(
            "This dashboard is populated from the uploaded bill "
            "and the completed AI analysis."
        )

        if (
            data.get("previous_reading") is not None
            and data.get("current_reading") is not None
        ):

            try:

                diff = (
                    float(data["current_reading"])
                    - float(data["previous_reading"])
                )

                st.metric(
                    "Reading Difference",
                    f"{diff:g} units",
                )

            except Exception:
                pass

# ============================================================
# BILL ANALYZER
# ============================================================

elif page == "🧾 Bill Analyzer":

    st.markdown(
        """
        <div class="ps-header">
            <div class="ps-title">🧾 Bill Analyzer</div>
            <div class="ps-subtitle">
                Upload your electricity bill and PowerSense AI
                will automatically perform the complete analysis.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # USER OPTIONS
    # --------------------------------------------------------

    provider_choice = st.selectbox(
        "Electricity Provider / DISCO",
        DISCOS,
        index=0,
    )

    category = st.selectbox(
        "Consumer Category",
        CONSUMER_CATEGORIES,
        index=0,
    )

    language = st.selectbox(
        "Response Language",
        LANGUAGES,
        index=0,
    )

    question = st.text_area(
        "Your question (optional)",
        placeholder="Why is my bill high? Explain the extra charges.",
        height=80,
    )

    # --------------------------------------------------------
    # UPLOAD
    # --------------------------------------------------------

    uploaded = st.file_uploader(
        "📄 Upload your electricity bill",
        type=[
            "jpg",
            "jpeg",
            "png",
            "pdf",
        ],
    )

    # ========================================================
    # AUTOMATIC COMPLETE WORKFLOW
    # ========================================================

    if uploaded:

        signature = f"{uploaded.name}:{uploaded.size}"

        # Only process a newly uploaded file
        if signature != st.session_state.signature:

            st.session_state.signature = signature

            st.session_state.analysis = None
            st.session_state.complaint = None
            st.session_state.context_chunks = []
            st.session_state.bill_data = None
            st.session_state.bill_text = ""
            st.session_state.errors = []

            # =================================================
            # STEP 1 — READ BILL
            # =================================================

            with st.status(
                "⚡ PowerSense AI is analyzing your bill...",
                expanded=True,
            ) as status:

                st.write(
                    "📄 Reading uploaded electricity bill..."
                )

                try:

                    text = extract_bill_text(uploaded)

                except Exception as e:

                    text = ""

                    st.session_state.errors.append(
                        f"Bill reading error: {e}"
                    )

                st.session_state.bill_text = text

                if not text or len(text.strip()) < 15:

                    status.update(
                        label="❌ Bill could not be read",
                        state="error",
                        expanded=True,
                    )

                    st.error(
                        "PowerSense AI could not confidently read "
                        "this bill. Please upload a clearer image/PDF. "
                        "No demo data will be inserted."
                    )

                elif not api_key:

                    status.update(
                        label="⚠️ Groq API key required",
                        state="error",
                        expanded=True,
                    )

                    st.warning(
                        "The bill was successfully read, but "
                        "GROQ_API_KEY is required for AI extraction "
                        "and analysis."
                    )

                else:

                    # =========================================
                    # STEP 2 — EXTRACT BILL INFORMATION
                    # =========================================

                    st.write(
                        "🤖 Bill Extraction Agent is extracting "
                        "actual values from your bill..."
                    )

                    try:

                        bill_data = extract_bill_fields_with_llm(
                            api_key,
                            text,
                        )

                    except Exception as e:

                        bill_data = None

                        st.session_state.errors.append(
                            f"Bill extraction error: {e}"
                        )

                    st.session_state.bill_data = bill_data

                    if not bill_data:

                        status.update(
                            label="❌ Bill extraction failed",
                            state="error",
                            expanded=True,
                        )

                        st.error(
                            "PowerSense AI could not extract the bill "
                            "details confidently. Please upload a "
                            "clearer bill."
                        )

                    else:

                        # =====================================
                        # STEP 3 — RAG
                        # =====================================

                        st.write(
                            "📚 RAG Agent is checking the bill "
                            "against the knowledge base..."
                        )

                        try:

                            query = f"""
                            Electricity bill verification.

                            Provider:
                            {bill_data.get("provider")}

                            Billing month:
                            {bill_data.get("billing_month")}

                            Tariff category:
                            {bill_data.get("tariff_category")}

                            Units consumed:
                            {bill_data.get("units_consumed")}

                            Electricity charges:
                            {bill_data.get("electricity_charges")}

                            Taxes:
                            {bill_data.get("taxes")}

                            Surcharges:
                            {bill_data.get("surcharges")}

                            FCA:
                            {bill_data.get("fca")}

                            Quarterly adjustment:
                            {bill_data.get("quarterly_adjustment")}

                            Fixed charges:
                            {bill_data.get("fixed_charges")}

                            Arrears:
                            {bill_data.get("arrears")}

                            Other charges:
                            {bill_data.get("other_charges")}

                            Verify the electricity bill,
                            tariff rules, charges and possible
                            billing issues.

                            User question:
                            {question}
                            """

                            vectorstore = (
                                build_or_load_vectorstore()
                            )

                            chunks = retrieve_relevant_chunks(
                                query,
                                vectorstore,
                            )

                            st.session_state.context_chunks = (
                                chunks or []
                            )

                        except Exception as e:

                            st.session_state.context_chunks = []

                            st.warning(
                                "Knowledge-base retrieval could "
                                f"not be completed: {e}"
                            )

                        # =====================================
                        # STEP 4 — AI ANALYSIS
                        # =====================================

                        st.write(
                            "🔍 Verification Agents are analyzing "
                            "charges and consumption..."
                        )

                        if provider_choice == "Auto-detect":

                            resolved_provider = (
                                bill_data.get("provider")
                                or "Unknown"
                            )

                        else:

                            resolved_provider = (
                                provider_choice
                            )

                        try:

                            result = analyze_and_verify_bill(
                                api_key,
                                bill_data,
                                resolved_provider,
                                category,
                                language,
                                st.session_state.context_chunks,
                            )

                        except Exception as e:

                            result = None

                            st.session_state.errors.append(
                                f"Analysis error: {e}"
                            )

                            st.error(
                                f"AI analysis error: {e}"
                            )

                        if result:

                            st.session_state.analysis = result

                            # =================================
                            # STEP 5 — COMPLAINT PACKAGE
                            # =================================

                            st.write(
                                "📢 Complaint Assistant is "
                                "preparing guidance..."
                            )

                            try:

                                complaint = (
                                    generate_complaint_package(
                                        api_key,
                                        bill_data,
                                        result,
                                        resolved_provider,
                                        language,
                                    )
                                )

                                st.session_state.complaint = (
                                    complaint
                                )

                            except Exception as e:

                                st.session_state.complaint = None

                                st.warning(
                                    "Complaint package could "
                                    f"not be generated: {e}"
                                )

                            status.update(
                                label=(
                                    "✅ Complete Bill Analysis "
                                    "Finished"
                                ),
                                state="complete",
                                expanded=False,
                            )

                        else:

                            status.update(
                                label="❌ AI analysis failed",
                                state="error",
                                expanded=True,
                            )

                            st.error(
                                "AI analysis failed. Please check "
                                "your Groq API key and model availability."
                            )

        # ====================================================
        # SHOW UPLOADED BILL
        # ====================================================

        if uploaded.type.startswith("image"):

            st.image(
                uploaded,
                caption="Uploaded electricity bill",
                use_container_width=True,
            )

        # ====================================================
        # EXTRACTED TEXT
        # ====================================================

        if st.session_state.bill_text:

            with st.expander(
                "🔎 View Extracted Bill Text"
            ):

                st.text(
                    st.session_state.bill_text[:12000]
                )

        # ====================================================
        # ACTUAL EXTRACTED BILL INFORMATION
        # ====================================================

        data = st.session_state.bill_data

        if data:

            st.markdown(
                """
                <div class="success-box">
                    <b>✅ Bill information extracted successfully</b><br>
                    The information below comes from the uploaded
                    electricity bill. PowerSense AI does not insert
                    demo or synthetic values.
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.subheader(
                "📋 Extracted Bill Information"
            )

            def display_value(value):

                if value is None:
                    return "Not detected"

                if isinstance(value, str) and not value.strip():
                    return "Not detected"

                return str(value)

            # ------------------------------------------------
            # BASIC INFORMATION
            # ------------------------------------------------

            st.markdown("### 🧾 Basic Bill Details")

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Provider",
                display_value(
                    data.get("provider")
                ),
            )

            c2.metric(
                "Billing Month",
                display_value(
                    data.get("billing_month")
                ),
            )

            c3.metric(
                "Consumer Number",
                display_value(
                    data.get("consumer_number")
                ),
            )

            c4.metric(
                "Meter Number",
                display_value(
                    data.get("meter_number")
                ),
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Issue Date",
                display_value(
                    data.get("issue_date")
                ),
            )

            c2.metric(
                "Due Date",
                display_value(
                    data.get("due_date")
                ),
            )

            c3.metric(
                "Tariff Category",
                display_value(
                    data.get("tariff_category")
                ),
            )

            c4.metric(
                "Units Consumed",
                display_value(
                    data.get("units_consumed")
                ),
            )

            # ------------------------------------------------
            # METER READINGS
            # ------------------------------------------------

            st.markdown("### 📊 Meter Readings")

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Previous Reading",
                display_value(
                    data.get("previous_reading")
                ),
            )

            c2.metric(
                "Current Reading",
                display_value(
                    data.get("current_reading")
                ),
            )

            # Calculate difference if possible
            reading_difference = None

            try:

                previous = data.get(
                    "previous_reading"
                )

                current = data.get(
                    "current_reading"
                )

                if (
                    previous is not None
                    and current is not None
                ):

                    reading_difference = (
                        float(current)
                        - float(previous)
                    )

            except Exception:

                reading_difference = None

            c3.metric(
                "Reading Difference",
                (
                    f"{reading_difference:g} units"
                    if reading_difference is not None
                    else "Not detected"
                ),
            )

            # ------------------------------------------------
            # BILL AMOUNTS
            # ------------------------------------------------

            st.markdown("### 💰 Bill Amounts")

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Previous Bill Amount",
                display_value(
                    data.get(
                        "previous_bill_amount"
                    )
                ),
            )

            c2.metric(
                "Current Bill Amount",
                display_value(
                    data.get(
                        "current_bill_amount"
                    )
                ),
            )

            c3.metric(
                "Amount Payable",
                display_value(
                    data.get(
                        "amount_payable"
                    )
                ),
            )

            # ------------------------------------------------
            # CHARGES
            # ------------------------------------------------

            st.markdown("### 💵 Charges")

            charge_data = {
                "Electricity Charges":
                    data.get(
                        "electricity_charges"
                    ),

                "Taxes":
                    data.get("taxes"),

                "Surcharges":
                    data.get("surcharges"),

                "FCA":
                    data.get("fca"),

                "Quarterly Adjustment":
                    data.get(
                        "quarterly_adjustment"
                    ),

                "Fixed Charges":
                    data.get("fixed_charges"),

                "Arrears":
                    data.get("arrears"),

                "Other Charges":
                    data.get(
                        "other_charges"
                    ),
            }

            cols = st.columns(4)

            for index, (
                label,
                value,
            ) in enumerate(
                charge_data.items()
            ):

                cols[index % 4].metric(
                    label,
                    display_value(value),
                )

            # ------------------------------------------------
            # ANALYSIS COMPLETE
            # ------------------------------------------------

            if st.session_state.analysis:

                st.divider()

                st.subheader(
                    "⚡ Analysis Complete"
                )

                analysis = (
                    st.session_state.analysis
                )

                summary = analysis.get(
                    "bill_summary",
                    {},
                )

                c1, c2, c3, c4 = st.columns(4)

                c1.metric(
                    "Provider",
                    display_value(
                        summary.get(
                            "provider"
                        )
                        or data.get(
                            "provider"
                        )
                    ),
                )

                c2.metric(
                    "Billing Month",
                    display_value(
                        summary.get(
                            "billing_month"
                        )
                        or data.get(
                            "billing_month"
                        )
                    ),
                )

                units = (
                    summary.get(
                        "units_consumed"
                    )
                    if summary.get(
                        "units_consumed"
                    ) is not None
                    else data.get(
                        "units_consumed"
                    )
                )

                c3.metric(
                    "Units",
                    display_value(
                        units
                    ),
                )

                total_bill = (
                    summary.get(
                        "total_bill"
                    )
                    if summary.get(
                        "total_bill"
                    ) is not None
                    else data.get(
                        "amount_payable"
                    )
                )

                c4.metric(
                    "Amount Payable",
                    display_value(
                        total_bill
                    ),
                )

                st.success(
                    "🎯 Your complete bill analysis is ready. "
                    "Use the sidebar to view Bill Breakdown, "
                    "Attention, Why Your Bill Is High, "
                    "Complaint Assistant and Sources."
                )

# ============================================================
# BILL BREAKDOWN
# ============================================================

elif page == "📊 Bill Breakdown":

    st.markdown(
        """
        <div class="ps-header">
            <div class="ps-title">📊 Bill Breakdown</div>
            <div class="ps-subtitle">
                Actual values extracted from your uploaded bill.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    analysis = st.session_state.analysis

    if not analysis:

        st.info(
            "Upload a bill from Bill Analyzer first."
        )

    else:

        summary = analysis.get(
            "bill_summary",
            {},
        )

        data = (
            st.session_state.bill_data
            or {}
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Provider",
            summary.get(
                "provider"
            )
            or data.get(
                "provider"
            )
            or "—",
        )

        c2.metric(
            "Billing Month",
            summary.get(
                "billing_month"
            )
            or data.get(
                "billing_month"
            )
            or "—",
        )

        units = (
            summary.get(
                "units_consumed"
            )
            if summary.get(
                "units_consumed"
            ) is not None
            else data.get(
                "units_consumed"
            )
        )

        c3.metric(
            "Units",
            units or "—",
        )

        total_bill = (
            summary.get(
                "total_bill"
            )
            if summary.get(
                "total_bill"
            ) is not None
            else data.get(
                "amount_payable"
            )
        )

        c4.metric(
            "Total Bill",
            total_bill or "—",
        )

        st.caption(
            "Due date: "
            + str(
                summary.get(
                    "due_date"
                )
                or data.get(
                    "due_date"
                )
                or "—"
            )
        )

        rows = analysis.get(
            "charge_breakdown",
            [],
        )

        if rows:

            table_rows = []

            for row in rows:

                status = row.get(
                    "status",
                    "",
                )

                table_rows.append(
                    {
                        "Component":
                            row.get(
                                "component"
                            ),

                        "Amount (PKR)":
                            row.get(
                                "amount"
                            ),

                        "Status":
                            f"{STATUS_ICONS.get(status, '')} "
                            f"{status or '—'}",

                        "Explanation":
                            row.get(
                                "explanation",
                                "—",
                            ),
                    }
                )

            st.dataframe(
                table_rows,
                use_container_width=True,
                hide_index=True,
            )

        consumption = analysis.get(
            "consumption_analysis",
            {},
        )

        if consumption:

            st.subheader(
                "📈 Consumption Analysis"
            )

            x, y, z, w = st.columns(4)

            x.metric(
                "Previous Units",
                consumption.get(
                    "previous_units"
                )
                or "—",
            )

            y.metric(
                "Current Units",
                consumption.get(
                    "current_units"
                )
                or "—",
            )

            z.metric(
                "Difference",
                consumption.get(
                    "difference"
                )
                or "—",
            )

            w.metric(
                "% Change",
                consumption.get(
                    "percent_change"
                )
                or "—",
            )

            st.caption(
                consumption.get(
                    "note",
                    "",
                )
            )

# ============================================================
# ATTENTION
# ============================================================

elif page == "⚠️ Attention":

    st.title(
        "⚠️ Charges That Need Your Attention"
    )

    analysis = st.session_state.analysis

    if not analysis:

        st.info(
            "Upload and analyze a bill first."
        )

    else:

        items = analysis.get(
            "attention_items",
            [],
        )

        if not items:

            st.success(
                "🟢 No charges were flagged as unclear "
                "or requiring verification."
            )

        for item in items:

            icon = STATUS_ICONS.get(
                item.get(
                    "status"
                ),
                "🟡",
            )

            with st.expander(
                f"{icon} "
                f"{item.get('charge_name', 'Unknown')} "
                f"— PKR {item.get('amount', '—')}"
            ):

                st.write(
                    "**Status:** "
                    + str(
                        item.get(
                            "status",
                            "—",
                        )
                    )
                )

                st.write(
                    "**Why flagged:** "
                    + str(
                        item.get(
                            "flag_reason",
                            "—",
                        )
                    )
                )

                st.write(
                    "**Source:** "
                    + str(
                        item.get(
                            "source_used"
                        )
                        or "No specific source matched"
                    )
                )

                st.write(
                    "**Verify:** "
                    + str(
                        item.get(
                            "what_to_verify",
                            "—",
                        )
                    )
                )

# ============================================================
# WHY IS BILL HIGH
# ============================================================

elif page == "💡 Why Is My Bill High?":

    st.title(
        "💡 Why Is My Bill High?"
    )

    analysis = st.session_state.analysis

    if not analysis:

        st.info(
            "Upload and analyze a bill first."
        )

    else:

        explanation = analysis.get(
            "why_bill_is_high",
            "No explanation was generated.",
        )

        st.write(
            explanation
        )

# ============================================================
# COMPLAINT ASSISTANT
# ============================================================

elif page == "📢 Complaint Assistant":

    st.title(
        "📢 Complaint Assistant"
    )

    analysis = st.session_state.analysis
    data = st.session_state.bill_data

    if not analysis or not data:

        st.info(
            "Upload and analyze a bill first so the "
            "complaint assistant has the actual bill context."
        )

    else:

        complaint = (
            st.session_state.complaint
        )

        if not complaint:

            if not api_key:

                st.error(
                    "GROQ_API_KEY is required."
                )

            else:

                with st.spinner(
                    "Complaint Assistant Agent is preparing your package..."
                ):

                    try:

                        provider = (
                            data.get(
                                "provider"
                            )
                            or "Unknown"
                        )

                        complaint = (
                            generate_complaint_package(
                                api_key,
                                data,
                                analysis,
                                provider,
                                "English",
                            )
                        )

                        st.session_state.complaint = (
                            complaint
                        )

                    except Exception as e:

                        st.error(
                            f"Complaint package could not be generated: {e}"
                        )

        complaint = (
            st.session_state.complaint
        )

        if complaint:

            st.subheader(
                "Should you consider a complaint?"
            )

            st.write(
                "Yes"
                if complaint.get(
                    "should_consider_complaint"
                )
                else "Not clearly necessary right now"
            )

            st.subheader(
                "Reason"
            )

            st.write(
                complaint.get(
                    "reason_summary",
                    "—",
                )
            )

            st.subheader(
                "Likely Complaint Category"
            )

            st.write(
                complaint.get(
                    "likely_complaint_category",
                    "—",
                )
            )

            st.subheader(
                "Evidence to Keep"
            )

            evidence = complaint.get(
                "evidence_to_keep",
                [],
            )

            for item in evidence:

                st.write(
                    "- " + str(item)
                )

            st.subheader(
                "Draft Complaint"
            )

            st.text_area(
                "Editable draft",
                value=complaint.get(
                    "draft_complaint_text",
                    "",
                ),
                height=200,
            )

            st.subheader(
                "Provider First"
            )

            st.write(
                complaint.get(
                    "contact_provider_first_note",
                    "Contact the relevant electricity provider first where appropriate.",
                )
            )

            st.link_button(
                "🔗 Open Official NEPRA Complaint Portal",
                NEPRA_COMPLAINT_URL,
            )

# ============================================================
# SOURCES
# ============================================================

elif page == "📚 Sources":

    st.title(
        "📚 Sources Used"
    )

    chunks = (
        st.session_state.context_chunks
    )

    analysis = (
        st.session_state.analysis
    )

    sources = set(
        analysis.get(
            "sources_used",
            [],
        )
        if analysis
        else []
    )

    for chunk in chunks:

        source = chunk.get(
            "source"
        )

        if source:

            sources.add(
                source
            )

    if not sources:

        st.warning(
            "No knowledge-base sources were retrieved "
            "for the current analysis."
        )

    else:

        for source in sorted(
            sources
        ):

            st.write(
                "📄 " + str(source)
            )

    with st.expander(
        "Retrieved Context"
    ):

        if not chunks:

            st.info(
                "No retrieved context."
            )

        else:

            for chunk in chunks:

                st.markdown(
                    f"""
                    **{chunk.get('source', 'Source')}**

                    {chunk.get('text', '')[:1000]}

                    ---
                    """
                )

# ============================================================
# ABOUT
# ============================================================

elif page == "ℹ️ About":

    st.title(
        "ℹ️ About PowerSense AI"
    )

    st.markdown(
        """
        **PowerSense AI** is a Pakistan-focused hackathon
        project for electricity-bill transparency.

        ### Workflow

        Upload a real bill → OCR/PDF extraction →
        Bill Extraction Agent → RAG/FAISS retrieval →
        Groq analysis → charge verification →
        high-bill explanation → complaint assistance.

        ### Important

        The app does not use a demo bill, synthetic
        consumption history, or fabricated tariff rate.

        If a value cannot be confidently extracted from
        the uploaded bill, it remains unavailable rather
        than being invented.
        """
    )

    st.markdown(
        f'<div class="disclaimer">{DISCLAIMER}</div>',
        unsafe_allow_html=True,
    )
