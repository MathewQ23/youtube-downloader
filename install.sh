#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/youtube-downloader"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APP_ID="com.mathew.YouTubeDownloader"

mkdir -p "$APP_DIR" "$DESKTOP_DIR" "$ICON_DIR"
install -m 644 "$SOURCE_DIR/app.py" "$APP_DIR/app.py"
install -m 644 "$SOURCE_DIR/downloader.py" "$APP_DIR/downloader.py"
install -m 644 "$SOURCE_DIR/youtube-downloader.svg" "$ICON_DIR/$APP_ID.svg"

cat > "$DESKTOP_DIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=YouTube 下载器
Comment=粘贴视频地址并选择分辨率下载
Exec=python3 $APP_DIR/app.py
Path=$APP_DIR
Icon=$APP_ID
Terminal=false
StartupNotify=true
Categories=AudioVideo;
Keywords=YouTube;视频;下载;
EOF
chmod +x "$DESKTOP_DIR/$APP_ID.desktop"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

printf '安装完成。请在应用菜单中搜索“YouTube 下载器”。\n'
