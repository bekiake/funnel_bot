#!/bin/bash

# Скрипт для запуска Funnel Bot

echo "🚀 Запуск Funnel Bot..."

# Проверяем существование .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    echo "📋 Скопируйте .env.example в .env и настройте:"
    echo "   cp .env.example .env"
    echo "   nano .env"
    exit 1
fi

# Проверяем существование виртуального окружения
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Устанавливаем зависимости
echo "📚 Установка зависимостей..."
pip install -r requirements.txt

# Создаем папку для логов
mkdir -p logs

# Создаем тестовые данные (если нужно)
if [ "$1" = "--create-test-data" ]; then
    echo "🗄️ Создание тестовых данных..."
    python scripts/create_test_data.py
fi

# Запускаем бота
echo "▶️ Запуск бота..."
python app.py
