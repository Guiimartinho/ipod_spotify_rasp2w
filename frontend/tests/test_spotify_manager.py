import os
import sys
import threading
import unittest
from unittest.mock import MagicMock

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

import datastore
import spotify_manager
import spotify_manager as sm
from fake_redis import FakeRedis


def track(i):
    return sm.UserTrack("Track %d" % i, "Artist", "Album", "spotify:track:%d" % i)


def album_dict(uri="spotify:album:a1", name="Al"):
    return {
        "name": name,
        "uri": uri,
        "artists": [{"name": "Ar"}],
        "tracks": {"items": [{"name": "X", "uri": "spotify:track:x"}], "next": None},
    }


def show_dict(uri="spotify:show:s1", name="Show"):
    return {
        "name": name,
        "uri": uri,
        "publisher": "Pub",
        "episodes": {"items": [{"name": "E", "uri": "spotify:episode:e"}], "next": None},
    }


class SpotifyManagerTestBase(unittest.TestCase):
    def setUp(self):
        self._orig_sp = spotify_manager._sp
        self._orig_ds = spotify_manager.DATASTORE
        self._orig_internet = spotify_manager.has_internet
        self.m = MagicMock()
        self.m.current_playback.return_value = None  # keep refresh_now_playing cheap
        spotify_manager._sp = self.m
        spotify_manager.DATASTORE = datastore.Datastore(client=FakeRedis())

    def tearDown(self):
        spotify_manager._sp = self._orig_sp
        spotify_manager.DATASTORE = self._orig_ds
        spotify_manager.has_internet = self._orig_internet


class TestBugFixes(SpotifyManagerTestBase):
    def test_get_album_tracks_uses_album_endpoint(self):
        # Regression: the original called sp.playlist_tracks on an album id.
        self.m.album.return_value = {
            "name": "Discovery",
            "artists": [{"name": "Daft Punk"}],
            "tracks": {
                "items": [{"name": "One More Time", "uri": "spotify:track:omt"}],
                "next": None,
            },
        }
        tracks = spotify_manager.get_album_tracks("spotify:album:a1")
        self.assertTrue(self.m.album.called)
        self.assertFalse(self.m.playlist_tracks.called)
        self.assertEqual(tracks[0].title, "One More Time")
        self.assertEqual(tracks[0].album, "Discovery")

    def test_track_index_no_stopiteration(self):
        tracks = [track(0), track(1)]
        self.assertEqual(spotify_manager._track_index(tracks, "spotify:track:1"), 2)
        self.assertEqual(spotify_manager._track_index(tracks, "missing"), -1)
        self.assertEqual(spotify_manager._track_index([], "missing"), -1)

    def test_now_playing_track_not_in_cache_does_not_crash(self):
        ds = spotify_manager.DATASTORE
        ds.setPlaylist(sm.UserPlaylist("PL", 0, "spotify:playlist:ctx", 1), [track(99)])
        response = {
            "currently_playing_type": "track",
            "item": {
                "name": "Now",
                "artists": [{"name": "A"}],
                "album": {"name": "Al"},
                "duration_ms": 1000,
                "uri": "spotify:track:NOTFOUND",
            },
            "is_playing": True,
            "progress_ms": 10,
            "context": {"type": "playlist", "uri": "spotify:playlist:ctx"},
        }
        np = spotify_manager.get_now_playing_track(response=response)
        self.assertEqual(np["track_index"], -1)
        self.assertEqual(np["context_name"], "PL")


class TestSearch(SpotifyManagerTestBase):
    def test_search_parses_results(self):
        self.m.search.side_effect = [
            {
                "tracks": {
                    "items": [
                        {
                            "name": "T",
                            "artists": [{"name": "A"}],
                            "album": {"name": "Al"},
                            "uri": "spotify:track:t",
                        }
                    ]
                }
            },
            {"artists": {"items": [{"name": "Ar", "uri": "spotify:artist:a"}]}},
            {"albums": {"items": [album_dict()]}},
        ]
        results = spotify_manager.search("daft")
        self.assertEqual(len(results.tracks), 1)
        self.assertEqual(len(results.artists), 1)
        self.assertEqual(len(results.albums), 1)
        self.assertIn("spotify:album:a1", results.album_track_map)

    def test_search_error_returns_empty(self):
        self.m.search.side_effect = RuntimeError("429 rate limited")
        results = spotify_manager.search("x")
        self.assertEqual(results.tracks, [])
        self.assertEqual(results.albums, [])


class TestPlayback(SpotifyManagerTestBase):
    def test_play_track_without_device_is_noop(self):
        spotify_manager.play_track("spotify:track:x")  # no devices stored
        self.assertFalse(self.m.start_playback.called)

    def test_play_track_with_device_starts_playback(self):
        spotify_manager.DATASTORE.setUserDevice(sm.UserDevice("d1", "Spotifypod", True))
        spotify_manager.play_track("spotify:track:x")
        self.assertTrue(self.m.start_playback.called)
        _, kwargs = self.m.start_playback.call_args
        self.assertEqual(kwargs["device_id"], "d1")

    def test_playback_error_is_swallowed(self):
        spotify_manager.DATASTORE.setUserDevice(sm.UserDevice("d1", "Spotifypod", True))
        self.m.start_playback.side_effect = RuntimeError("no active device")
        # Must not raise (would otherwise kill the worker thread).
        self.assertIsNone(spotify_manager.play_track("spotify:track:x"))


class TestRefreshData(SpotifyManagerTestBase):
    def _configure_single_page(self):
        self.m.current_user_saved_tracks.return_value = {
            "items": [
                {
                    "track": {
                        "name": "T",
                        "artists": [{"name": "A"}],
                        "album": {"name": "Al"},
                        "uri": "spotify:track:t1",
                    }
                }
            ],
            "offset": 0,
            "next": None,
        }
        self.m.current_user_followed_artists.return_value = {
            "artists": {"items": [{"name": "Ar", "uri": "spotify:artist:a1"}], "next": None}
        }
        self.m.current_user_playlists.return_value = {
            "items": [{"id": "p1", "name": "PL", "uri": "spotify:playlist:p1"}],
            "offset": 0,
            "next": None,
        }
        self.m.playlist_tracks.return_value = {
            "items": [
                {
                    "track": {
                        "name": "PT",
                        "artists": [{"name": "A"}],
                        "album": {"name": "Al"},
                        "uri": "spotify:track:pt1",
                    }
                }
            ],
            "next": None,
        }
        self.m.current_user_saved_albums.return_value = {
            "items": [{"album": album_dict()}],
            "offset": 0,
            "next": None,
        }
        self.m.new_releases.return_value = {
            "albums": {"items": [album_dict("spotify:album:nr1", "NR")], "next": None}
        }
        self.m.current_user_saved_shows.return_value = {
            "items": [{"show": show_dict()}],
            "next": None,
        }
        self.m.devices.return_value = {
            "devices": [{"id": "d1", "name": "Spotifypod Den", "is_active": True}]
        }

    def test_refresh_data_populates_all_sections(self):
        self._configure_single_page()
        spotify_manager.refresh_data()
        ds = spotify_manager.DATASTORE
        self.assertEqual(ds.getSavedTrackCount(), 1)
        self.assertEqual(ds.getArtistCount(), 1)
        self.assertEqual(ds.getPlaylistCount(), 1)
        self.assertEqual(ds.getAlbumCount(), 1)
        self.assertEqual(ds.getNewReleasesCount(), 1)
        self.assertEqual(ds.getShowsCount(), 1)
        self.assertEqual(len(ds.getAllSavedDevices()), 1)

    def test_one_failing_section_does_not_abort_the_rest(self):
        self._configure_single_page()
        self.m.current_user_followed_artists.side_effect = RuntimeError("boom")
        spotify_manager.refresh_data()
        ds = spotify_manager.DATASTORE
        self.assertEqual(ds.getArtistCount(), 0)  # the failing section
        self.assertEqual(ds.getSavedTrackCount(), 1)  # later sections still ran
        self.assertEqual(ds.getPlaylistCount(), 1)


class TestProxy(SpotifyManagerTestBase):
    def test_proxy_forwards_and_is_concurrency_safe(self):
        self.m.devices.return_value = {"devices": []}

        def worker():
            for _ in range(50):
                spotify_manager.sp.devices()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self.m.devices.call_count, 200)

    def test_get_sp_returns_injected_client(self):
        self.assertIs(spotify_manager.get_sp(), self.m)


if __name__ == "__main__":
    unittest.main()
