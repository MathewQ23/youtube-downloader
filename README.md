# YouTube 桌面下载器

一个适用于 Ubuntu/GNOME 的 GTK4 桌面应用。粘贴视频地址、选择清晰度和可用字幕，即可下载到 `~/Downloads`。

## 功能

- 支持 360p、720p、1080p、1440p 和 4K
- 自动合并视频和音频
- 显示预计大小、测速结果和预计时间
- 显示实时下载进度、速度和剩余时间
- 自动列出视频实际提供的字幕，并保存为独立 `.srt` 文件
- 关闭窗口后退出，不常驻后台

## 环境要求

- Ubuntu 22.04 或更高版本
- Python 3
- GTK4 / PyGObject
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- FFmpeg
- Node.js

安装依赖：

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 ffmpeg nodejs
python3 -m pip install --user -U yt-dlp
```

## 安装包

下载仓库中的 [`packages/youtube-downloader_1.0.0_all.deb`](https://github.com/MathewQ23/youtube-downloader/raw/main/packages/youtube-downloader_1.0.0_all.deb)，然后安装：

```bash
sudo apt install ./youtube-downloader_1.0.0_all.deb
```

安装完成后，在 Ubuntu 的应用菜单中搜索“YouTube 下载器”。安装包已内置最新版 `yt-dlp`，系统仍需安装 GTK4、FFmpeg 和 Node.js；`apt` 会自动处理这些依赖。

## 从源码安装

```bash
git clone git@github.com:MathewQ23/youtube-downloader.git
cd youtube-downloader
chmod +x install.sh
./install.sh
```

安装完成后，在 Ubuntu 的应用菜单中搜索“YouTube 下载器”即可启动。

应用安装到当前用户目录，不需要 `sudo`：

```text
~/.local/share/youtube-downloader/
```

安装后可以删除克隆得到的 `youtube-downloader` 目录。

## 从源码运行

如果不想安装：

```bash
git clone git@github.com:MathewQ23/youtube-downloader.git
cd youtube-downloader
python3 app.py
```

视频和字幕默认保存到：

```text
~/Downloads
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 说明

- 所选清晰度不可用时，会使用不超过该值的最佳画质。
- 字幕列表只显示视频实际提供的作者字幕和原始语言自动字幕。
- YouTube 可能对连续请求进行限流，出现 HTTP 429 时请稍后重试。
- 请仅下载你有权保存和使用的内容，并遵守 YouTube 服务条款及当地法律。
