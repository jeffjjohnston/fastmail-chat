"""
A simple Flask application that integrates with OpenAI's API to handle email-related
tasks.
"""

import os
import re
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.responses.tool_param import Mcp
from markupsafe import Markup, escape

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Please set it to a strong, secure value."
    )


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

# Validate environment variables
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
if not BEARER_TOKEN:
    raise RuntimeError("BEARER_TOKEN environment variable is not set.")
if not FASTMAIL_API_KEY:
    raise RuntimeError("FASTMAIL_API_KEY environment variable is not set.")
if not MCP_SERVER_URL:
    raise RuntimeError("MCP_SERVER_URL environment variable is not set.")

client = OpenAI(api_key=OPENAI_API_KEY)

TOOLS = [
    Mcp(
        type="mcp",
        server_label="Email",
        server_url=MCP_SERVER_URL,
        require_approval="never",
        headers={
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "fastmail-api-token": FASTMAIL_API_KEY,
        },
    )
]

MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "o4-mini",
    "o3",
]
DEFAULT_MODEL = "gpt-4o-mini"


@app.route("/", methods=["GET", "POST"])
def index():
    """Main route for the application."""
    selected_model = session.get("model", DEFAULT_MODEL)
    if request.method == "POST":
        if request.form.get("action") == "clear":
            session.pop("previous_response_id", None)
            session.pop("history", None)
            return redirect(url_for("index"))

        message = request.form.get("message", "")
        selected_model = request.form.get("model", selected_model)
        session["model"] = selected_model
        previous_id = session.get("previous_response_id")

        resp = client.responses.create(
            model=selected_model,
            tools=TOOLS,
            input=message,
            instructions="Use the Email tool",
            previous_response_id=previous_id,
            reasoning={"summary": "auto"},
        )

        summaries: list[str] = []
        for output in resp.output:
            if output.type == "reasoning" and getattr(output, "summary", None):
                for summary in output.summary:
                    summaries.append(summary.text)

        history = session.get("history", [])
        history.append(
            {
                "user": message,
                "assistant": resp.output_text,
                "reasoning": summaries,
            }
        )
        session["history"] = history
        session["previous_response_id"] = resp.id

        return redirect(url_for("index"))

    history = session.get("history", [])
    return render_template(
        "index.html",
        history=history,
        models=MODELS,
        selected_model=selected_model,
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
