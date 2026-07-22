import unittest
from io import BytesIO
from unittest.mock import patch

import downloader


class DownloaderTests(unittest.TestCase):
    def test_rejects_non_youtube_url(self):
        with self.assertRaises(ValueError):
            downloader.validate("https://example.com/video", 1080)
        with self.assertRaises(ValueError):
            downloader.validate("ftp://youtube.com/video", 1080)

    def test_builds_selected_resolution_command(self):
        command = downloader.build_command(
            "https://www.youtube.com/watch?v=4bdQ_OIbcC0", 2160
        )
        self.assertIn(
            "bestvideo[height<=2160]+bestaudio/best[height<=2160]", command
        )
        self.assertIn("--merge-output-format", command)
        self.assertIn("mp4", command)
        self.assertIn("--progress", command)

    def test_lists_only_real_and_original_subtitles(self):
        options = downloader.subtitle_options({
            "subtitles": {"en": [{"name": "English"}]},
            "automatic_captions": {
                "en-orig": [{"name": "English (Original)"}],
                "zh-Hans-en": [{"name": "Chinese from English"}],
            },
        })
        self.assertEqual(options, [
            {"label": "英文（作者字幕）", "language": "en", "automatic": False},
            {"label": "英文（自动字幕）", "language": "en-orig", "automatic": True},
        ])

    def test_builds_exact_subtitle_command(self):
        command = downloader.build_subtitle_command(
            "https://www.youtube.com/watch?v=4bdQ_OIbcC0", "en-orig", True
        )
        self.assertIn("--write-auto-subs", command)
        self.assertNotIn("--write-subs", command)
        self.assertEqual(command[command.index("--sub-langs") + 1], "en-orig")

    def test_uses_absolute_node_runtime(self):
        runtime = downloader.js_runtime_arg()
        self.assertRegex(runtime, r"^node:/")

    def test_parses_progress_and_result(self):
        self.assertEqual(
            downloader.parse_line(
                'download:{"percent":"42.5%","speed":1048576,"eta":90,"elapsed":30,"downloaded":31457280}'
            ),
            ("progress", {"percent": 42.5, "speed": 1048576, "eta": 90, "elapsed": 30, "downloaded": 31457280}),
        )
        self.assertEqual(
            downloader.parse_line("result:/tmp/video.mp4"),
            ("finished", "/tmp/video.mp4"),
        )

    def test_parses_video_metadata_and_estimates_time(self):
        metadata = downloader.parse_metadata(
            {"title": "Demo", "formats": [
                {"height": 1080, "filesize": 20_000_000},
                {"vcodec": "none", "filesize_approx": 2_000_000},
                {"height": 2160, "filesize": 80_000_000},
            ]},
            1080,
        )
        self.assertEqual(
            metadata,
            {"title": "Demo", "size": 22_000_000, "speed_test_url": None, "subtitles": []},
        )
        self.assertEqual(downloader.estimate_seconds(22_000_000, 2_000_000), 11)
        self.assertIsNone(downloader.estimate_seconds(22_000_000, None))

    def test_formats_duration_and_size(self):
        self.assertEqual(downloader.format_duration(90), "1分30秒")
        self.assertEqual(downloader.format_size(1048576), "1.0 MB")

    @patch("downloader.subprocess.Popen")
    def test_download_reports_real_ytdlp_error(self, popen):
        process = popen.return_value
        process.stdout = iter(["ERROR: Sign in to confirm you are not a bot\n"])
        process.wait.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "Sign in to confirm"):
            downloader.download(
                "https://www.youtube.com/watch?v=4bdQ_OIbcC0", 1080, lambda *_: None
            )

    @patch("downloader.subprocess.Popen")
    def test_cancel_all_terminates_active_download(self, popen):
        process = popen.return_value
        process.poll.return_value = None
        downloader.ACTIVE_PROCESSES.add(process)
        downloader.cancel_all()
        process.terminate.assert_called_once()
        self.assertFalse(downloader.ACTIVE_PROCESSES)

    @patch("downloader.run_tracked")
    def test_metadata_has_timeout(self, run):
        run.side_effect = downloader.subprocess.TimeoutExpired("yt-dlp", 20)
        with self.assertRaisesRegex(RuntimeError, "读取超时"):
            downloader.fetch_metadata(
                "https://www.youtube.com/watch?v=4bdQ_OIbcC0", 1080
            )
        self.assertEqual(run.call_args.kwargs["timeout"], 20)

    def test_metadata_includes_selected_video_url(self):
        metadata = downloader.parse_metadata(
            {"title": "Demo", "formats": [
                {"height": 1080, "filesize": 20_000_000, "url": "https://cdn/video"},
                {"vcodec": "none", "filesize": 2_000_000},
            ]},
            1080,
        )
        self.assertEqual(metadata["speed_test_url"], "https://cdn/video")

    @patch("downloader.time.monotonic", side_effect=[10.0, 12.0])
    @patch("downloader.urlopen")
    def test_speed_test_reads_only_four_megabytes(self, urlopen, _monotonic):
        response = BytesIO(b"x" * downloader.SPEED_TEST_BYTES)
        urlopen.return_value.__enter__.return_value = response
        speed = downloader.measure_speed("https://cdn/video")
        self.assertEqual(speed, downloader.SPEED_TEST_BYTES / 2)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.headers["Range"], "bytes=0-4194303")


if __name__ == "__main__":
    unittest.main()
