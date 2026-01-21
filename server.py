import threading
import requests
import time
import csv
from datetime import datetime
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import openai
import json

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================

# Load environment variables
load_dotenv()

# OKTA CONFIG
OKTA_ORG_URL = os.getenv("OKTA_ORG_URL")
OKTA_API_TOKEN = os.getenv("OKTA_API_TOKEN")
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID")

# SLACK CONFIG
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

# SETTINGS
ACCESS_DURATION_SECONDS = 60

# ==========================================
# 📚 MOCK DATA (The "Mellon" Knowledge Base)
# ==========================================
MOCK_JIRA_DB = {
    "TICKET-101": {
        "status": "In Progress", 
        "assignee": "jake@madeforsapiens.com", 
        "summary": "Fix CSS typo on login page",
        "type": "Bug",
        "severity": "Low"
    },
    "TICKET-404": {
        "status": "Active", 
        "assignee": "jake@madeforsapiens.com", 
        "summary": "CRITICAL: Production Payment Gateway Failure",
        "type": "Incident",
        "severity": "High"
    },
    "TICKET-900": {
        "status": "Closed", 
        "assignee": "other_dev@company.com", 
        "summary": "Update copyright year in footer",
        "type": "Task",
        "severity": "Low"
    }
}



# ==========================================
# 🛠️ HELPER FUNCTIONS (The "Brain")
# ==========================================

def log_audit(action, email, status):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("audit_log.csv", mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, email, action, status])
    print(f"📝 Audit Logged: {action} -> {status}")

def get_okta_headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"SSWS {OKTA_API_TOKEN}"
    }

def get_user_id(email):
    print(f"🔎 Looking up ID for: {email}...")
    url = f"{OKTA_ORG_URL}/api/v1/users/{email}"
    try:
        response = requests.get(url, headers=get_okta_headers())
        if response.status_code == 200:
            return response.json()['id']
    except Exception as e:
        print(f"❌ API Error: {e}")
    return None

def schedule_revocation(user_id, email, duration_minutes):
    """
    Waits for X minutes, then removes the user from the group.
    """
    print(f"⏳ Timer started: Revoking {email} in {duration_minutes} minutes...")
    
    # Calculate seconds
    duration_seconds = duration_minutes * 60 
    
    # Wait...
    time.sleep(duration_seconds)
    
    # Time's up! Revoke access.
    url = f"{OKTA_ORG_URL}/api/v1/groups/{TARGET_GROUP_ID}/users/{user_id}"
    try:
        requests.delete(url, headers=get_okta_headers())
        log_audit("REVOKED", email, "AUTO_TIMER_EXPIRED")
        print(f"🔒 Time's up. Access revoked for {email}.")
    except Exception as e:
        print(f"❌ Error revoking access: {e}")

# ==========================================
# 🧠 THE WORKER (The "Mellon" Workflow)
# ==========================================
def process_access_request(user_text, requester_id):
    """
    1. Analyzes intent with AI.
    2. Posts a risk-scored message to Slack.
    """
    print(f"🚀 Starting AI Workflow for: {user_text}")

    # 1. HARDCODED USER FOR DEMO
    # In production, we'd use get_user_id() to find the email
    user_email = "jake@madeforsapiens.com" 

    # 2. ASK THE BRAIN (This calls the AI function from Step 3)
    ai_decision = analyze_request_with_llm(user_email, user_text)
    
    # 3. DETERMINE UI COLORS based on Risk
    if ai_decision['risk_level'] == "HIGH":
        status_emoji = "⚠️"
        color = "#ff0000" # Red
        risk_text = "*HIGH RISK DETECTED*"
    else:
        status_emoji = "✅"
        color = "#36a64f" # Green
        risk_text = "*Low Risk (Verified)*"

    # 4. BUILD THE SLACK MESSAGE (Block Kit)
    slack_msg = {
        "channel": SLACK_CHANNEL_ID,
        "text": f"New Access Request from {user_email}",
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{status_emoji} Mellon Access Request"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*User:*\n{user_email}"},
                            {"type": "mrkdwn", "text": f"*Ticket Context:*\n{ai_decision['ticket_id'] or 'None'}"},
                            {"type": "mrkdwn", "text": f"*Risk Level:*\n{risk_text}"},
                            {"type": "mrkdwn", "text": f"*Recommended Duration:*\n{ai_decision['duration']} Minutes"}
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*AI Rationale:*\n> {ai_decision['rationale']}"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Approve Access"},
                                "style": "primary",
                                "value": f"approve_{user_email}", 
                                "action_id": "approve_request"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Deny"},
                                "style": "danger",
                                "value": "deny",
                                "action_id": "deny_request"
                            }
                        ]
                    }
                ]
            }
        ]
    }

    # 5. POST TO SLACK
    try:
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json=slack_msg
        )
        print(f"📨 Message sent to Slack: {r.status_code}")
    except Exception as e:
        print(f"❌ Error sending to Slack: {e}")

# ==========================================
# OpenAI: Provide Contextual Risk Socre Using LLM
# ==========================================   

def analyze_request_with_llm(user_email, user_text):
    print(f"🤔 AI analyzing request from {user_email}: {user_text}")
    
    # Initialize the OpenAI Client
    # Note: It automatically looks for OPENAI_API_KEY in your .env file
    client = openai.OpenAI()

    # The System Prompt: We feed the "Mellon" Mock DB into the AI's brain
    system_prompt = f"""
    You are a Senior Security Engineer. 
    Review the access request below against the provided JIRA CONTEXT.

    JIRA CONTEXT:
    {json.dumps(MOCK_JIRA_DB)}

    RULES:
    1. Extract the Ticket ID (e.g., TICKET-101) from the user's request.
    2. Look up the ticket in the JIRA CONTEXT.
    3. If the ticket exists AND matches the user's request, Risk = LOW.
    4. If ticket is missing, closed, or high-severity mismatch, Risk = HIGH.
    5. Duration: Recommend 30 mins for simple bugs, 60 mins for incidents.

    Return ONLY valid JSON in this format:
    {{
        "ticket_id": "TICKET-XXX" or null,
        "risk_level": "LOW" or "HIGH",
        "rationale": "One short sentence explaining why.",
        "duration": 30
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Cheap and fast for demos
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User: {user_email}\nRequest: {user_text}"}
            ],
            temperature=0 # Temperature 0 means "Be strict, don't be creative"
        )
        
        # Parse the JSON response from the AI
        ai_output = response.choices[0].message.content
        return json.loads(ai_output)

    except Exception as e:
        # FAIL-SAFE: If AI crashes, don't crash the bot. Return a safe default.
        print(f"⚠️ AI Analysis Failed: {e}")
        return {
            "ticket_id": "UNKNOWN",
            "risk_level": "HIGH",
            "rationale": "AI unavailable. Manual review required.",
            "duration": 30
        }     

# ==========================================
# 🌐 FLASK SERVER
# ==========================================
app = Flask(__name__)

# ==========================================
# ⚡ ACTION HANDLER (When Buttons are Clicked)
# ==========================================
@app.route('/slack/interactions', methods=['POST'])
def handle_slack_interactions():
    # 1. Parse the payload from Slack
    payload = json.loads(request.form['payload'])
    action = payload['actions'][0]
    action_id = action['action_id']
    approver_name = payload['user']['name'] 
    
    # 2. Handle "Approve"
    if action_id == "approve_request":
        email_to_approve = action['value'].split("_", 1)[1]
        print(f"👍 {approver_name} approved access for: {email_to_approve}")
        
        # A. Call Okta to add user
        user_id = get_user_id(email_to_approve)
        
        if user_id:
            url = f"{OKTA_ORG_URL}/api/v1/groups/{TARGET_GROUP_ID}/users/{user_id}"
            requests.put(url, headers=get_okta_headers())
            
            # B. Log & Timer
            log_audit("GRANTED", email_to_approve, f"Approved by {approver_name}")
            
            # Start 60-second revocation timer
            revocation_thread = threading.Thread(target=schedule_revocation, args=(user_id, email_to_approve, 1))
            revocation_thread.start()
            
            return jsonify({
                "replace_original": "true",
                "text": f"✅ *ACCESS GRANTED.*\nUser {email_to_approve} added for 1 minute.\n_⏳ Timer started..._"
            })
        else:
            # THIS IS THE MISSING PART
            return jsonify({
                "replace_original": "false",
                "text": f"❌ Error: Could not find Okta User ID for {email_to_approve}"
            })

    # 3. Handle "Deny"
    elif action_id == "deny_request":
        log_audit("DENIED", "N/A", f"Rejected by {approver_name}")
        return jsonify({
            "replace_original": "true",
            "text": f"🚫 *ACCESS DENIED BY {approver_name.upper()}.*"
        })

    return "", 200

# ==========================================
# 🌐 FLASK SERVER (The "Front Door")
# ==========================================
@app.route('/slack/command', methods=['POST'])
def handle_slash_command():
    # 1. Parse the incoming data from Slack
    data = request.form
    user_id = data.get('user_id')
    user_text = data.get('text') # The natural language intent

    # 2. Validation: Ensure they actually typed a reason
    if not user_text:
        return jsonify({
            "response_type": "ephemeral",
            "text": "🛡️ *Mellon:* Speak 'friend' and enter. (Please provide a reason or Ticket ID.)"
        })

    # 3. Start the background worker (The AI Workflow)
    # This keeps the main thread free to respond to Slack immediately
    worker = threading.Thread(target=process_access_request, args=(user_text, user_id))
    worker.start()

    # 4. Reply immediately so Slack doesn't timeout (The 3-second rule)
    return jsonify({
        "response_type": "ephemeral",
        "text": f"🪄 *Mellon* is consulting the lore regarding: _{user_text}_..."
    })

if __name__ == '__main__':
    print("🚀 Mellon Bot Server is live on Port 3000...")
    app.run(port=3000)