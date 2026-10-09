#!/usr/bin/env bash
# deploy.sh — run this on the VPS as root after uploading files
# Usage: bash /tmp/thesis_upload/deploy.sh

set -e

SITE_ROOT="/var/www/thesis"
NGINX_CONF="/etc/nginx/sites-available/thesis"
NGINX_LINK="/etc/nginx/sites-enabled/thesis"
UPLOAD_DIR="/tmp/thesis_upload"

echo "==> Creating site directory..."
mkdir -p "$SITE_ROOT/figures"

echo "==> Copying index.html..."
cp "$UPLOAD_DIR/index.html" "$SITE_ROOT/index.html"

echo "==> Copying figures..."
if [ -d "$UPLOAD_DIR/figures" ]; then
    cp -r "$UPLOAD_DIR/figures/." "$SITE_ROOT/figures/"
    echo "    Copied figures."
else
    echo "    WARNING: No figures directory found in upload. Upload figures separately."
fi

echo "==> Setting permissions..."
chown -R www-data:www-data "$SITE_ROOT"
chmod -R 755 "$SITE_ROOT"

echo "==> Installing nginx config..."
cp "$UPLOAD_DIR/nginx_thesis.conf" "$NGINX_CONF"

if [ ! -L "$NGINX_LINK" ]; then
    ln -s "$NGINX_CONF" "$NGINX_LINK"
    echo "    Symlink created."
else
    echo "    Symlink already exists."
fi

echo "==> Testing nginx configuration..."
nginx -t

echo "==> Reloading nginx..."
systemctl reload nginx

echo ""
echo "==> Done! Site is available at: http://72.56.38.144:8080"
echo "    Figures directory: $SITE_ROOT/figures/"
echo "    To add figures later:  scp figures/*.png root@72.56.38.144:$SITE_ROOT/figures/"
