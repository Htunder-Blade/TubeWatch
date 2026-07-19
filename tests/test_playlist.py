from __future__ import annotations

import unittest
from unittest.mock import call, patch

from tubewatch.exceptions import SourceFetchError
from tubewatch.youtube.playlist import fetch_playlist_videos


PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL_TEST"


def entry(video_id: str, title: str | None) -> dict[str, object]:
    return {"id": video_id, "title": title}


class FetchPlaylistVideosTests(unittest.TestCase):
    @patch("tubewatch.youtube.playlist._extract_playlist_batch")
    def test_continues_after_malformed_and_duplicate_entries(self, extract_batch):
        extract_batch.side_effect = [
            {
                "entries": [
                    entry("private", None),
                    entry("video-1", "One"),
                    entry("video-2", "Two"),
                    entry("video-1", "One duplicate"),
                ],
                "playlist_count": 21,
            },
            {
                "entries": [entry("video-3", "Three")],
                "playlist_count": 21,
            },
        ]

        videos = fetch_playlist_videos(PLAYLIST_URL, limit=3)

        self.assertEqual([video.video_id for video in videos], ["video-1", "video-2", "video-3"])
        self.assertEqual(
            extract_batch.call_args_list,
            [
                call(PLAYLIST_URL, 1, 20),
                call(PLAYLIST_URL, 21, 40),
            ],
        )

    @patch("tubewatch.youtube.playlist._extract_playlist_batch")
    def test_returns_available_videos_when_playlist_ends_early(self, extract_batch):
        extract_batch.return_value = {
            "entries": [entry("private", None), entry("video-1", "One")],
            "playlist_count": 2,
        }

        videos = fetch_playlist_videos(PLAYLIST_URL, limit=3)

        self.assertEqual([video.video_id for video in videos], ["video-1"])
        extract_batch.assert_called_once_with(PLAYLIST_URL, 1, 20)

    @patch("tubewatch.youtube.playlist._extract_playlist_batch")
    def test_rejects_batch_without_entries_list(self, extract_batch):
        extract_batch.return_value = {"entries": None}

        with self.assertRaisesRegex(SourceFetchError, "播放列表视频列表"):
            fetch_playlist_videos(PLAYLIST_URL, limit=3)


if __name__ == "__main__":
    unittest.main()
