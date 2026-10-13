"""
app.py - Flask web server for VakSetu, a multilingual computational Sanskrit chatbot.

Routes
  GET  /          chat interface
  GET  /health    health check used by Docker HEALTHCHECK and the Jenkins smoke test
  POST /api/chat  {"message": "...", "language": "auto|en|sa|hi|ta"} -> bot reply (JSON)
"""

import os

from flask import Flask, jsonify, render_template, request

from sanskrit_engine import BOT_NAME, SUPPORTED_LANGUAGES, VERSION, get_reply

app = Flask(__name__)
app.json.ensure_ascii = False      # keep Devanagari / Tamil readable in JSON


@app.get("/")
def home():
    return render_template("index.html", version=VERSION, languages=SUPPORTED_LANGUAGES)


@app.get("/health")
def health():
    return jsonify(status="ok", bot=BOT_NAME, version=VERSION)


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    language = str(data.get("language", "auto"))
    if not message:
        return jsonify(error="Type a message first."), 400
    return jsonify(get_reply(message, language))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
