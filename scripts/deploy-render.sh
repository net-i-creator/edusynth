#!/usr/bin/env bash
# Deploy УмБаза (frontend + backend) to Render as a single Docker service.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! render whoami >/dev/null 2>&1; then
  echo "Run: render login"
  exit 1
fi

render workspace set tea-d3f88b1r0fns73dcks60 >/dev/null 2>&1 || true

REPO="${GITHUB_REPO:-net-i-creator/edusynth}"
REPO_URL="https://github.com/${REPO}"

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub auth required. Run: gh auth login -h github.com -p https -w"
  exit 1
fi

if ! gh repo view "$REPO" >/dev/null 2>&1; then
  echo "==> Creating GitHub repo $REPO ..."
  gh repo create "$REPO" --public --source=. --remote=origin --push
else
  git remote remove origin 2>/dev/null || true
  git remote add origin "$REPO_URL.git"
  echo "==> Pushing to $REPO_URL ..."
  git push -u origin main
fi

echo "==> Ensuring PostgreSQL and Redis exist..."
render postgres list --output json | python3 -c "
import json,sys
items=json.load(sys.stdin).get('data',[])
assert any(i.get('name')=='edusynth-db' for i in items), 'Run render postgres create first'
" >/dev/null

render keyvalues list --output json | python3 -c "
import json,sys
items=json.load(sys.stdin).get('data',[])
assert any(i.get('name')=='edusynth-redis' for i in items), 'Run render kv create first'
" >/dev/null

DB_URL=$(render postgres get edusynth-db --include-sensitive-connection-info --output json \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['connectionInfo']['internalConnectionString'])")
REDIS_URL=$(render keyvalues get edusynth-redis --include-sensitive-connection-info --output json \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['connectionInfo']['externalConnectionString'])" \
  | sed 's/^rediss:/redis:/')

GROQ_KEY=""
if [ -f "$ROOT/.env" ]; then
  GROQ_KEY=$(grep '^GROQ_API_KEY=' "$ROOT/.env" | cut -d= -f2-)
fi

if render services list --output json | python3 -c "
import json,sys
items=json.load(sys.stdin)
for i in items:
    if i.get('service',{}).get('name')=='edusynth':
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
  echo "==> Service edusynth already exists, triggering redeploy..."
  SRV_ID=$(render services list --output json | python3 -c "
import json,sys
for i in json.load(sys.stdin):
    if i.get('service',{}).get('name')=='edusynth':
        print(i['service']['id']); break
")
  render deploys create "$SRV_ID" --confirm --output json
else
  echo "==> Creating web service from $REPO_URL ..."
  render services create \
    --name edusynth \
    --type web_service \
    --repo "$REPO_URL" \
    --branch main \
    --runtime docker \
    --plan free \
    --region oregon \
    --health-check-path /health \
    --env-var "DATABASE_URL=$DB_URL" \
    --env-var "REDIS_URL=$REDIS_URL" \
    --env-var "AI_PROVIDER=groq" \
    --env-var "GROQ_MODEL=llama-3.3-70b-versatile" \
    --env-var "IMAGE_PROVIDER=web_search" \
    --env-var "IMAGE_REHOST_S3=false" \
    --env-var "IMAGE_VISION_VERIFY=false" \
    --env-var 'CORS_ORIGINS=["*"]' \
    --env-var "GROQ_API_KEY=$GROQ_KEY" \
    --confirm \
    --output json
fi

echo ""
echo "Done! Site URL:"
render services list --output json | python3 -c "
import json,sys
for i in json.load(sys.stdin):
    s=i.get('service',{})
    if s.get('name')=='edusynth':
        print(s['serviceDetails']['url'])
"
