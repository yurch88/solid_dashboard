#!/bin/bash

# Остановить и удалить все контейнеры, связанные с проектом
docker-compose down --volumes --remove-orphans

# Удалить старые данные проекта
rm -rf wireguard-config/

# Удалить старые образы проекта
docker rmi $(docker images -q solid-vpn-dashboard) --force 2>/dev/null || true

# Удалить все контейнеры
echo "Удаление всех контейнеров..."
docker container rm -f $(docker container ls -aq) 2>/dev/null || true

# Удалить все образы
echo "Удаление всех образов..."
docker image rm -f $(docker image ls -q) 2>/dev/null || true

# Очистить неиспользуемые данные Docker (опционально, для полного удаления артефактов)
echo "Очистка неиспользуемых данных Docker..."
docker system prune -af --volumes

# Уничтожить директорию хранения конфигов
rm -r /etc/wireguard

# Успешное завершение
echo "Система Docker очищена."
