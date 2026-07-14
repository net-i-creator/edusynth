#!/usr/bin/env bash
# One-command deploy script for УмБаза backend
# Prerequisites: railway CLI logged in (`railway login`)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

echo "==> Creating Railway project..."
npx @railway/cli init --name edusynth-api 2>/dev/null || true

echo "==> Adding PostgreSQL..."
npx @railway/cli add --database postgres --yes 2>/dev/null || true

echo "==> Adding Redis..."
npx @railway/cli add --database redis --yes 2>/dev/null || true

echo "==> Setting environment variables..."
if [ -f "$ROOT/.env" ]; then
  GROQ_KEY=$(grep '^GROQ_API_KEY=' "$ROOT/.env" | cut -d= -f2-)
  npx @railway/cli variables set \
    AUTH_ENABLED=false \
    AI_PROVIDER=groq \
    GROQ_MODEL=llama-3.3-70b-versatile \
    IMAGE_PROVIDER=web_search \
    IMAGE_REHOST_S3=false \
    IMAGE_VISION_VERIFY=false \
    "GROQ_API_KEY=$GROQ_KEY" \
    'CORS_ORIGINS=["https://edusynth-umbaza.netlify.app"]'
fi

echo "==> Deploying..."
npx @railway/cli up --detach

echo "==> Getting public URL..."
npx @railway/cli domain 2>/dev/null || npx @railway/cli status

echo ""
echo "Done! Copy the Railway URL and run:"
echo "  netlify env:set BACKEND_URL https://YOUR-RAILWAY-URL.up.railway.app"
echo "  netlify deploy --prod --dir=frontend"
