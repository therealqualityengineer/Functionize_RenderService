from flask import Flask, request, jsonify
import requests
import base64
import os

app = Flask(__name__)

# 🔹 Jira Config (from environment variables)
JIRA_DOMAIN = "aruntieto-demo.atlassian.net"
EMAIL = os.getenv("JIRA_EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")

# 🔐 Encode auth
auth = base64.b64encode(f"{EMAIL}:{API_TOKEN}".encode()).decode()

# 🔹 Extract Jira description (ADF → text)
def extract_text(description):
    text = ""

    if not description:
        return text

    for block in description.get("content", []):
        if block["type"] == "paragraph":
            for item in block.get("content", []):
                if item["type"] == "text":
                    text += item["text"] + " "
            text += "\n"

    return text.strip()

# 🔹 Health check (for testing)
@app.route("/", methods=["GET"])
def home():
    return "Jira AI Webhook Running 🚀", 200

# 🔹 Webhook endpoint
@app.route("/jira-webhook", methods=["POST"])
def jira_webhook():
    try:
        data = request.get_json(force=True)

        # 🔹 Get issue key from webhook
        issue_key = data["issue"]["key"]
        print(f"\nReceived webhook for: {issue_key}")

        # 🔹 Fetch full Jira issue
        url = f"https://{JIRA_DOMAIN}/rest/api/3/issue/{issue_key}"

        headers = {
            "Authorization": f"Basic {auth}",
            "Accept": "application/json"
        }

        response = requests.get(url, headers=headers)
        issue_data = response.json()

        if "fields" not in issue_data:
            print("❌ Jira API Error:", issue_data)
            return jsonify({"error": issue_data}), 400

        # 🔹 Extract description
        description_raw = issue_data["fields"]["description"]
        description = extract_text(description_raw)

        print("\n--- Clean Description ---\n", description)

        # 🔥 MOCK AI OUTPUT (replace later with OpenAI/Gemini)
        steps = f"""
Environment: QA
Base URL: https://practicesoftwaretesting.com

Open Application
Navigate to base URL
Click Login link
Type "admin@practicesoftwaretesting.com" into Username field
Type "welcome01" into Password field
Click Login button
Verify dashboard is displayed
"""

        print("\n--- Generated Steps ---\n", steps)

        # 🔹 Add comment to Jira
        comment_url = f"https://{JIRA_DOMAIN}/rest/api/3/issue/{issue_key}/comment"

        comment_body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "🤖 AI Generated Test Steps:\n\n" + steps
                            }
                        ]
                    }
                ]
            }
        }

        headers.update({"Content-Type": "application/json"})

        comment_response = requests.post(comment_url, json=comment_body, headers=headers)

        print("\n--- Jira Comment Status ---\n", comment_response.status_code)

        return jsonify({"status": "Success", "issue": issue_key})

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"error": str(e)}), 500


# 🔹 Run server (Render compatible)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)