import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

import datastore
import spotify_manager as sm
import view_model
from fake_redis import FakeRedis


def track(i):
    return sm.UserTrack("Track %d" % i, "Artist", "Album", "spotify:track:%d" % i)


class FakeMenu(view_model.MenuPage):
    def __init__(self, n):
        super().__init__("header", None, True)
        self.n = n

    def total_size(self):
        return self.n

    def page_at(self, i):
        return view_model.MenuPage("item%d" % i, self, False)


class TestMenuNavigation(unittest.TestCase):
    def _assert_window_invariant(self, m):
        self.assertTrue(m.page_start <= m.index < m.page_start + view_model.MENU_PAGE_SIZE)

    def test_last_item_is_reachable(self):
        m = FakeMenu(10)
        for _ in range(9):
            m.nav_up()
            self._assert_window_invariant(m)
        self.assertEqual(m.index, 9)
        # cannot move past the end
        m.nav_up()
        self.assertEqual(m.index, 9)

    def test_navigate_back_to_top(self):
        m = FakeMenu(10)
        for _ in range(9):
            m.nav_up()
        for _ in range(9):
            m.nav_down()
            self._assert_window_invariant(m)
        self.assertEqual(m.index, 0)
        self.assertEqual(m.page_start, 0)
        m.nav_down()
        self.assertEqual(m.index, 0)

    def test_small_menu_no_scroll(self):
        m = FakeMenu(3)
        m.nav_up()
        m.nav_up()
        self.assertEqual(m.index, 2)
        self.assertEqual(m.page_start, 0)
        m.nav_up()  # blocked at the end
        self.assertEqual(m.index, 2)

    def test_render_returns_page_size_lines(self):
        m = FakeMenu(10)
        ds = datastore.Datastore(client=FakeRedis())
        original = sm.DATASTORE
        sm.DATASTORE = ds
        try:
            rendering = m.render()
        finally:
            sm.DATASTORE = original
        self.assertEqual(len(rendering.lines), view_model.MENU_PAGE_SIZE)
        self.assertEqual(rendering.total_count, 10)


class TestRootPage(unittest.TestCase):
    def setUp(self):
        self._original = sm.DATASTORE
        self.ds = datastore.Datastore(client=FakeRedis())
        sm.DATASTORE = self.ds

    def tearDown(self):
        sm.DATASTORE = self._original

    def test_now_playing_toggles_last_menu_entry(self):
        root = view_model.RootPage(None)
        self.ds.now_playing = None
        self.assertEqual(root.total_size(), 6)  # "Now Playing" hidden
        self.ds.now_playing = {"is_playing": True}
        self.assertEqual(root.total_size(), 7)


class TestSinglePlaylistPage(unittest.TestCase):
    def test_emoji_stripped_from_title(self):
        pl = sm.UserPlaylist("\U0001F525 Party \U0001F389", 0, "spotify:playlist:x", 5)
        page = view_model.SinglePlaylistPage(pl, None)
        self.assertEqual(page.header.strip(), "Party")


class TestSearchResultsPage(unittest.TestCase):
    def setUp(self):
        self.results = sm.SearchResults(
            tracks=[track(0), track(1)],
            artists=[sm.UserArtist("Ar", "spotify:artist:1")],
            albums=[sm.UserAlbum("Al", "Ar", 10, "spotify:album:1")],
            album_track_map={"spotify:album:1": [track(2)]},
        )
        self.page = view_model.SearchResultsPage(None, self.results)

    def test_total_size_accounts_for_section_headers(self):
        # 2 tracks(+1), 1 artist(+1), 1 album(+1) = 3 + 2 + 2
        self.assertEqual(self.page.total_size(), 7)

    def test_section_headers_are_titles(self):
        self.assertEqual(self.page.page_at(0).header, "TRACKS")
        self.assertTrue(self.page.page_at(0).is_title)
        self.assertEqual(self.page.page_at(3).header, "ARTISTS")
        self.assertEqual(self.page.page_at(5).header, "ALBUMS")

    def test_track_item_maps_to_playable_page(self):
        item = self.page.page_at(1)
        self.assertEqual(item.header, "Track 0")
        self.assertFalse(item.has_sub_page)

    def test_album_item_maps_to_playlist_page(self):
        item = self.page.page_at(6)
        self.assertIsInstance(item, view_model.InMemoryPlaylistPage)


if __name__ == "__main__":
    unittest.main()
