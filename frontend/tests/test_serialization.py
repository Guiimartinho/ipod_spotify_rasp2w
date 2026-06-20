import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)  # tests/  (fake_redis)
sys.path.insert(0, os.path.dirname(_HERE))  # frontend/  (config, serialization, ...)

import serialization
import spotify_manager as sm  # importing registers the domain classes


class TestSerialization(unittest.TestCase):
    def _roundtrip(self, obj):
        return serialization.loads(serialization.dumps(obj))

    def test_track_roundtrip(self):
        t = sm.UserTrack("Song", "Artist", "Album", "spotify:track:1")
        out = self._roundtrip(t)
        self.assertIs(type(out), sm.UserTrack)
        self.assertEqual(out.title, "Song")
        self.assertEqual(out.artist, "Artist")
        self.assertEqual(out.album, "Album")
        self.assertEqual(out.uri, "spotify:track:1")

    def test_all_registered_types_roundtrip(self):
        samples = [
            sm.UserDevice("d1", "Spotifypod", True),
            sm.UserAlbum("Al", "Ar", 12, "spotify:album:1"),
            sm.UserEpisode("Ep", "Pub", "Show", "spotify:episode:1"),
            sm.UserShow("Show", "Pub", 5, "spotify:show:1"),
            sm.UserArtist("Ar", "spotify:artist:1"),
            sm.UserPlaylist("PL", 3, "spotify:playlist:1", 20),
        ]
        for obj in samples:
            out = self._roundtrip(obj)
            self.assertIs(type(out), type(obj))
            for slot in obj.__slots__:
                self.assertEqual(getattr(out, slot), getattr(obj, slot))

    def test_list_of_objects(self):
        tracks = [sm.UserTrack("a", "x", "y", "u%d" % i) for i in range(3)]
        out = self._roundtrip(tracks)
        self.assertEqual(len(out), 3)
        self.assertEqual([t.uri for t in out], ["u0", "u1", "u2"])
        self.assertTrue(all(isinstance(t, sm.UserTrack) for t in out))

    def test_none_and_unicode(self):
        self.assertIsNone(serialization.loads(serialization.dumps(None)))
        self.assertIsNone(serialization.loads(None))
        t = sm.UserTrack("Café — naïve 日本語", "Ártist", "Albüm", "uri")
        self.assertEqual(self._roundtrip(t).title, "Café — naïve 日本語")

    def test_dict_passthrough(self):
        out = self._roundtrip({"a": 1, "b": [1, 2, 3]})
        self.assertEqual(out, {"a": 1, "b": [1, 2, 3]})

    def test_unknown_type_raises(self):
        class NotRegistered:
            __slots__ = ["x"]

            def __init__(self):
                self.x = 1

        with self.assertRaises(TypeError):
            serialization.dumps(NotRegistered())


if __name__ == "__main__":
    unittest.main()
