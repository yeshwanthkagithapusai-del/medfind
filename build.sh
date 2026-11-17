#!/usr/bin/env bash
# MediFind Production Build Script for Linux / PaaS (Render, Railway, VPS)
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Collecting static assets (with WhiteNoise compression)..."
python manage.py collectstatic --no-input

echo "==> Applying database migrations..."
python manage.py migrate --no-input

echo "==> Build completed successfully!"
