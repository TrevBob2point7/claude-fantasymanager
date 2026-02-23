#!/bin/bash
set -e

echo "Installing backend dependencies..."
cd /workspace/backend
pip install uv==0.10.4
uv sync

echo "Installing frontend dependencies..."
cd /workspace/frontend
npm install

echo "Installing Playwright browsers..."
npx playwright install --with-deps chromium

echo "Dev environment ready!"
