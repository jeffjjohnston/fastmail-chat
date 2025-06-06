import os
import re
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from openai import OpenAI
from markupsafe import Markup, escape

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is not set. Please set it to a strong, secure value.")

# Simple markdown renderer for basic formatting
@app.template_filter("markdown")
def render_markdown(text: str) -> Markup:
    """Convert a small subset of Markdown to HTML."""
    text = escape(text)

    # fenced code blocks
    text = re.sub(r"```(.*?)```", r"<pre><code>\1</code></pre>", text, flags=re.S)
    # inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # emphasis
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)

    # simple bullet lists
    lines = text.splitlines()
    processed = []
    in_list = False
    for line in lines:
        if re.match(r"^\s*[-*] ", line):
            if not in_list:
                processed.append("<ul>")
                in_list = True
            item = re.sub(r"^\s*[-*]\s+", "", line)
            processed.append(f"<li>{item}</li>")
        else:
            if in_list:
                processed.append("</ul>")
                in_list = False
            processed.append(line)
    if in_list:
        processed.append("</ul>")

    return Markup("<br>".join(processed))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
FASTMAIL_API_KEY = os.getenv("FASTMAIL_API_KEY")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")

client = OpenAI(api_key=OPENAI_API_KEY)

TOOLS = [
    {
        "type": "mcp",
        "server_label": "Email",
        "server_url": MCP_SERVER_URL,
        "require_approval": "never",
        "headers": {
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "fastmail-api-token": FASTMAIL_API_KEY,
        },
    }
]

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if request.form.get("action") == "clear":
            session.pop("previous_response_id", None)
            session.pop("history", None)
            return redirect(url_for("index"))

        message = request.form.get("message", "")
        previous_id = session.get("previous_response_id")

        resp = client.responses.create(
            model="gpt-4o-mini",
            tools=TOOLS,
            input=message,
            instructions="Use the Email tool",
            previous_response_id=previous_id,
        )

        history = session.get("history", [])
        history.append({"user": message, "assistant": resp.output_text})
        session["history"] = history
        session["previous_response_id"] = resp.id

        return redirect(url_for("index"))

    history = session.get("history", [])
    return render_template("index.html", history=history)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
