# ---------------------------------------------------------------
# VakSetu - Multilingual Computational Sanskrit Chatbot
# ---------------------------------------------------------------
FROM python:3.12-slim

LABEL maintainer="Sai Thiagarajan (23MIS1150)" \
      description="VakSetu: multilingual computational Sanskrit chatbot (Flask)"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

# 1. Install dependencies first so this layer is cached between builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy the application source
COPY app.py sanskrit_engine.py ./
COPY templates ./templates

# 3. Run as a non-root user
RUN useradd --create-home botuser
USER botuser

EXPOSE 5000

# 4. Docker marks the container healthy only if /health answers
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["python", "app.py"]
