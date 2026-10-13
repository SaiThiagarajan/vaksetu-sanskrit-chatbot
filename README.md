# वाक्सेतुः VakSetu - Multilingual Computational Sanskrit Chatbot

A Flask chatbot that applies simple computational linguistics to Sanskrit and
replies in **English, Sanskrit, Hindi and Tamil** (script is auto-detected).

Built for the Agile Development Process and DevOps Lab, Continuous Integration sprint
(Jenkins + Docker), by Sai Thiagarajan (23MIS1150).

## Commands

| Command | What it does | Example |
|---|---|---|
| `translit <text>` | Devanagari <-> IAST transliteration | `translit संस्कृतम्` |
| `sandhi <w1> + <w2>` | Vowel sandhi with the Paninian sutra | `sandhi deva + ālaya` |
| `decline <noun>` | 24-form declension table (a-stem masculine) | `decline rāma` |
| `number <n>` | Devanagari numeral + Sanskrit word | `number 18` |
| `calc <expr>` | Safe arithmetic (no `eval`) | `calc 12 * (3 + 4)` |
| `meaning <word>` | English / Sanskrit / Hindi / Tamil dictionary | `meaning water` |
| `subhashita` | A classical Sanskrit saying | `subhashita` |

## Project structure

```
app.py               Flask routes: /, /health, /api/chat
sanskrit_engine.py   language engine (pure Python, unit-tested)
templates/index.html chat interface
tests/               pytest unit + API tests
Dockerfile           container image (python:3.12-slim, non-root, healthcheck)
Jenkinsfile          CI: Checkout -> Build -> Test/Validate -> Docker Build -> Smoke Test -> Result
```

## Run locally (Windows)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest
python app.py            # open http://localhost:5000
```

## Run with Docker

```
docker build -t vaksetu-bot:1.0 .
docker run -d --name vaksetu -p 5000:5000 vaksetu-bot:1.0
```
