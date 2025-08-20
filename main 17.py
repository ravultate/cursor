import streamlit as st
from streamlit_option_menu import option_menu
import login
import app  
import chat_with_files as chat
import financial_insights as insights

# Enhanced page configuration
st.set_page_config(
    page_title="Agentic RAG",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS injection for immediate theming
# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)



# Call CSS injection
# inject_custom_css()

# Main header
st.markdown('<h1 class="main-header">🤖Agentic RAG System</h1>', unsafe_allow_html=True)

# Sidebar menu
with st.sidebar:
    st.markdown("### 🚀 Navigation")
    
    selected = option_menu(
        menu_title=None,
        options=["🔐 Login", "⚙️ Data Pipeline", "💬 Chat", "💼 Financial Insights", "📊 Analytics"],
        #icons=["key", "gear", "chat-dots", "briefcase", "graph-up"],
        menu_icon="cast",
        default_index=0,
        orientation="vertical",
        styles={
            "container": {"padding": "0!important", "background-color": "#d1ecf1"},
            "icon": {"color": "#1e3c72", "font-size": "18px"},
            "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px", "--hover-color": "#d1ecf1"},
            "nav-link-selected": {"background-color": "#1e3c72"},
        }
    )
    
    # System status
    st.markdown("---")
    st.markdown("### 🔧 System Status")
    
    if "access_token" in st.session_state and st.session_state.access_token:
        st.success("✅ Authenticated")
    else:
        st.error("❌ Not authenticated")
    
    if "index_name" in st.session_state and st.session_state.index_name:
        st.success("✅ Index ready")
        st.info(f"Index: {st.session_state.index_name}")
    else:
        st.warning("⚠️ No index")
    
    # Feature highlights
    st.markdown("---")
    st.markdown("### ✨ Features")
    
    features = [
        "🔍 Hybrid Search",
        "🧠 Semantic Ranking", 
        "🤖 Agentic Intelligence",
        "📄 Multi-document RAG",
        "🔗 SharePoint Integration",
        "💼 Financial Insights",
        "📊 PPTX Reports",
        "📋 Bulk Processing"
    ]
    
    for feature in features:
        st.markdown(f"- {feature}")

# Main content area
if selected == "🔐 Login":
    login.show_data()
    
if selected == "⚙️ Data Pipeline" :#and Action == "Sharepoint Authentication":
    if "Sharepoint Authentication" in st.session_state.selected_action:
        if "access_token" not in st.session_state or not st.session_state.access_token:
            st.error("❌ Please login first before accessing the data pipeline.")
            st.info("👈 Use the Login tab to authenticate with Microsoft.")
        else:
            app.main()
    # If file uploaded, show ingest button
    if "Select File Upload" in st.session_state.selected_action:
        st.info("A file has been uploaded. Click below to ingest data.")
        if st.button("🚀 Ingest Data", type="primary"):
            app.data_pipeline_upload()
# if selected == "⚙️ Data Pipeline":
#     if "Select File Upload" in st.session_state.selected_action: #and Action == "Select File Upload":
#         app.upload_main()
#     else:
#         app.data_pipeline_upload()
    
elif selected == "💬 Chat":
    if "index_name" not in st.session_state or not st.session_state.index_name:
        st.error("❌ Please run the data pipeline first to create a search index.")
        st.info("👈 Use the Data Pipeline tab to process your documents.")
    else:
        chat.main()

elif selected == "💼 Financial Insights":
    if "index_name" not in st.session_state or not st.session_state.index_name:
        st.error("❌ Please run the data pipeline first to create a search index.")
        st.info("👈 Use the Data Pipeline tab to process your documents.")
    else:
        insights.main()
        
elif selected == "📊 Analytics":
    st.markdown("### 📊 System Analytics")
    
    if "query_logs" in st.session_state and st.session_state.query_logs:
        logs = st.session_state.query_logs
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Queries", len(logs))
        
        with col2:
            avg_confidence = sum(log.get("confidence", 0) for log in logs) / len(logs)
            st.metric("Avg Confidence", f"{avg_confidence:.3f}")
        
        with col3:
            avg_time = sum(log.get("processing_time", 0) for log in logs) / len(logs)
            st.metric("Avg Time", f"{avg_time:.2f}s")
        
        with col4:
            total_sources = sum(log.get("sources_used", 0) for log in logs)
            st.metric("Total Sources", total_sources)
        
        # Query analysis
        st.markdown("### 🔍 Query Analysis")
        
        complexities = [log.get("query_analysis", {}).get("complexity", "unknown") for log in logs]
        query_types = [log.get("query_analysis", {}).get("query_type", "unknown") for log in logs]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Complexity Distribution:**")
            complexity_counts = {c: complexities.count(c) for c in set(complexities)}
            for comp, count in complexity_counts.items():
                st.write(f"- {comp.title()}: {count}")
        
        with col2:
            st.markdown("**Query Type Distribution:**")
            type_counts = {t: query_types.count(t) for t in set(query_types)}
            for qtype, count in type_counts.items():
                st.write(f"- {qtype.title()}: {count}")
        
        # Recent queries
        st.markdown("### 📝 Recent Queries")
        for i, log in enumerate(logs[-5:], 1):
            with st.expander(f"Query {i}: {log.get('query', 'Unknown')[:100]}..."):
                st.write(f"**Query:** {log.get('query', 'Unknown')}")
                st.write(f"**Confidence:** {log.get('confidence', 0):.3f}")
                st.write(f"**Processing Time:** {log.get('processing_time', 0):.2f}s")
                st.write(f"**Sources Used:** {log.get('sources_used', 0)}")
    
    else:
        st.info("No analytics data available yet. Start chatting to see analytics!")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 0.9rem; margin-top: 2rem;'>
        🤖Agentic RAG System | Powered by Azure AI Search + OpenAI | Financial Due Diligence Ready
    </div>
    """,
    unsafe_allow_html=True
)
