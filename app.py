import streamlit as st
import imaplib
import email
from email.header import decode_header
import os
import urllib.parse
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool

# 1. PAGE CONFIG
st.set_page_config(page_title="AI Inbox Manager", page_icon="📧", layout="wide")
st.title("📧 Bank AI Inbox Manager")
st.markdown("Select an unread email from the sidebar to generate a response.")

# 2. EMAIL FETCHING LOGIC (IMAP)
def get_unread_emails(username, password, limit=5):
    email_list = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(username, password)
        mail.select("inbox")
        status, messages = mail.search(None, 'UNSEEN')
        
        email_ids = messages[0].split()
        if not email_ids: return []

        latest_ids = email_ids[-limit:]
        latest_ids.reverse() 

        for e_id in latest_ids:
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    sender = msg.get("From")
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = msg.get_payload(decode=True).decode()
                    
                    email_list.append({"subject": subject, "sender": sender, "body": body})
        return email_list
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return []

# 3. SIDEBAR CONFIGURATION
with st.sidebar:
    st.header("🔐 Setup")
    gmail_user = st.text_input("Gmail Address", placeholder="you@gmail.com")
    gmail_pass = st.text_input("App Password", type="password")
    gemini_key = st.text_input("Gemini API Key", type="password") 
    st.divider()

    if st.button("🔄 Fetch Unread Emails"):
        if gmail_user and gmail_pass:
            with st.spinner("Scanning Inbox..."):
                emails = get_unread_emails(gmail_user, gmail_pass, limit=5)
                if emails:
                    st.session_state['email_list'] = emails
                    st.success(f"Found {len(emails)} unread emails!")
                else:
                    st.warning("No unread emails found.")
        else:
            st.error("Please enter credentials first.")

    selected_email_data = None
    if 'email_list' in st.session_state and st.session_state['email_list']:
        st.subheader("Select Email to Process:")
        email_options = [f"{i+1}. {e['sender']} - {e['subject'][:20]}..." for i, e in enumerate(st.session_state['email_list'])]
        selected_option = st.selectbox("Choose one:", email_options)
        index = email_options.index(selected_option)
        selected_email_data = st.session_state['email_list'][index]

# 4. AGENT SETUP
class BankPolicyTool(BaseTool):
    name: str = "Search Bank Policy"
    description: str = "Useful to find bank rules."
    def _run(self, query: str) -> str:
        policies = {
            "fraud": "POLICY 9.1: Unauthorized Transaction. If reported within 24 hours, 0 liability. Immediate freeze.",
            "refund": "POLICY 4.2: Refunds <$50 auto-credit. >$50 require Manager Approval.",
            "fee": "POLICY 2.1: Overdraft fees $35. Waivable once per year."
        }
        for key, text in policies.items():
            if key in query.lower(): return text
        return "Refer to General Terms."

@st.cache_resource
def create_crew(api_key):
    # Securely use the API key passed from the sidebar
    os.environ["AIzaSyBiwgmdDcnNgdZ9m_Sn88j0vjPVeQIAv2I"] = api_key
    my_llm = LLM(model="gemini/gemini-2.5-flash", api_key=api_key)

    triage = Agent(role='Triage', goal='Classify urgency.', backstory='Bank Manager.', llm=my_llm)
    analyst = Agent(role='Analyst', goal='Extract data.', backstory='Data extractor.', llm=my_llm)
    writer = Agent(role='Support Lead', goal='Draft response.', backstory='Support Agent.', llm=my_llm, tools=[BankPolicyTool()])
    
    return triage, analyst, writer

# 5. MAIN INTERFACE
if selected_email_data:
    st.subheader(f"📨 Reading: {selected_email_data['subject']}")
    st.caption(f"From: {selected_email_data['sender']}")
    
    with st.expander("View Full Email Body", expanded=True):
        st.write(selected_email_data['body'])

    st.divider()

    if st.button("🚀 Generate AI Response"):
        if not gemini_key:
            st.error("Please enter Gemini API Key.")
        else:
            with st.spinner("Agents are working..."):
                triage, analyst, writer = create_crew(gemini_key)
                email_text = selected_email_data['body']
                
                t_classify = Task(description=f"Analyze urgency: {email_text}", expected_output="Urgency level.", agent=triage)
                t_extract = Task(description=f"Extract entities from: {email_text}", expected_output="List of data.", agent=analyst)
                t_draft = Task(description="Draft a reply using policy tool.", expected_output="Final email text.", agent=writer)

                crew = Crew(agents=[triage, analyst, writer], tasks=[t_classify, t_extract, t_draft], process=Process.sequential, max_rpm=3)
                result = crew.kickoff()

                st.success("Draft Ready!")
                st.subheader("📝 AI Draft")
                st.write(result.raw)

                subject = f"Re: {selected_email_data['subject']}"
                body = urllib.parse.quote(result.raw)
                st.markdown(f"""<a href="mailto:?subject={subject}&body={body}" target="_blank" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">📧 Open in Email Client</a>""", unsafe_allow_html=True)
else:
    st.info("👈 Connect your Gmail and click 'Fetch Unread Emails' to start.")