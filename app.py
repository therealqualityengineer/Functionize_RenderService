from flask import Flask, request, jsonify
import requests
import base64

app = Flask(__name__)
app.config["ALLOWED_HOSTS"] = ["*"]

# 🔹 Jira Config (UPDATE THESE)
JIRA_DOMAIN = "aruntieto-demo.atlassian.net"
EMAIL = "arunramalingam99@gmail.com"
API_TOKEN = "ATATT3xFfGF0TJe-zYk6J70kJWiWeqiO3AwzN55rYtjzYmq7zmvUyBOz4-3CEa_C0lhFqmMmmQveAjCPNTSAqd1tqPw_RbM1MzcA71keTAtwTnWqKB2y1vP6q6agU7xDw9Fysmt-mUuNZzQL8ccePy-2bj8gdsowm7CG5Lctcm6JRIo1YZiUTy4=95EAB6A6"

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
            return jsonify({"error": issue_data})

        # 🔹 Extract description
        description_raw = issue_data["fields"]["description"]
        description = extract_text(description_raw)

        print("\n--- Clean Description ---\n", description)

        # 🔥 MOCK AI OUTPUT (no API dependency)
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
        return jsonify({"error": str(e)})

# 🔹 Run server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)