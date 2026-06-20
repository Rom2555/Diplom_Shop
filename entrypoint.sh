#!/bin/sh
echo "Выполняются миграции....."
python manage.py migrate

echo "Запускается Gunicorn....."
exec gunicorn diplom_shop.wsgi:application --bind 0.0.0.0:8000 --workers 3