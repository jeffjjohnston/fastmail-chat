"""
A simple Flask application that integrates with OpenAI's API to handle email-related
tasks.
"""

import os
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
)
import markdown
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.responses.tool_param import Mcp
from markupsafe import Markup

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
FASTMAIL_API_KEY = os.getenv("FASTMAIL_API_KEY")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")
APP_SECRET_KEY = os.getenv("SECRET_KEY")

# Validate environment variables
if not APP_SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Please set it to a strong, secure value."
    )
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
if not BEARER_TOKEN:
    raise RuntimeError("BEARER_TOKEN environment variable is not set.")
if not FASTMAIL_API_KEY:
    raise RuntimeError("FASTMAIL_API_KEY environment variable is not set.")
if not MCP_SERVER_URL:
    raise RuntimeError("MCP_SERVER_URL environment variable is not set.")

client = OpenAI(api_key=OPENAI_API_KEY)

OPENAI_INSTRUCTIONS = "Use the Email tool. Assume email is from the user's own mailbox."

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

app = Flask(__name__)
app.secret_key = APP_SECRET_KEY


@app.template_filter("markdown")
def render_markdown(text: str) -> Markup:
    """Convert Markdown text to HTML using python-markdown."""
    html = markdown.markdown(
        text,
        extensions=["fenced_code", "codehilite", "tables"],
        output_format="html",
    )
    return Markup(html)


@app.route("/", methods=["GET", "POST"])
def index():
    """Main route for the application."""
    selected_model = session.get("model", DEFAULT_MODEL)
    if request.method == "POST":
        if request.is_json:
            data = request.get_json() or {}
            selected_model = data.get("model", selected_model)
            action = data.get("action")
            message = data.get("message", "")
        else:
            selected_model = request.form.get("model", selected_model)
            action = request.form.get("action")
            message = request.form.get("message", "")

        session["model"] = selected_model
        if action == "clear":
            session.pop("previous_response_id", None)
            session.pop("history", None)
            if request.is_json:
                return jsonify({"cleared": True})
            return redirect(url_for("index"))

        previous_id = session.get("previous_response_id")

        try:
            resp = client.responses.create(
                model=selected_model,
                tools=TOOLS,
                input=message,
                instructions=OPENAI_INSTRUCTIONS,
                previous_response_id=previous_id,
                reasoning={"summary": "auto"},
            )
        except Exception as exc:  # pylint: disable=broad-except
            flash(f"Error contacting OpenAI: {exc}", "error")
            return redirect(url_for("index"))

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

        if request.is_json:
            return jsonify(
                {
                    "assistant_html": str(render_markdown(resp.output_text)),
                    "reasoning_html": [
                        str(render_markdown(text)) for text in summaries
                    ],
                }
            )

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
