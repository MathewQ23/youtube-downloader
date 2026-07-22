#!/usr/bin/env python3
import threading

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

import downloader

APP_ID = "com.mathew.YouTubeDownloader"
RESOLUTIONS = [360, 720, 1080, 1440, 2160]


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="YouTube 下载器")
        self.set_default_size(600, 350)
        self.set_resizable(False)
        self.metadata_timer = None
        self.metadata_request = 0
        self.subtitle_options = []
        self.connect("close-request", self.on_close)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        self.set_child(box)

        title = Gtk.Label(label="下载 YouTube 视频", xalign=0)
        title.add_css_class("title-2")
        box.append(title)

        self.url = Gtk.Entry(placeholder_text="粘贴 YouTube 视频地址")
        self.url.set_hexpand(True)
        self.url.connect("changed", self.schedule_metadata)
        box.append(self.url)

        row = Gtk.Box(spacing=10)
        box.append(row)
        self.resolution = Gtk.DropDown.new_from_strings(
            ["360p", "720p", "1080p", "1440p", "4K"]
        )
        self.resolution.set_selected(2)
        self.resolution.set_hexpand(True)
        self.resolution.connect("notify::selected", self.schedule_metadata)
        row.append(self.resolution)

        self.subtitles = Gtk.DropDown.new_from_strings(["不下载字幕"])
        self.subtitles.set_selected(0)
        row.append(self.subtitles)

        self.button = Gtk.Button(label="下载")
        self.button.add_css_class("suggested-action")
        self.button.connect("clicked", self.start_download)
        row.append(self.button)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        info_box.set_margin_top(4)
        box.append(info_box)

        self.video_title = Gtk.Label(label="尚未读取视频", xalign=0)
        self.video_title.set_wrap(True)
        self.video_title.set_wrap_mode(2)
        self.video_title.set_lines(2)
        self.video_title.add_css_class("heading")
        info_box.append(self.video_title)

        self.video_details = Gtk.Label(
            label="粘贴地址后显示预计大小和时间", xalign=0
        )
        self.video_details.add_css_class("dim-label")
        self.video_details.set_wrap(True)
        info_box.append(self.video_details)

        self.progress = Gtk.ProgressBar(show_text=True)
        self.progress.set_fraction(0)
        box.append(self.progress)

        self.status = Gtk.Label(label="视频保存到 Downloads", xalign=0)
        self.status.set_wrap(True)
        box.append(self.status)

    def selected_resolution(self):
        return RESOLUTIONS[self.resolution.get_selected()]

    def schedule_metadata(self, *_args):
        self.metadata_request += 1
        self.subtitle_options = []
        self.subtitles.set_model(Gtk.StringList.new(["不下载字幕"]))
        self.subtitles.set_selected(0)
        if self.metadata_timer:
            GLib.source_remove(self.metadata_timer)
        self.metadata_timer = GLib.timeout_add(600, self.start_metadata)

    def start_metadata(self):
        self.metadata_timer = None
        url = self.url.get_text().strip()
        resolution = self.selected_resolution()
        try:
            downloader.validate(url, resolution)
        except ValueError:
            self.video_title.set_text("尚未读取视频")
            self.video_details.set_text("粘贴地址后显示预计大小和时间")
            return False
        self.metadata_request += 1
        request = self.metadata_request
        self.video_title.set_text("正在读取视频信息…")
        self.video_details.set_text("请稍候")
        threading.Thread(
            target=self.load_metadata, args=(request, url, resolution), daemon=True
        ).start()
        return False

    def load_metadata(self, request, url, resolution):
        try:
            metadata = downloader.fetch_metadata(url, resolution)
            GLib.idle_add(self.show_speed_test, request, metadata)
            speed = downloader.measure_speed(metadata["speed_test_url"])
            GLib.idle_add(self.show_metadata, request, metadata, speed)
        except Exception as error:
            GLib.idle_add(self.show_metadata_error, request, str(error))

    def show_speed_test(self, request, metadata):
        if request == self.metadata_request:
            self.subtitle_options = metadata["subtitles"]
            labels = ["不下载字幕"] + [item["label"] for item in self.subtitle_options]
            self.subtitles.set_model(Gtk.StringList.new(labels))
            self.subtitles.set_selected(0)
            self.video_title.set_text(metadata["title"])
            self.video_details.set_text(
                f"预计大小：{downloader.format_size(metadata['size'])}    正在测试下载速度…"
            )
        return False

    def show_metadata(self, request, metadata, speed):
        if request != self.metadata_request:
            return False
        size = downloader.format_size(metadata["size"])
        seconds = downloader.estimate_seconds(metadata["size"], speed)
        self.video_title.set_text(metadata["title"])
        self.video_details.set_text(
            f"预计大小：{size}    实测速度：{downloader.format_size(speed)}/s"
            f"    预计时间：{downloader.format_duration(seconds)}"
        )
        return False

    def show_metadata_error(self, request, message):
        if request == self.metadata_request:
            self.video_title.set_text("无法读取视频信息")
            self.video_details.set_text(message)
        return False

    def start_download(self, _button):
        url = self.url.get_text().strip()
        resolution = self.selected_resolution()
        subtitle_index = self.subtitles.get_selected()
        subtitle = self.subtitle_options[subtitle_index - 1] if subtitle_index else None
        try:
            downloader.validate(url, resolution)
        except ValueError as error:
            self.status.set_text(str(error))
            return
        self.button.set_sensitive(False)
        self.progress.set_fraction(0)
        self.progress.set_text("0%")
        self.status.set_text("正在准备下载…")
        threading.Thread(
            target=self.run_download, args=(url, resolution, subtitle), daemon=True
        ).start()

    def run_download(self, url, resolution, subtitle):
        try:
            downloader.download(url, resolution, self.emit)
            if subtitle:
                try:
                    downloader.download_subtitle(url, subtitle)
                    GLib.idle_add(self.subtitle_finished, subtitle["label"])
                except Exception as error:
                    GLib.idle_add(self.subtitle_failed, str(error))
            else:
                GLib.idle_add(self.video_finished)
        except Exception as error:
            GLib.idle_add(self.finish_error, str(error))

    def emit(self, kind, value):
        GLib.idle_add(self.update_ui, kind, value)

    def update_ui(self, kind, value):
        if kind == "progress":
            percent = value["percent"]
            self.progress.set_fraction(max(0, min(percent / 100, 1)))
            self.progress.set_text(f"{round(percent)}%")
            speed = downloader.format_size(value.get("speed")) + "/s" if value.get("speed") else "测速中"
            eta = downloader.format_duration(value.get("eta"))
            self.status.set_text(f"速度 {speed} · 剩余约 {eta}")
        elif kind == "finished":
            self.progress.set_fraction(1)
            self.progress.set_text("完成")
            self.status.set_text(f"已保存：{value}")
        return False

    def finish_error(self, message):
        self.status.set_text(message)
        self.button.set_sensitive(True)
        return False

    def subtitle_finished(self, label):
        self.status.set_text(f"视频已保存 · 字幕已保存：{label}")
        self.button.set_sensitive(True)
        return False

    def subtitle_failed(self, message):
        self.status.set_text(f"视频已保存 · 字幕失败：{message}")
        self.button.set_sensitive(True)
        return False

    def video_finished(self):
        self.button.set_sensitive(True)
        return False

    def on_close(self, _window):
        downloader.cancel_all()
        return False


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        window = self.props.active_window
        if not window:
            window = Window(self)
        window.present()


if __name__ == "__main__":
    raise SystemExit(App().run())
