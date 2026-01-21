JIT-Admin-Bot: Slack-Native Identity Orchestrator

A Zero-Trust Access Management tool that automates temporary "Break Glass" privileges via Slack commands and Okta APIs.

-----------

📋 Project Overview

The Problem: Permanent "Super Admin" access is a major security risk (Standing Privilege). However, manual provisioning processes are slow, leading to "Shadow IT" or dangerous password sharing.

The Solution: This application implements a Just-in-Time (JIT) access workflow directly within Slack. It allows authorized users to request ephemeral administrative access, which is automatically provisioned and revoked after a set duration, ensuring a Zero Trust posture.

Key Features:

-Slack-Native Workflow: Triggered via /request-admin [email] slash commands.
-Asynchronous Processing: Utilizes background threading to handle API latency without blocking the user interface.
-Human-in-the-Loop Governance: Enforces a mandatory approval step (✅ reaction) from a designated Security Officer before granting access.
-Automated Lifecycle: Automatically grants and revokes Okta group membership (Admin Roles) after 30 minutes.
-Audit Trail: Logs every request, approval, and revocation event to audit_log.csv for compliance evidence.

----------

----------

🛠 Tech Stack

- **Backend:** Python 3, Flask (Web Server)
- **AI Engine:** OpenAI API (Context analysis)
- **Tunneling:** Ngrok (Localhost exposure)
- **Identity Provider:** Okta (SSWS API)
- **Interface:** Slack API (Webhooks & Block Kit)
- **Architecture:** Event-Driven, Threaded

----------

⚙️ Configuration & Setup

**Important:** This project uses a `.env` file to manage secrets. Never commit your API keys to GitHub.

1. **Clone the Repository**
   ```bash
   git clone [your-repo-link]
   cd Mellon-JIT-Bot

----------

⚙️ The Workflow (Architecture)

1. The Trigger: User types /request-admin user@company.com in Slack.
2. The Hook: Slack sends a JSON payload to the local Flask server via Ngrok.
3. The Thread: The server validates the request, spawns a background worker thread, and immediately acknowledges Slack to prevent timeout.
4. The Gate: The worker thread posts an approval card to the #security-ops channel and polls for a ✅ reaction.
5. The Grant: Upon approval, the script calls the Okta API to add the target user to the JIT_Super_Admins group.
6. The Timer: The thread sleeps for the requested duration (e.g., 30 mins).
7. The Revoke: Access is automatically removed, and the session is closed.

----------

🚀 Setup & Installation

1. Prerequisites
-Python 3.x
-Ngrok Account (Free tier is sufficient)
-Okta Admin Access
-Slack App with commands and chat:write permissions

2. Slack Configuration
Before running the code, you must set up the "Security Operations" channel where approvals will happen.

-Create a Channel: Create a public channel named #temp-admin-requests (or similar).
-Get Channel ID: Right-click the channel name in the sidebar $\to$ Copy Link. Paste it somewhere. The ID is the last part of the URL (e.g., C01234567).
-Invite the Bot: Go to the #security-ops channel and type /invite @[Your-App-Name]. Critical Step: If the bot is not invited, it cannot post approval requests.

3. Okta Configuration

1. Create Group: Create a group named JIT_Temp_Super_Admins in your Okta Directory.
2. Get Group ID: Go to the group's page and copy the ID from the URL (starts with 00g...).
3. Get API Token: Go to Security $\to$ API $\to$ Tokens and generate a new SSWS Token.


4. Application Config
Open server.py and update the Configuration Section with your specific IDs:

# OKTA CONFIG
OKTA_ORG_URL = "https://[your-org].okta.com"
OKTA_API_TOKEN = "x-x-x-x..."      # Your SSWS Token
TARGET_GROUP_ID = "00g..."         # The ID of the 'JIT_Super_Admins' group

# SLACK CONFIG
SLACK_BOT_TOKEN = "xoxb-..."       # Your Bot User OAuth Token
SLACK_CHANNEL_ID = "C0..."         # The ID of your #security-ops channel

(Note: In a production environment, these credentials should be stored in environment variables or a Secrets Manager, not hardcoded.)


5. Running the Application

1. Start the Server with [bash python3 server.py]
2. Start the Tunnel: Open a second terminal and run Ngrok to expose port 3000 with [bash ./ngrok http 3000]
3. Update Slack Webhook: Copy the Ngrok URL (e.g., https://xyz.ngrok-free.app) and update your Slash Command in the Slack API Dashboard:
Command: /request-admin
Request URL: https://[your-ngrok-url]/slack/command








