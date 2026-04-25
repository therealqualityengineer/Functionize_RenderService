from flask import Flask, request, jsonify
import requests
import base64
import os

app = Flask(__name__)

# 🔹 Jira Config
JIRA_DOMAIN = "aruntieto-demo.atlassian.net"
EMAIL = os.getenv("JIRA_EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")

# 🔐 Encode auth
auth = base64.b64encode(f"{EMAIL}:{API_TOKEN}".encode()).decode()

# 🔹 OpenRouter Config
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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

        # 🔥 HIGH-QUALITY PROMPT
        prompt = f"""
Convert the following manual test case into clean, automation-ready Functionize steps.

CONTEXT:
- Environment: QA
- Base URL: https://practicesoftwaretesting.com

STRICT RULES:
- DO NOT return code or markdown
- Include necessary navigation steps (like clicking Login page/button before typing)
- DO NOT use ``` or quotes
- Each step must be on a new line
- Use only these actions: Open, Click, Type, Verify
- Use clear field names (Username field, Password field)
- Keep steps short and readable
- Add final verification step
- No explanation

EXAMPLE FORMAT (structure only, NOT data):
Open https://example.com
Click Login button
Type user@example.com into Username field
Type password into Password field
Click Login button
Verify dashboard page is displayed

TEST CASE:
{description}
"""

        # 🔥 OpenRouter API call
        try:
            ai_response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openrouter/free",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }
            )

            print("\n🔍 Raw OpenRouter Response:\n", ai_response.text)

            result = ai_response.json()

            # ✅ Safe extraction
            if "choices" in result and len(result["choices"]) > 0:
                steps = result["choices"][0]["message"]["content"]
            else:
                steps = "AI returned no valid response"

        except Exception as e:
            print("❌ OpenRouter Error:", str(e))
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