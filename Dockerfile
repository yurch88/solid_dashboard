FROM lscr.io/linuxserver/wireguard:latest

RUN apk update && apk add --no-cache \
    python3 \
    py3-pip \
    wireguard-tools \
    bash \
    dpkg \
    dumb-init \
    iptables \
    iptables-legacy
    
RUN update-alternatives --install /sbin/iptables iptables /sbin/iptables-legacy 10 \
    --slave /sbin/iptables-restore iptables-restore /sbin/iptables-legacy-restore \
    --slave /sbin/iptables-save iptables-save /sbin/iptables-legacy-save
    
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

HEALTHCHECK CMD /usr/bin/timeout 5s /bin/sh -c "/usr/bin/wg show | /bin/grep -q interface || exit 1" \
    --interval=1m \
    --timeout=5s \
    --retries=3

ENTRYPOINT ["/usr/bin/dumb-init", "/entrypoint.sh"]
