#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-1.0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$ROOT/build/deb"
DIST="$ROOT/dist"
APP_DIR="$BUILD/usr/lib/youtube-downloader"
BIN_DIR="$BUILD/usr/bin"
DESKTOP_DIR="$BUILD/usr/share/applications"
ICON_DIR="$BUILD/usr/share/icons/hicolor/scalable/apps"
PACKAGE="$DIST/youtube-downloader_${VERSION}_all.deb"

rm -rf "$BUILD"
mkdir -p "$BUILD/DEBIAN" "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$DIST"

install -m 644 "$ROOT/app.py" "$APP_DIR/app.py"
install -m 644 "$ROOT/downloader.py" "$APP_DIR/downloader.py"
install -m 644 "$ROOT/youtube-downloader.svg" "$ICON_DIR/com.mathew.YouTubeDownloader.svg"

curl -fL --retry 3 \
  https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
  -o "$APP_DIR/yt-dlp"
chmod 755 "$APP_DIR/yt-dlp"

cat > "$BUILD/DEBIAN/control" <<EOF
Package: youtube-downloader
Version: $VERSION
Section: video
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-4.0, ffmpeg, nodejs
Maintainer: MathewQ <861054376@qq.com>
Description: GTK4 YouTube video downloader
 Download YouTube videos and available subtitles with a simple GTK4 interface.
EOF

cat > "$BIN_DIR/youtube-downloader" <<'EOF'
#!/usr/bin/env bash
exec python3 /usr/lib/youtube-downloader/app.py "$@"
EOF
chmod 755 "$BIN_DIR/youtube-downloader"

cat > "$DESKTOP_DIR/com.mathew.YouTubeDownloader.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=YouTube 下载器
Comment=粘贴视频地址并选择分辨率下载
Exec=youtube-downloader
Icon=com.mathew.YouTubeDownloader
Terminal=false
StartupNotify=true
Categories=AudioVideo;
Keywords=YouTube;视频;下载;
EOF
chmod 644 "$DESKTOP_DIR/com.mathew.YouTubeDownloader.desktop"
find "$BUILD" -type d -exec chmod 755 {} +

dpkg-deb --root-owner-group --build "$BUILD" "$PACKAGE"
printf '%s\n' "$PACKAGE"
