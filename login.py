
import streamlit as st
from streamlit_msal import Msal
import requests
import app

CLIENT_ID = "d9866f97-2533-4caa-b4b4-a2fb62acbd51"
TENANT_ID = "84812faf-3276-46f6-a54e-7562ed4a7a60" # Replace with your Directory (tenant) ID
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["User.Read", "Sites.Read.All", "Files.Read.All"]

def get_sharepoint_sites(access_token):
    """Fetch SharePoint sites using multiple discovery methods"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    sites = []
    site_names = set()
    
    with st.spinner("🔍 Discovering your SharePoint sites..."):
        # Method 1: Search for sites
        try:
            search_url = "https://graph.microsoft.com/v1.0/sites?search=*"
            response = requests.get(search_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for site in data.get('value', []):
                    if site.get('displayName') and site['displayName'] not in site_names:
                        sites.append(site)
                        site_names.add(site['displayName'])
        except Exception as e:
            st.warning(f"Error searching sites: {str(e)}")
        
        # Method 2: Get followed sites
        try:
            followed_url = "https://graph.microsoft.com/v1.0/me/followedSites"
            response = requests.get(followed_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for site in data.get('value', []):
                    if site.get('displayName') and site['displayName'] not in site_names:
                        sites.append(site)
                        site_names.add(site['displayName'])
        except Exception as e:
            st.info(f"Could not fetch followed sites: {str(e)}")
    
    return sites

def main():
    # st.set_page_config() must only be called once at the top of main.py, not here
    
    # Initialize session state variables
    if 'should_authenticate' not in st.session_state:
        st.session_state.should_authenticate = False
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'selected_site' not in st.session_state:
        st.session_state.selected_site = None
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None
    
    # Center the content
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
            <div style='text-align: center; padding: 50px 0;'>
                <h1>🔐 SharePoint Data Pipeline</h1>
                <p style='font-size: 18px; color: #666;'>
                    Secure access to your SharePoint data and analytics
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        # Check if user is already authenticated and has selected a site
        if st.session_state.authenticated and st.session_state.selected_site:
            st.success("✅ Authentication Complete!")
            st.info(f"**Authenticated User:** {st.session_state.user_info.get('name', 'User')}")
            st.info(f"**Selected Site:** {st.session_state.selected_site.get('displayName', 'Unknown')}")
            
            st.markdown("---")
            st.markdown("### 🚀 Ready to Continue")
            st.markdown("""
                **Great! You're all set up.** 
                
                👈 **Use the sidebar menu** to navigate to:
                - **Data Pipeline** - Process your SharePoint documents
                - **Chat** - Interact with your processed data
                - **Financial Insights** - Analyze financial information
            """)
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔄 Change Site", use_container_width=True):
                    st.session_state.selected_site = None
                    st.rerun()
            
            with col_b:
                if st.button("👋 Sign Out", use_container_width=True):
                    # Clear all session state
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()
            
            return
        
        # Show authentication interface if not authenticated
        if not st.session_state.authenticated:
            st.markdown("### 🔑 Microsoft Authentication Required")
            st.markdown("Click the button below to sign in with your Microsoft account and access SharePoint sites.")
            
            # SIMPLE FIX: Only show MSAL after user clicks button
            if not st.session_state.should_authenticate:
                # Show sign-in button - NO automatic popup
                if st.button("🚀 Sign in with Microsoft", type="primary", use_container_width=True):
                    st.session_state.should_authenticate = True
                    st.rerun()
            else:
                # Now initialize MSAL - popup will appear
                st.info("🔄 Initializing Microsoft authentication...")
                
                auth_data = Msal.initialize_ui(
                    client_id=CLIENT_ID,
                    authority=AUTHORITY,
                    scopes=SCOPES,
                    connecting_label="🔄 Connecting to Microsoft...",
                    disconnected_label="❌ Authentication failed - please try again",
                    sign_in_label="🚀 Sign in with Microsoft",
                    sign_out_label="👋 Sign out"
                )
                
                if auth_data:
                    st.session_state.authenticated = True
                    st.session_state.access_token = auth_data.get('accessToken')
                    st.session_state.user_info = auth_data.get('account', {})
                    # Capture user email/UPN if available for later upload identification
                    account = st.session_state.user_info or {}
                    possible_email = account.get('username') or account.get('upn') or account.get('email')
                    if possible_email:
                        st.session_state.user_email = possible_email
                    
                    st.success(f"✅ Welcome, {st.session_state.user_info.get('name', 'User')}!")
                    st.rerun()
        
        # Site selection interface (only show if authenticated but no site selected)
        if st.session_state.authenticated and not st.session_state.selected_site:
            st.markdown("---")
            st.markdown("### 🏢 Select Your SharePoint Site")
            
            # Fetch SharePoint sites
            sites = get_sharepoint_sites(st.session_state.access_token)
            
            if sites:
                st.success(f"✅ Found {len(sites)} SharePoint sites")
                
                # Create site selection dropdown
                site_options = {f"{site['displayName']}": site for site in sites}
                selected_site_name = st.selectbox(
                    "📁 Choose a site to work with:",
                    options=list(site_options.keys()),
                    index=0,
                    help="Select the SharePoint site you want to process data from"
                )
                
                if selected_site_name:
                    selected_site = site_options[selected_site_name]
                    
                    # Show site preview
                    st.markdown("#### 📋 Site Preview")
                    col_x, col_y = st.columns(2)
                    with col_x:
                        st.metric("Site Name", selected_site.get('displayName', 'N/A'))
                        st.metric("Created", selected_site.get('createdDateTime', 'N/A')[:10] if selected_site.get('createdDateTime') else 'N/A')
                    with col_y:
                        st.metric("Site ID", selected_site.get('id', 'N/A')[:20] + "..." if selected_site.get('id') else 'N/A')
                        st.metric("Web URL", "Available" if selected_site.get('webUrl') else 'N/A')
                    
                    # Confirm site selection
                    if st.button("✅ Confirm Site Selection", type="primary", use_container_width=True):
                        st.session_state.selected_site = selected_site
                        st.success(f"🎉 Site '{selected_site['displayName']}' selected successfully!")
                        st.rerun()
            else:
                st.warning("⚠️ No SharePoint sites found. This could be due to:")
                st.markdown("""
                - **Permissions**: You may not have access to any SharePoint sites
                - **Organization Policy**: Your organization may restrict site discovery
                - **New Account**: No sites have been created or shared with your account yet
                
                **Next Steps:**
                - Contact your SharePoint administrator
                - Verify you have been granted access to at least one SharePoint site
                - Try accessing SharePoint through the web interface first
                """)

def show_data():

    section = [ "Sharepoint Authentication", "Select File Upload"]
    
    # Create the radio button selection with the placeholder as default
    selected_action = st.radio("Choose an action", options=section, index=0)
    st.session_state.selected_action = selected_action
    
    
    # Authentication section
    if selected_action == "Sharepoint Authentication":
        main()
    # Site selection section
    elif selected_action == "Select File Upload":
        if not st.session_state.get('authenticated'):
            st.error("❌ Please sign in with Microsoft before uploading files.")
            st.info("Go to Sharepoint Authentication above and complete sign-in.")
        else:
            app.upload_main()  # Saves file and user email, does not process
            st.warning("File uploaded! 👉 Please go to the Data Pipeline tab to run ingestion.")
    # Return the selected action
    return st.session_state.selected_action
