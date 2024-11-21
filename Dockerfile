# Используем базовый образ с поддержкой WireGuard
FROM lscr.io/linuxserver/wireguard:latest

# Устанавливаем необходимые инструменты
RUN apk update && apk add --no-cache \
    python3 \
    py3-pip \
    wireguard-tools \ # WireGuard утилиты для управления интерфейсом wg0
    bash \
    dpkg \
    dumb-init \ # Утилита для корректного управления процессами внутри контейнера
    iptables \
    iptables-legacy  # Legacy iptables для совместимости с WireGuard

# Настройка iptables-legacy
RUN update-alternatives --install /sbin/iptables iptables /sbin/iptables-legacy 10 \
    --slave /sbin/iptables-restore iptables-restore /sbin/iptables-legacy-restore \
    --slave /sbin/iptables-save iptables-save /sbin/iptables-legacy-save

# Копируем файлы приложения
COPY app.py /app/app.py
COPY requirements.txt /app/requirements.txt
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY entrypoint.sh /entrypoint.sh

# Делаем скрипт entrypoint.sh исполняемым
RUN chmod +x /entrypoint.sh

# Устанавливаем зависимости Python
RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

# Настраиваем рабочую директорию
WORKDIR /app

# Открываем порты
EXPOSE 80
EXPOSE 51820/udp

# Добавляем HEALTHCHECK для проверки интерфейса wg0
HEALTHCHECK CMD /usr/bin/timeout 5s /bin/sh -c "/usr/bin/wg show | /bin/grep -q interface || exit 1" \
    --interval=1m \
    --timeout=5s \
    --retries=3 #<----added (Проверка наличия интерфейса wg0 для здоровья контейнера)

# Используем dumb-init для управления процессами
ENTRYPOINT ["/usr/bin/dumb-init", "/entrypoint.sh"]
