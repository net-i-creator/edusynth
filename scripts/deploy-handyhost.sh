#!/usr/bin/env bash
# Deploy frontend + API proxy to HandyHost (УмБаза.рф)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="www/xn--80aabzw5b.xn--p1ai"
FTP_HOST="${FTP_HOST:-109.95.210.216}"
FTP_USER="${FTP_USER:-u207755}"
FTP_PASS="${FTP_PASS:?Set FTP_PASS environment variable}"

STAGING="$ROOT/.deploy-staging"
rm -rf "$STAGING"
mkdir -p "$STAGING"

echo "==> Preparing files..."
cp -R "$ROOT/frontend/." "$STAGING/"
cp "$ROOT/deploy/handyhost/.htaccess" "$STAGING/"
mkdir -p "$STAGING/api"
cp "$ROOT/deploy/handyhost/api/index.php" "$STAGING/api/"

echo "==> Uploading to HandyHost ($REMOTE_DIR)..."
lftp -u "$FTP_USER","$FTP_PASS" "$FTP_HOST" <<EOF
set ftp:ssl-allow no
set mirror:parallel-transfer-count 4
mirror -R --delete --verbose "$STAGING" "$REMOTE_DIR"
cd $REMOTE_DIR
chmod 644 index.html lesson.html account.html auth.html faq.html news.html oferta.html confidentiality.html .htaccess
chmod 755 css js assets api
chmod 644 css/styles.css api/index.php assets/minobr-emblem.png
chmod 755 assets/brand assets/logos
chmod 644 assets/brand/umbaza-mark-v2.png
chmod 644 assets/logos/vk-square.png assets/logos/max-square.png assets/logos/yookassa.png assets/logos/sbp.png assets/logos/tochka.png 2>/dev/null || true
chmod 644 js/animations.js js/api.js js/auth.js js/education-config.js js/guest-limit.js js/site-config.js js/yandex-metrika.js
chmod 755 news
glob -a chmod 644 news/*.html
glob -a rm -r .DS_Store
bye
EOF

rm -rf "$STAGING"
echo "==> Done! Site: https://xn--80aabzw5b.xn--p1ai (УмБаза.рф)"
