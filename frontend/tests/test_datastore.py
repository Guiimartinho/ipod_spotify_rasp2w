import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

import datastore
import spotify_manager as sm
from fake_redis import FakeRedis, RaisingRedis


def track(i):
    return sm.UserTrack("Track %d" % i, "Artist", "Album", "spotify:track:%d" % i)


class TestDatastore(unittest.TestCase):
    def setUp(self):
        self.ds = datastore.Datastore(client=FakeRedis())

    def test_saved_track_roundtrip_and_count(self):
        self.ds.setSavedTrack(0, track(0))
        self.ds.setSavedTrack(1, track(1))
        self.assertEqual(self.ds.getSavedTrackCount(), 2)
        out = self.ds.getSavedTrack(1)
        self.assertEqual(out.title, "Track 1")
        self.assertEqual(out.uri, "spotify:track:1")

    def test_artist_roundtrip_and_missing_is_none(self):
        self.ds.setArtist(0, sm.UserArtist("Daft Punk", "spotify:artist:1"))
        self.assertEqual(self.ds.getArtist(0).name, "Daft Punk")
        self.assertEqual(self.ds.getArtistCount(), 1)
        # missing key must return None, not raise (regression for pickle.loads(None))
        self.assertIsNone(self.ds.getArtist(99))

    def test_playlist_roundtrip(self):
        pl = sm.UserPlaylist("My PL", 0, "spotify:playlist:p1", 2)
        tracks = [track(0), track(1)]
        self.ds.setPlaylist(pl, tracks, index=0)
        self.assertEqual(self.ds.getPlaylistCount(), 1)
        self.assertEqual(self.ds.getPlaylist(0).name, "My PL")
        self.assertEqual(self.ds.getPlaylistUri("spotify:playlist:p1").name, "My PL")
        got = self.ds.getPlaylistTracks("spotify:playlist:p1")
        self.assertEqual([t.uri for t in got], ["spotify:track:0", "spotify:track:1"])
        self.assertEqual(len(self.ds.getAllSavedPlaylists()), 1)

    def test_album_roundtrip(self):
        al = sm.UserAlbum("Discovery", "Daft Punk", 14, "spotify:album:a1")
        self.ds.setAlbum(al, [track(0)], index=0)
        self.assertEqual(self.ds.getAlbumCount(), 1)
        self.assertEqual(self.ds.getAlbum(0).name, "Discovery")
        self.assertEqual(self.ds.getAlbumUri("spotify:album:a1").artist, "Daft Punk")
        self.assertEqual(len(self.ds.getAllSavedAlbums()), 1)

    def test_new_release_roundtrip(self):
        al = sm.UserAlbum("Fresh", "New Artist", 10, "spotify:album:nr1")
        self.ds.setNewRelease(al, [track(0)], index=0)
        self.assertEqual(self.ds.getNewReleasesCount(), 1)
        self.assertEqual(self.ds.getNewRelease(0).name, "Fresh")
        self.assertEqual(len(self.ds.getAllNewReleases()), 1)

    def test_show_roundtrip(self):
        show = sm.UserShow("My Show", "Pub", 3, "spotify:show:s1")
        eps = [sm.UserEpisode("Ep1", "Pub", "My Show", "spotify:episode:e1")]
        self.ds.setShow(show, eps, index=0)
        self.assertEqual(self.ds.getShowsCount(), 1)
        self.assertEqual(self.ds.getShow(0).name, "My Show")
        self.assertEqual(self.ds.getShowEpisodes("spotify:show:s1")[0].name, "Ep1")
        self.assertEqual(len(self.ds.getAllSavedShows()), 1)

    def test_devices(self):
        self.ds.setUserDevice(sm.UserDevice("d1", "Spotifypod", True))
        self.ds.setUserDevice(sm.UserDevice("d2", "Spotifypod 2", False))
        self.assertEqual(len(self.ds.getAllSavedDevices()), 2)
        self.assertEqual(self.ds.getSavedDevice("d1").name, "Spotifypod")
        self.ds.clearDevices()
        self.assertEqual(self.ds.getAllSavedDevices(), [])

    def test_clear_only_removes_app_keys(self):
        self.ds.r.set("unrelated:key", "keepme")
        self.ds.setSavedTrack(0, track(0))
        self.ds.clear()
        self.assertEqual(self.ds.getSavedTrackCount(), 0)
        self.assertEqual(self.ds.r.get("unrelated:key"), b"keepme")


class TestDatastoreDegraded(unittest.TestCase):
    """When Redis is unreachable, reads degrade to empty instead of raising."""
    def setUp(self):
        self.ds = datastore.Datastore(client=RaisingRedis())

    def test_ping_false(self):
        self.assertFalse(self.ds.ping())

    def test_reads_degrade_quietly(self):
        self.assertEqual(self.ds.getArtistCount(), 0)
        self.assertEqual(self.ds.getAllSavedPlaylists(), [])
        self.assertEqual(self.ds.getAllSavedDevices(), [])
        self.assertIsNone(self.ds.getArtist(0))


if __name__ == "__main__":
    unittest.main()
