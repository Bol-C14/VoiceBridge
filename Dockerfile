FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspaces/VoiceBridge

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

# Install Node.js (if missing) and the Codex CLI package globally
RUN apt-get update \
 && apt-get install -y curl gnupg ca-certificates \
 && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
 && apt-get install -y nodejs \
 && npm install -g @openai/codex \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
