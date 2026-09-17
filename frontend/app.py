import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from frontend.api_client import ApiClient, ApiClientError

# Page setup
st.set_page_config(
    page_title="TracePath AI | Support Analytics",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize API client
client = ApiClient()

# Custom CSS for polished, high-contrast engineering appearance
st.markdown("""
<style>
    /* Metric Cards */
    .metric-card {
        background: #151C2C;
        border: 1px solid #2A364F;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        margin-bottom: 12px;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94A3B8;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-top: 4px;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #64748B;
        margin-top: 2px;
    }
    
    /* Prominent Answer Card */
    .answer-card {
        background: linear-gradient(135deg, #1E1B4B 0%, #0F172A 100%);
        border: 1px solid #6366F1;
        border-radius: 10px;
        padding: 20px;
        margin: 16px 0;
    }
    .answer-title {
        font-size: 0.9rem;
        color: #818CF8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .answer-body {
        font-size: 1.25rem;
        font-weight: 600;
        color: #FFFFFF;
        margin-top: 8px;
        line-height: 1.5;
    }

    /* Anomaly Item Card */
    .anomaly-card {
        background: #151C2C;
        border-left: 4px solid #EF4444;
        border-radius: 6px;
        padding: 14px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ================= SIDEBAR =================
with st.sidebar:
    st.markdown("## 🛡️ **TracePath AI**")
    st.caption("AI-powered customer support intelligence")
    st.markdown("---")

    nav_choice = st.radio(
        "Navigation",
        [
            "📊 Overview Dashboard",
            "💬 Ask AI",
            "⚠️ Anomaly Center",
            "🔍 Ticket Explorer",
            "⚙️ System Status"
        ],
        index=0
    )

    st.markdown("---")
    
    # System Status Indicator in Sidebar
    try:
        health = client.get_health()
        st.success(f"🟢 Backend: {health.get('status', 'OK').upper()}")
        st.caption(f"Tickets: **{health['dataset']['loaded_ticket_count']}** | Engine: **SQLite**")
    except ApiClientError as err:
        st.error("🔴 Backend Offline")
        st.caption("Start server: `python main.py`")


# ================= PAGE 1: OVERVIEW DASHBOARD =================
if nav_choice == "📊 Overview Dashboard":
    st.title("📊 Executive Support Overview")
    st.caption("Real-time operational metrics and distribution analytics calculated from SQLite.")

    try:
        stats_resp = client.get_stats()
        stats = stats_resp["data"]

        # Top KPI Metric Row
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Tickets</div>
                <div class="metric-value">{stats['total_tickets']}</div>
                <div class="metric-sub">100% Ingested</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Open</div>
                <div class="metric-value" style="color: #38BDF8;">{stats['open_tickets']}</div>
                <div class="metric-sub">{(stats['open_tickets']/stats['total_tickets']*100):.1f}% Active</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Resolved</div>
                <div class="metric-value" style="color: #4ADE80;">{stats['resolved_tickets']}</div>
                <div class="metric-sub">{(stats['resolved_tickets']/stats['total_tickets']*100):.1f}% Resolved</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Escalated</div>
                <div class="metric-value" style="color: #FBBF24;">{stats['escalated_tickets']}</div>
                <div class="metric-sub">{(stats['escalated_tickets']/stats['total_tickets']*100):.1f}% Escalated</div>
            </div>
            """, unsafe_allow_html=True)
        with c5:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Critical</div>
                <div class="metric-value" style="color: #F87171;">{stats['critical_tickets']}</div>
                <div class="metric-sub">High Attention</div>
            </div>
            """, unsafe_allow_html=True)
        with c6:
            st.markdown(f"""
            <div class="metric-card" style="border-color: #EF4444;">
                <div class="metric-label" style="color: #FCA5A5;">Anomalies</div>
                <div class="metric-value" style="color: #EF4444;">{stats['anomaly_count']}</div>
                <div class="metric-sub">Statistical Outliers</div>
            </div>
            """, unsafe_allow_html=True)

        # Performance KPI Sub-row
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Avg Response Time", f"{stats['average_response_time']} hrs")
        with k2:
            st.metric("Avg Resolution Time", f"{stats['average_resolution_time']} hrs")
        with k3:
            st.metric("Avg Customer Rating", f"{stats['average_customer_rating']} / 5 ⭐")
        with k4:
            st.metric("Response SLA Breaches (>4h)", f"{stats['sla_breach_count']} tickets")

        st.markdown("---")
        st.subheader("📈 Operational Distributions")

        # Fetch chart breakdown from API
        breakdown_resp = client.get_stats_breakdown()
        b_data = breakdown_resp["data"]

        # Chart Row 1: Category and Priority
        ch1, ch2 = st.columns(2)
        with ch1:
            st.markdown("##### 📁 Tickets by Category")
            df_cat = pd.DataFrame(b_data["by_category"])
            chart_cat = (
                alt.Chart(df_cat)
                .mark_bar(cornerRadius=4)
                .encode(
                    x=alt.X("category:N", title="Category", sort="-y"),
                    y=alt.Y("count:Q", title="Ticket Count"),
                    color=alt.Color("category:N", legend=None, scale=alt.Scale(scheme="indigo")),
                    tooltip=["category", "count"]
                )
                .properties(height=280)
            )
            st.altair_chart(chart_cat, use_container_width=True)

        with ch2:
            st.markdown("##### 🎯 Tickets by Priority")
            df_prio = pd.DataFrame(b_data["by_priority"])
            prio_order = ["Low", "Medium", "High", "Critical"]
            chart_prio = (
                alt.Chart(df_prio)
                .mark_bar(cornerRadius=4)
                .encode(
                    x=alt.X("priority:N", title="Priority", sort=prio_order),
                    y=alt.Y("count:Q", title="Ticket Count"),
                    color=alt.Color("priority:N", legend=None, scale=alt.Scale(
                        domain=["Low", "Medium", "High", "Critical"],
                        range=["#38BDF8", "#FBBF24", "#F97316", "#EF4444"]
                    )),
                    tooltip=["priority", "count"]
                )
                .properties(height=280)
            )
            st.altair_chart(chart_prio, use_container_width=True)

        # Chart Row 2: Status & Ratings
        ch3, ch4 = st.columns(2)
        with ch3:
            st.markdown("##### 🔄 Tickets by Status")
            df_status = pd.DataFrame(b_data["by_status"])
            chart_status = (
                alt.Chart(df_status)
                .mark_bar(cornerRadius=4)
                .encode(
                    x=alt.X("status:N", title="Status", sort="-y"),
                    y=alt.Y("count:Q", title="Ticket Count"),
                    color=alt.Color("status:N", legend=None, scale=alt.Scale(
                        domain=["Resolved", "Open", "Escalated"],
                        range=["#4ADE80", "#38BDF8", "#FBBF24"]
                    )),
                    tooltip=["status", "count"]
                )
                .properties(height=280)
            )
            st.altair_chart(chart_status, use_container_width=True)

        with ch4:
            st.markdown("##### ⭐ Customer Rating Distribution")
            df_rat = pd.DataFrame(b_data["rating_distribution"])
            chart_rat = (
                alt.Chart(df_rat)
                .mark_bar(cornerRadius=4)
                .encode(
                    x=alt.X("rating:N", title="Rating (Resolved Tickets)"),
                    y=alt.Y("count:Q", title="Count"),
                    color=alt.value("#6366F1"),
                    tooltip=["rating", "count"]
                )
                .properties(height=280)
            )
            st.altair_chart(chart_rat, use_container_width=True)

        # Chart Row 3: Agent Breakdown
        st.markdown("##### 👤 Ticket Volume per Agent")
        df_agent = pd.DataFrame(b_data["by_agent"])
        chart_agent = (
            alt.Chart(df_agent)
            .mark_bar(cornerRadius=4)
            .encode(
                y=alt.Y("agent_id:N", title="Agent ID", sort="-x"),
                x=alt.X("count:Q", title="Assigned Tickets"),
                color=alt.value("#3B82F6"),
                tooltip=["agent_id", "count"]
            )
            .properties(height=320)
        )
        st.altair_chart(chart_agent, use_container_width=True)

    except ApiClientError as e:
        st.error(f"Failed to load dashboard metrics: {e.message}")


# ================= PAGE 2: ASK AI =================
elif nav_choice == "💬 Ask AI":
    st.title("💬 AI Customer Support Query Engine")
    st.caption("Ask questions in plain English. The AI extracts structured intent, and deterministic backend logic computes the exact mathematical answer from SQLite.")

    # Assessment Sample Query Buttons
    st.markdown("##### ⚡ Example Questions (Click to run):")
    sample_queries = [
        "How many tickets are currently open?",
        "Which agent resolved the most tickets this month?",
        "Show me all Critical tickets not resolved within 12 hours.",
        "What is the average customer rating for Technical category tickets?",
        "Are there any anomalies in resolution times this week?",
    ]

    # Render buttons in clean rows
    btn_cols = st.columns(len(sample_queries))
    selected_query_from_btn = None
    for idx, (col, sq) in enumerate(zip(btn_cols, sample_queries)):
        if col.button(f"Q{idx+1}", help=sq, use_container_width=True):
            selected_query_from_btn = sq

    # State management for prompt input
    if "current_question" not in st.session_state:
        st.session_state.current_question = ""

    if selected_query_from_btn:
        st.session_state.current_question = selected_query_from_btn

    # Natural Language Form
    with st.form(key="nl_query_form"):
        user_input = st.text_input(
            "Enter your analytics question:",
            value=st.session_state.current_question,
            placeholder="e.g., How many critical tickets are unresolved?"
        )
        submit_btn = st.form_submit_button("Ask TracePath AI 🚀", type="primary", use_container_width=True)

    # Process query
    active_question = user_input.strip() if submit_btn else (selected_query_from_btn or "")
    if active_question:
        with st.spinner("Translating natural language intent and querying SQLite..."):
            try:
                res = client.query_natural_language(active_question)
                
                # Visual Answer Container
                st.markdown(f"""
                <div class="answer-card">
                    <div class="answer-title">📌 Factual Database Answer</div>
                    <div class="answer-body">{res['answer']}</div>
                </div>
                """, unsafe_allow_html=True)

                # Metadata Metrics Row
                meta = res.get("metadata", {})
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("Intent Classified", res["interpretation"]["intent"].upper())
                with m2:
                    st.metric("Records Matched", meta.get("total_records_matched", 0))
                with m3:
                    st.metric("Execution Time", f"{meta.get('execution_time_ms', 0)} ms")
                with m4:
                    st.metric("Anomaly Flag", "⚠️ Yes" if meta.get("is_anomaly_request") else "✅ Normal")

                # Tabular Data Results
                if res.get("data"):
                    st.markdown("##### 📋 Result Dataset")
                    df_res = pd.DataFrame(res["data"])
                    st.dataframe(df_res, use_container_width=True)

                # Expandable Pydantic AST Inspector
                with st.expander("🛠️ View Strict Pydantic Intent AST & Safety Specification"):
                    st.json(res["interpretation"])

            except ApiClientError as err:
                st.error(f"Query processing failed: {err.message}")


# ================= PAGE 3: ANOMALY CENTER =================
elif nav_choice == "⚠️ Anomaly Center":
    st.title("⚠️ Anomaly & Outlier Center")
    st.caption("Deterministic statistical IQR detection and SLA threshold analysis. Flagged without LLM hallucinations.")

    try:
        # Filter controls
        f1, f2, f3 = st.columns(3)
        with f1:
            sel_type = st.selectbox(
                "Filter Anomaly Type",
                ["All", "long_resolution_time", "unresolved_high_priority_aged"]
            )
        with f2:
            sel_sev = st.selectbox(
                "Filter Severity",
                ["All", "critical", "high", "medium", "low"]
            )
        with f3:
            sel_prio = st.selectbox(
                "Filter Ticket Priority",
                ["All", "Critical", "High", "Medium", "Low"]
            )

        anom_type_param = None if sel_type == "All" else sel_type
        sev_param = None if sel_sev == "All" else sel_sev
        prio_param = None if sel_prio == "All" else sel_prio

        report_resp = client.get_anomalies(
            anomaly_type=anom_type_param,
            severity=sev_param,
            priority=prio_param
        )
        report = report_resp["data"]

        # Statistical IQR Banner
        iqr = report.get("iqr_statistics", {})
        st.info(
            f"📊 **IQR Statistical Outlier Baseline (Resolution Times):** "
            f"**Q1:** {iqr.get('q1')}h | **Median:** {iqr.get('median')}h | **Q3:** {iqr.get('q3')}h | **IQR:** {iqr.get('iqr')}h | "
            f"**Upper Outlier Threshold (Q3 + 1.5×IQR): {iqr.get('upper_bound')} hrs**"
        )

        # Summary KPIs
        a1, a2, a3 = st.columns(3)
        a1.metric("Total Flagged Anomalies", report["total_anomalies_detected"])
        a2.metric("Long Resolution Outliers", report["anomalies_by_type"].get("long_resolution_time", 0))
        a3.metric("Aged High/Critical Tickets (>24h)", report["anomalies_by_type"].get("unresolved_high_priority_aged", 0))

        st.markdown("---")
        st.subheader("🚨 Flagged Anomaly Records")

        items = report.get("items", [])
        if items:
            df_items = pd.DataFrame(items)
            
            # Format dataframe columns
            st.dataframe(
                df_items[[
                    "ticket_id", "severity", "anomaly_type", "metric", "threshold",
                    "priority", "status", "category", "agent_id", "reason", "issue_summary"
                ]],
                use_container_width=True
            )
        else:
            st.success("No anomalies found matching the selected filter criteria.")

    except ApiClientError as err:
        st.error(f"Could not retrieve anomaly report: {err.message}")


# ================= PAGE 4: TICKET EXPLORER =================
elif nav_choice == "🔍 Ticket Explorer":
    st.title("🔍 Support Ticket Explorer")
    st.caption("Search, filter, and inspect records from the 500-ticket dataset.")

    try:
        # Search and Filters Row 1
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            f_cat = st.selectbox("Category", ["All", "Billing", "Technical", "General"])
        with r2:
            f_prio = st.selectbox("Priority", ["All", "Low", "Medium", "High", "Critical"])
        with r3:
            f_status = st.selectbox("Status", ["All", "Open", "Resolved", "Escalated"])
        with r4:
            f_agent = st.selectbox(
                "Agent ID",
                ["All", "AGT-01", "AGT-02", "AGT-03", "AGT-04", "AGT-05", "AGT-06", "AGT-07", "AGT-08", "AGT-09", "AGT-10", "AGT-11", "AGT-12"]
            )

        # Row 2: Search text & Page Size
        s1, s2 = st.columns([3, 1])
        with s1:
            search_query = st.text_input("Search issue summary or ticket ID:", placeholder="e.g., checkout, login, invoice")
        with s2:
            page_size = st.selectbox("Page Size", [20, 50, 100], index=0)

        # Pagination State
        if "ticket_page" not in st.session_state:
            st.session_state.ticket_page = 1

        tickets_resp = client.get_tickets(
            category=f_cat,
            priority=f_prio,
            status=f_status,
            agent_id=f_agent,
            search=search_query,
            page=st.session_state.ticket_page,
            page_size=page_size
        )
        t_data = tickets_resp["data"]
        items = t_data["items"]
        total = t_data["total"]
        total_pages = t_data["total_pages"]

        st.caption(f"Showing **{len(items)}** of **{total}** matching tickets (Page **{st.session_state.ticket_page}** of **{total_pages}**)")

        if items:
            df_t = pd.DataFrame(items)
            st.dataframe(df_t, use_container_width=True)
        else:
            st.info("No tickets match the selected filters.")

        # Pagination Buttons
        p_col1, p_col2, p_col3 = st.columns([1, 4, 1])
        with p_col1:
            if st.button("⬅️ Previous", disabled=(st.session_state.ticket_page <= 1)):
                st.session_state.ticket_page -= 1
                st.rerun()
        with p_col3:
            if st.button("Next ➡️", disabled=(st.session_state.ticket_page >= total_pages)):
                st.session_state.ticket_page += 1
                st.rerun()

    except ApiClientError as err:
        st.error(f"Error loading tickets: {err.message}")


# ================= PAGE 5: SYSTEM STATUS =================
elif nav_choice == "⚙️ System Status":
    st.title("⚙️ System Diagnostics & Architecture")
    st.caption("Inspect live API connectivity, local database integrity, and architecture verification.")

    try:
        health = client.get_health()

        h1, h2, h3 = st.columns(3)
        h1.metric("Application Status", health.get("status", "UNKNOWN").upper())
        h2.metric("Environment", health.get("environment", "development"))
        h3.metric("Uptime", f"{health.get('uptime_seconds', 0)}s")

        st.markdown("---")
        st.subheader("📦 Database & Dataset Integrity")

        db_meta = health.get("database", {})
        ds_meta = health.get("dataset", {})

        c_db, c_ds = st.columns(2)
        with c_db:
            st.markdown("##### 🗄️ Database Engine")
            st.json(db_meta)
        with c_ds:
            st.markdown("##### 📄 CSV Dataset Layer")
            st.json(ds_meta)

        st.markdown("---")
        st.subheader("🛡️ LLM Safety Guarantee")
        st.markdown("""
        - **Zero SQL Execution by LLM**: The LLM output is strictly validated into a typed Pydantic AST.
        - **Deterministic Python Query Engine**: Parameterized SQLite queries compute 100% factual answers.
        - **Statistical Anomaly Engine**: Detects IQR outliers ($Q3 + 1.5 \times \text{IQR}$) and aged SLA violations via Python.
        - **Zero Credential Exposure**: Streamlit UI only communicates via HTTP with the backend without containing API keys.
        """)

    except ApiClientError as err:
        st.error(f"Could not retrieve system health: {err.message}")
