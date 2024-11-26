FROM python:3.11-slim

# Установка зависимостей для Docker CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    dumb-init \
    curl \
    gnupg \
    lsb-release \
    bash && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y --no-install-recommends docker-ce-cli && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY app.py /app/app.py
COPY requirements.txt /app/requirements.txt
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

WORKDIR /app

EXPOSE 80

HEALTHCHECK CMD curl --fail http://localhost:80/ || exit 1

ENTRYPOINT ["/usr/bin/dumb-init", "/entrypoint.sh"]
