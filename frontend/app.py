import streamlit as st
import requests
import os
import pandas as pd

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="TracePath AI - Customer Support Analytics",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 TracePath AI - Customer Support Analytics Platform")
st.markdown(
    "Ask natural-language questions about support tickets. "
    "The AI translates your question into a strict structured intent, and deterministic backend logic executes the query safely against SQLite."
)

# Sidebar - System Status
st.sidebar.header("System Connectivity")
try:
    health_resp = requests.get(f"{API_BASE_URL}/health", timeout=3)
    if health_resp.status_code == 200:
        health_data = health_resp.json()
        st.sidebar.success(f"Backend Status: {health_data.get('status').upper()}")
        st.sidebar.write(f"**Loaded Tickets:** {health_data['dataset']['loaded_ticket_count']}")
        st.sidebar.write(f"**Database:** {health_data['database']['engine']}")
        st.sidebar.write(f"**Uptime:** {health_data['uptime_seconds']}s")
    else:
        st.sidebar.error(f"Backend returned code {health_resp.status_code}")
except Exception:
    st.sidebar.error(f"Cannot reach Backend at {API_BASE_URL}")

st.sidebar.markdown("---")
st.sidebar.subheader("💡 Example Questions")
examples = [
    "How many tickets are currently open?",
    "Which agent resolved the most tickets this month?",
    "Show me all Critical tickets not resolved within 12 hours.",
    "What is the average customer rating for Technical category tickets?",
    "Are there any anomalies in resolution times this week?",
    "How many critical tickets are unresolved?",
    "What is the average rating by category?",
]

selected_example = st.sidebar.radio("Select an example to load:", ["Custom Question"] + examples)

# Main Navigation Tabs
tab_nl, tab_kpi, tab_anom, tab_data = st.tabs([
    "💬 AI Query Engine", "📈 Executive Dashboard", "⚠️ Anomaly Detection", "🔍 Ticket Explorer"
])

with tab_nl:
    default_prompt = "" if selected_example == "Custom Question" else selected_example
    user_query = st.text_input("Enter your support analytics question:", value=default_prompt, placeholder="e.g., How many critical tickets are unresolved?")
    
    col_btn, _ = st.columns([1, 5])
    if col_btn.button("Run Query 🚀", type="primary") and user_query:
        with st.spinner("Translating intent & querying SQLite..."):
            try:
                resp = requests.post(
                    f"{API_BASE_URL}/api/query",
                    json={"question": user_query},
                    timeout=15
                )
                if resp.status_code == 200:
                    res_data = resp.json()
                    
                    st.success("### Factual Answer:")
                    st.write(res_data["answer"])

                    # Metadata details
                    meta = res_data.get("metadata", {})
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Execution Time", f"{meta.get('execution_time_ms', 0)} ms")
                    c2.metric("Matched Records", meta.get("total_records_matched", 0))
                    c3.metric("Anomaly Flag", "Yes ⚠️" if meta.get("is_anomaly_request") else "No ✅")

                    # Data Table Breakdown
                    if res_data.get("data"):
                        st.subheader("Data Result Set")
                        df_res = pd.DataFrame(res_data["data"])
                        st.dataframe(df_res, use_container_width=True)

                    # Structured Interpretation Accordion
                    with st.expander("🛠️ View Strict Pydantic Intent AST"):
                        st.json(res_data["interpretation"])

                else:
                    st.error(f"API Error ({resp.status_code}): {resp.text}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

with tab_kpi:
    st.subheader("Executive Dashboard KPI Metrics (/api/stats)")
    try:
        stats_resp = requests.get(f"{API_BASE_URL}/api/stats", timeout=5)
        if stats_resp.status_code == 200:
            stats = stats_resp.json()["data"]
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Tickets", stats["total_tickets"])
            c2.metric("Open Tickets", stats["open_tickets"])
            c3.metric("Resolved Tickets", stats["resolved_tickets"])
            c4.metric("Escalated Tickets", stats["escalated_tickets"])
            
            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Critical Tickets", stats["critical_tickets"])
            c6.metric("Flagged Anomalies", stats["anomaly_count"], delta_color="inverse")
            c7.metric("Avg Response Time", f"{stats['average_response_time']} hrs")
            c8.metric("Avg Customer Rating", f"{stats['average_customer_rating'] or 'N/A'} ⭐")
        else:
            st.warning("Failed to fetch dashboard stats.")
    except Exception:
        st.info("Start the backend server (`python main.py`) to view live dashboard stats.")

with tab_anom:
    st.subheader("Statistical Outlier & SLA Anomaly Detection (/api/anomalies)")
    try:
        anom_resp = requests.get(f"{API_BASE_URL}/api/anomalies", timeout=5)
        if anom_resp.status_code == 200:
            report = anom_resp.json()["data"]
            
            st.write(f"**Total Detected Anomalies:** {report['total_anomalies_detected']}")
            
            # Show IQR Stats
            iqr = report.get("iqr_statistics", {})
            st.info(
                f"📊 **IQR Resolution Time Baseline:** Q1 = {iqr.get('q1')}h | Median = {iqr.get('median')}h | "
                f"Q3 = {iqr.get('q3')}h | IQR = {iqr.get('iqr')}h | **Upper Outlier Threshold = {iqr.get('upper_bound')}h**"
            )
            
            if report.get("items"):
                df_anom = pd.DataFrame(report["items"])
                st.dataframe(df_anom, use_container_width=True)
            else:
                st.success("No anomalies currently flagged in the dataset.")
    except Exception:
        st.info("Connect to the backend API to view anomaly records.")

with tab_data:
    st.subheader("Support Tickets Data Explorer (/api/tickets)")
    try:
        tickets_resp = requests.get(f"{API_BASE_URL}/api/tickets?page_size=50", timeout=5)
        if tickets_resp.status_code == 200:
            data = tickets_resp.json()["data"]["items"]
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No tickets loaded in database.")
    except Exception:
        st.info("Connect to the backend API to view raw ticket records.")
