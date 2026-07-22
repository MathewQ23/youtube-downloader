import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DOWNLOAD_DIR = Path.home() / "Downloads"
RESOLUTIONS = {360, 720, 1080, 1440, 2160}
NODE_PATH = Path.home() / ".nvm/versions/node/v22.22.1/bin/node"
SPEED_TEST_BYTES = 4 * 1024 * 1024
ACTIVE_PROCESSES = set()


def cancel_all():
    for process in list(ACTIVE_PROCESSES):
        if process.poll() is None:
            process.terminate()
    ACTIVE_PROCESSES.clear()


def run_tracked(command, timeout=None):
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    ACTIVE_PROCESSES.add(process)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    finally:
        ACTIVE_PROCESSES.discard(process)


def js_runtime_arg():
    node = NODE_PATH if NODE_PATH.exists() else shutil.which("node")
    return f"node:{node}" if node else "node"


def validate(url, resolution):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in {
        "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"
    }:
        raise ValueError("请输入有效的 YouTube 视频地址")
    if resolution not in RESOLUTIONS:
        raise ValueError("不支持该分辨率")


def video_format(resolution):
    return f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]"


def build_command(url, resolution):
    validate(url, resolution)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        "yt-dlp", "--no-playlist", "--js-runtimes", js_runtime_arg(),
        "--newline", "--progress", "--concurrent-fragments", "8",
        "-f", video_format(resolution), "--merge-output-format", "mp4",
        "--progress-template",
        'download:download:{"percent":"%(progress._percent_str)s","speed":%(progress.speed)j,"eta":%(progress.eta)j,"elapsed":%(progress.elapsed)j,"downloaded":%(progress.downloaded_bytes)j}',
        "--print", "after_move:result:%(filepath)s",
        "-o", str(DOWNLOAD_DIR / "%(title)s [%(id)s] %(height)sp.%(ext)s"),
        url,
    ]
    return command


LANGUAGE_NAMES = {
    "en": "英文", "en-orig": "英文", "zh-Hans": "简体中文",
    "zh-Hant": "繁体中文", "ja": "日文", "ko": "韩文",
}


def subtitle_options(data):
    options = []
    for language in data.get("subtitles", {}):
        name = LANGUAGE_NAMES.get(language, language)
        options.append({
            "label": f"{name}（作者字幕）", "language": language, "automatic": False,
        })
    for language in data.get("automatic_captions", {}):
        if not language.endswith("-orig"):
            continue
        name = LANGUAGE_NAMES.get(language, language.removesuffix("-orig"))
        options.append({
            "label": f"{name}（自动字幕）", "language": language, "automatic": True,
        })
    return options


def build_subtitle_command(url, language, automatic):
    command = [
        "yt-dlp", "--no-playlist", "--js-runtimes", js_runtime_arg(),
        "--skip-download", "--sub-langs", language, "--sub-format", "srt/best",
        "--convert-subs", "srt",
        "-o", str(DOWNLOAD_DIR / "%(title)s [%(id)s].%(ext)s"), url,
    ]
    command.insert(1, "--write-auto-subs" if automatic else "--write-subs")
    return command


def parse_line(line):
    if line.startswith("result:"):
        return "finished", line[7:].strip()
    if not line.startswith("download:"):
        return None
    try:
        data = json.loads(line[9:])
        data["percent"] = float(re.sub(r"[^0-9.]", "", data.get("percent", "0")) or 0)
        return "progress", data
    except (json.JSONDecodeError, ValueError):
        return None


def parse_metadata(data, resolution):
    videos = [
        item for item in data.get("formats", [])
        if item.get("height") and item["height"] <= resolution
        and item.get("vcodec") != "none"
    ]
    audios = [
        item for item in data.get("formats", [])
        if item.get("vcodec") == "none"
    ]
    video = max(videos, key=lambda item: (item.get("height", 0), item.get("tbr", 0)), default={})
    audio = max(audios, key=lambda item: item.get("abr", 0), default={})
    size = sum((item.get("filesize") or item.get("filesize_approx") or 0) for item in (video, audio))
    return {
        "title": data.get("title", "未知标题"),
        "size": size or None,
        "speed_test_url": video.get("url"),
        "subtitles": subtitle_options(data),
    }


def measure_speed(url):
    if not url:
        raise RuntimeError("没有可用的测速地址")
    request = Request(url, headers={"Range": f"bytes=0-{SPEED_TEST_BYTES - 1}"})
    start = time.monotonic()
    total = 0
    with urlopen(request, timeout=10) as response:
        while total < SPEED_TEST_BYTES:
            chunk = response.read(min(65536, SPEED_TEST_BYTES - total))
            if not chunk:
                break
            total += len(chunk)
    elapsed = time.monotonic() - start
    if not total or elapsed <= 0:
        raise RuntimeError("测速失败")
    return total / elapsed


def fetch_metadata(url, resolution):
    validate(url, resolution)
    try:
        result = run_tracked(
            ["yt-dlp", "--no-playlist", "--js-runtimes", js_runtime_arg(), "-J", url],
            timeout=20,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("读取超时，请检查网络后重试") from error
    if result.returncode:
        raise RuntimeError("无法读取视频信息")
    return parse_metadata(json.loads(result.stdout), resolution)


def estimate_seconds(size, speed):
    return round(size / speed) if size and speed else None


def format_duration(seconds):
    if seconds is None:
        return "未知"
    seconds = max(0, round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}小时{minutes}分"
    if minutes:
        return f"{minutes}分{seconds}秒"
    return f"{seconds}秒"


def format_size(size):
    if not size:
        return "未知大小"
    return f"{size / 1048576:.1f} MB" if size < 1073741824 else f"{size / 1073741824:.2f} GB"


def download(url, resolution, emit):
    process = subprocess.Popen(
        build_command(url, resolution), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    ACTIVE_PROCESSES.add(process)
    assert process.stdout is not None
    error_lines = []
    for raw_line in process.stdout:
        line = raw_line.strip()
        event = parse_line(line)
        if event:
            emit(*event)
        elif line.startswith("ERROR:"):
            error_lines.append(line.removeprefix("ERROR:").strip())
    code = process.wait()
    ACTIVE_PROCESSES.discard(process)
    if code != 0:
        message = error_lines[-1] if error_lines else f"yt-dlp 退出码：{code}"
        raise RuntimeError(f"下载失败：{message}")


def download_subtitle(url, option):
    result = run_tracked(
        build_subtitle_command(url, option["language"], option["automatic"]),
    )
    if result.returncode:
        errors = [
            line.removeprefix("ERROR:").strip()
            for line in result.stdout.splitlines() + result.stderr.splitlines()
            if line.startswith("ERROR:")
        ]
        raise RuntimeError(errors[-1] if errors else "字幕下载失败")
