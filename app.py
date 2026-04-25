from flask import Flask, request, jsonify
import requests
import base64
import os
from google import genai

app = Flask(__name__)

# 🔹 Jira Config
JIRA_DOMAIN = "aruntieto-demo.atlassian.net"
EMAIL = os.getenv("JIRA_EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")

# 🔐 Encode auth
auth = base64.b64encode(f"{EMAIL}:{API_TOKEN}".encode()).decode()

# 🔹 Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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

# 🔹 Health check
@app.route("/", methods=["GET"])
def home():
    return "Jira AI Webhook Running 🚀", 200

# 🔹 Webhook
@app.route("/jira-webhook", methods=["POST"])
def jira_webhook():
    try:
        data = request.get_json(force=True)

        issue_key = data["issue"]["key"]
        print(f"\nReceived webhook for: {issue_key}")

        # 🔹 Fetch Jira issue
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

        description_raw = issue_data["fields"]["description"]
        description = extract_text(description_raw)

        print("\n--- Clean Description ---\n", description)

        # 🔥 GEMINI AI
        prompt = f"""
Convert the following manual test case into Functionize test steps.

Rules:
- Use Click, Type, Verify
- Keep steps clear and short
- Add final verification
- No explanation

Test Case:
{description}
"""

        try:
            ai_response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )

            # 🔍 FULL DEBUG (IMPORTANT)
            print("\n🔍 Raw Gemini Response:\n", ai_response)

            # ✅ SAFE extraction
            if hasattr(ai_response, "text") and ai_response.text:
                steps = ai_response.text
            else:
                steps = str(ai_response)

        except Exception as e:
            print("❌ Gemini Error:", str(e))
            steps = f"AI failed: {str(e)}"

        print("\n--- AI Generated Steps ---\n", steps)

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


# 🔹 Run server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)