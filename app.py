from flask import Flask, request, jsonify
import requests
import base64
import os

app = Flask(__name__)

# 🔹 Jira Config
JIRA_DOMAIN = "aruntieto-demo.atlassian.net"
EMAIL = os.getenv("JIRA_EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")

auth = base64.b64encode(f"{EMAIL}:{API_TOKEN}".encode()).decode()

# 🔹 OpenRouter Config
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 🔹 Extract Jira description
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

# 🔹 Load RAG context
def load_app_context():
    try:
        with open("app_context.txt", "r") as f:
            return f.read()
    except:
        return ""

# 🔹 Detect test type
def detect_test_type(description):
    desc = description.lower()
    if "logout" in desc:
        return "logout"
    elif "login" in desc:
        return "login"
    else:
        return "generic"

# 🔹 AI Call
def call_ai(prompt):
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "mistralai/mistral-7b-instruct",
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strict QA automation generator. Follow output format EXACTLY."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
    )

    result = response.json()

    if "choices" in result and len(result["choices"]) > 0:
        return result["choices"][0]["message"]["content"]

    return None

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
            return jsonify({"error": issue_data}), 400

        description = extract_text(issue_data["fields"]["description"])

        print("\n--- Description ---\n", description)

        app_context = load_app_context()
        test_type = detect_test_type(description)

        # 🔥 Dynamic task
        if test_type == "login":
            task = "Generate COMPLETE test design for login functionality"
        elif test_type == "logout":
            task = "Generate COMPLETE test design for logout functionality"
        else:
            task = "Generate test steps based on the scenario"

        # 🔥 FINAL PROMPT
        prompt = f"""
You are a QA automation expert.

APPLICATION CONTEXT:
{app_context}

TASK:
{task}

STRICT OUTPUT FORMAT:

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
- Follow format EXACTLY
- Use correct flow (login/logout)
- Use real context data
- Use only: Open, Click, Type, Verify
- No markdown, no code, no quotes
- No extra text outside format

TEST CASE:
{description}
"""

        # 🔁 Retry mechanism
        output = None

        for attempt in range(2):
            print(f"🔁 AI Attempt {attempt + 1}")

            output = call_ai(prompt)

            if output and "--- FUNCTIONIZE INPUT START ---" in output:
                print("✅ Valid output")
                break
            else:
                print("⚠️ Invalid output, retrying...")

        # ❌ Final failure
        if not output or "--- FUNCTIONIZE INPUT START ---" not in output:
            output = """⚠️ AI could not generate valid structured output.
Please refine the user story and try again."""

        print("\n--- FINAL OUTPUT ---\n", output)

        # 🔹 Post to Jira
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
        requests.post(comment_url, json=comment_body, headers=headers)

        return jsonify({"status": "Success", "issue": issue_key})

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"error": str(e)}), 500


# 🔹 Run server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)