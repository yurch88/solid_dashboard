FROM lscr.io/linuxserver/wireguard:latest

RUN apk update && apk add --no-cache python3 py3-pip wireguard-tools bash

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
EXPOSE 51820/udp

ENTRYPOINT ["/entrypoint.sh"]
