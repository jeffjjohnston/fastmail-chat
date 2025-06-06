# fastmail-chat

A simple Flask chat interface that uses OpenAI with your Fastmail MCP server.

## Setup

Install dependencies and set the following environment variables:

- `OPENAI_API_KEY` – your OpenAI API key
- `BEARER_TOKEN` – bearer token for the MCP server
- `FASTMAIL_API_KEY` – Fastmail API key
- `MCP_SERVER_URL` – URL of the Fastmail MCP server
- `SECRET_KEY` – (optional) Flask session secret

Run the server with:

```bash
python app.py
```

The web page is available at <http://localhost:5000>. Use the *Clear Conversation* button to reset context.
