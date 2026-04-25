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

# 🔹 Load Mini RAG context
def load_app_context():
    try:
        with open("app_context.txt", "r") as f:
            return f.read()
    except Exception:
        return "No app context available"

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

        # 🔹 Load RAG context
        app_context = load_app_context()

        # 🔥 FINAL PROMPT (Mini RAG + Full Output)
        prompt = f"""
You are an expert QA automation engineer.

APPLICATION CONTEXT:
{app_context}

TASK:
Generate structured test design.

OUTPUT FORMAT:

--- FUNCTIONIZE INPUT START ---
<ONLY steps here>
--- FUNCTIONIZE INPUT END ---

--- NEGATIVE TEST SCENARIOS ---
- Scenario 1: ...
- Scenario 2: ...

--- TEST COVERAGE ANALYSIS ---
- Covered:
- Missing:
- Risks:

RULES:
- Use credentials from context (do NOT invent data)
- Use correct navigation (e.g., Sign in before login)
- Use real field names (Email address, Password)
- Use only: Open, Click, Type, Verify
- No code, no markdown, no quotes
- Include realistic negative scenarios
- Coverage must reflect actual gaps
- Output must be clean and structured exactly as defined

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

            if "choices" in result and len(result["choices"]) > 0:
                output = result["choices"][0]["message"]["content"]
            else:
                output = "AI returned no valid response"

        except Exception as e:
            print("❌ OpenRouter Error:", str(e))
            output = f"AI failed: {str(e)}"

        print("\n--- FINAL AI OUTPUT ---\n", output)

        # 🔹 Add comment to Jira
        comment_url = f"https://{JIRA_DOMAIN}/rest/api/3/issue/{issue_key}/comment"

        comment_text = f"""🤖 AI Generated Test Design

👉 Copy ONLY the below section into Functionize

{output}
"""

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
                                "text": comment_text
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