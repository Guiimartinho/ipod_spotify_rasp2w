"""View-model layer for sPot.

Page objects model the iPod menu/navigation and produce immutable ``Rendering``
snapshots that ``spotifypod.py`` draws.

Changes vs. the original:
  * No longer calls ``spotify_manager.refresh_devices()`` at import time — startup
    side effects now live in ``spotify_manager.start()``, called from the app's main().
  * ``@lru_cache`` on instance methods (which leaked page objects and returned stale
    data after a refresh) replaced with a plain per-instance dict.
  * Fixed the mutable-default-argument on ``MenuRendering``.
  * Play-on-render pages now play exactly once instead of on every redraw, and handle
    the no-context (saved track) case instead of crashing.
"""
from __future__ import annotations

import logging
import re as re
from typing import Any, Callable, Optional

import config
import spotify_manager

log = logging.getLogger("spot.viewmodel")

MENU_PAGE_SIZE = config.MENU_PAGE_SIZE

# Screen render types
MENU_RENDER_TYPE = 0
NOW_PLAYING_RENDER = 1
SEARCH_RENDER = 2

# Menu line item types
LINE_NORMAL = 0
LINE_HIGHLIGHT = 1
LINE_TITLE = 2


class LineItem():
    def __init__(self, title: str = "", line_type: int = LINE_NORMAL, show_arrow: bool = False) -> None:
        self.title = title
        self.line_type = line_type
        self.show_arrow = show_arrow


class Rendering():
    def __init__(self, type: int) -> None:
        self.type = type

    def unsubscribe(self) -> None:
        pass


class MenuRendering(Rendering):
    def __init__(self, header: str = "", lines: Optional[list] = None,
                 page_start: int = 0, total_count: int = 0) -> None:
        super().__init__(MENU_RENDER_TYPE)
        self.lines = lines if lines is not None else []
        self.header = header
        self.page_start = page_start
        self.total_count = total_count
        self.now_playing = spotify_manager.DATASTORE.now_playing
        self.has_internet = spotify_manager.has_internet


class NowPlayingRendering(Rendering):
    def __init__(self) -> None:
        super().__init__(NOW_PLAYING_RENDER)
        self.callback: Optional[Callable] = None
        self.after_id: Any = None

    def subscribe(self, app: Any, callback: Callable) -> None:
        if callback == self.callback:
            return
        new_callback = self.callback is None
        self.callback = callback
        self.app = app
        if new_callback:
            self.refresh()

    def refresh(self) -> None:
        if not self.callback:
            return
        if self.after_id:
            self.app.after_cancel(self.after_id)
        self.callback(spotify_manager.DATASTORE.now_playing)
        self.after_id = self.app.after(500, lambda: self.refresh())

    def unsubscribe(self) -> None:
        super().unsubscribe()
        self.callback = None
        self.app = None


class NowPlayingCommand():
    def __init__(self, runnable: Callable[[], Any] = lambda: ()) -> None:
        self.has_run = False
        self.runnable = runnable

    def run(self) -> None:
        self.has_run = True
        self.runnable()


class SearchRendering(Rendering):
    def __init__(self, query: str, active_char: int) -> None:
        super().__init__(SEARCH_RENDER)
        self.query = query
        self.active_char = active_char
        self.loading = False
        self.callback: Optional[Callable] = None
        self.results: Any = None

    def get_active_char(self) -> str:
        return ' ' if self.active_char == 26 else chr(self.active_char + ord('a'))

    def subscribe(self, app: Any, callback: Callable) -> None:
        if (callback == self.callback):
            return
        new_callback = self.callback is None
        self.callback = callback
        self.app = app
        if new_callback:
            self.refresh()

    def refresh(self) -> None:
        if not self.callback:
            return
        self.callback(self.query, self.get_active_char(), self.loading, self.results)
        self.results = None

    def unsubscribe(self) -> None:
        super().unsubscribe()
        self.callback = None
        self.app = None


class SearchPage():
    def __init__(self, previous_page: Any) -> None:
        self.header = "Search"
        self.has_sub_page = True
        self.previous_page = previous_page
        self.live_render = SearchRendering("", 0)
        self.is_title = False

    def nav_prev(self) -> None:
        self.live_render.query = self.live_render.query[0:-1]
        self.live_render.refresh()

    def nav_next(self) -> None:
        if len(self.live_render.query) > 15:
            return
        self.live_render.query += self.live_render.get_active_char()
        self.live_render.refresh()

    def nav_play(self) -> None:
        pass

    def nav_up(self) -> None:
        self.live_render.active_char += 1
        if (self.live_render.active_char > 26):
            self.live_render.active_char = 0
        self.live_render.refresh()

    def nav_down(self) -> None:
        self.live_render.active_char -= 1
        if (self.live_render.active_char < 0):
            self.live_render.active_char = 26
        self.live_render.refresh()

    def run_search(self, query: str) -> None:
        self.live_render.loading = True
        self.live_render.refresh()
        self.live_render.results = spotify_manager.search(query)
        self.live_render.loading = False
        self.live_render.refresh()

    def nav_select(self) -> Any:
        spotify_manager.run_async(lambda: self.run_search(self.live_render.query))
        return self

    def nav_back(self) -> Any:
        return self.previous_page

    def render(self) -> Rendering:
        return self.live_render


class NowPlayingPage():
    def __init__(self, previous_page: Any, header: str, command: NowPlayingCommand) -> None:
        self.has_sub_page = False
        self.previous_page = previous_page
        self.command = command
        self.header = header
        self.live_render = NowPlayingRendering()
        self.is_title = False

    def play_previous(self) -> None:
        spotify_manager.play_previous()
        self.live_render.refresh()

    def play_next(self) -> None:
        spotify_manager.play_next()
        self.live_render.refresh()

    def toggle_play(self) -> None:
        spotify_manager.toggle_play()
        self.live_render.refresh()

    def nav_prev(self) -> None:
        spotify_manager.run_async(lambda: self.play_previous())

    def nav_next(self) -> None:
        spotify_manager.run_async(lambda: self.play_next())

    def nav_play(self) -> None:
        spotify_manager.run_async(lambda: self.toggle_play())

    def nav_up(self) -> None:
        pass

    def nav_down(self) -> None:
        pass

    def nav_select(self) -> Any:
        return self

    def nav_back(self) -> Any:
        return self.previous_page

    def render(self) -> Rendering:
        if (not self.command.has_run):
            self.command.run()
        return self.live_render


class MenuPage():
    def __init__(self, header: str, previous_page: Any, has_sub_page: bool,
                 is_title: bool = False) -> None:
        self.index = 0
        self.page_start = 0
        self.header = header
        self.has_sub_page = has_sub_page
        self.previous_page = previous_page
        self.is_title = is_title

    def total_size(self) -> int:
        return 0

    def page_at(self, index: int) -> Any:
        return None

    def nav_prev(self) -> None:
        spotify_manager.run_async(lambda: spotify_manager.play_previous())

    def nav_next(self) -> None:
        spotify_manager.run_async(lambda: spotify_manager.play_next())

    def nav_play(self) -> None:
        spotify_manager.run_async(lambda: spotify_manager.toggle_play())

    def get_index_jump_up(self) -> int:
        return 1

    def get_index_jump_down(self) -> int:
        return 1

    def nav_up(self) -> None:
        jump = self.get_index_jump_up()
        if(self.index >= self.total_size() - jump):
            return
        if (self.index >= self.page_start + MENU_PAGE_SIZE - jump):
            self.page_start = self.page_start + jump
        self.index = self.index + jump

    def nav_down(self) -> None:
        jump = self.get_index_jump_down()
        if(self.index <= (jump - 1)):
            return
        if (self.index <= self.page_start + (jump - 1)):
            self.page_start = self.page_start - jump
            if (self.page_start == 1):
                self.page_start = 0
        self.index = self.index - jump

    def nav_select(self) -> Any:
        return self.page_at(self.index)

    def nav_back(self) -> Any:
        return self.previous_page

    def render(self) -> Rendering:
        lines = []
        total_size = self.total_size()
        for i in range(self.page_start, self.page_start + MENU_PAGE_SIZE):
            if (i < total_size):
                page = self.page_at(i)
                if (page is None):
                    lines.append(LineItem())
                else:
                    line_type = LINE_TITLE if page.is_title else \
                        LINE_HIGHLIGHT if i == self.index else LINE_NORMAL
                    lines.append(LineItem(page.header, line_type, page.has_sub_page))
            else:
                lines.append(LineItem())
        return MenuRendering(lines=lines, header=self.header, page_start=self.index, total_count=total_size)


class ShowsPage(MenuPage):
    def __init__(self, previous_page: Any) -> None:
        super().__init__(self.get_title(), previous_page, has_sub_page=True)
        self.shows = self.get_content()
        self.num_shows = len(self.shows)
        self._page_cache: dict = {}

    def get_title(self) -> str:
        return "Podcasts"

    def get_content(self) -> list:
        return spotify_manager.DATASTORE.getAllSavedShows()

    def total_size(self) -> int:
        return self.num_shows

    def page_at(self, index: int) -> Any:
        if index not in self._page_cache:
            self._page_cache[index] = SingleShowPage(self.shows[index], self)
        return self._page_cache[index]


class PlaylistsPage(MenuPage):
    def __init__(self, previous_page: Any) -> None:
        super().__init__(self.get_title(), previous_page, has_sub_page=True)
        self.playlists = self.get_content()
        self.num_playlists = len(self.playlists)
        self._page_cache: dict = {}
        # sort playlists to keep order as arranged in the Spotify library
        self.playlists.sort(key=self.get_idx)

    def get_title(self) -> str:
        return "Playlists"

    def get_content(self) -> list:
        return spotify_manager.DATASTORE.getAllSavedPlaylists()

    def get_idx(self, e: Any) -> int:
        # self.playlists may also contain albums (no idx attribute)
        if type(e) == spotify_manager.UserPlaylist:
            return e.idx
        return 0

    def total_size(self) -> int:
        return self.num_playlists

    def page_at(self, index: int) -> Any:
        if index not in self._page_cache:
            self._page_cache[index] = SinglePlaylistPage(self.playlists[index], self)
        return self._page_cache[index]


class AlbumsPage(PlaylistsPage):
    def __init__(self, previous_page: Any) -> None:
        super().__init__(previous_page)

    def get_title(self) -> str:
        return "Albums"

    def get_content(self) -> list:
        return spotify_manager.DATASTORE.getAllSavedAlbums()


class SearchResultsPage(MenuPage):
    def __init__(self, previous_page: Any, results: Any) -> None:
        super().__init__("Search Results", previous_page, has_sub_page=True)
        self.results = results
        tracks, albums, artists = len(results.tracks), len(results.albums), len(results.artists)
        # Add 1 to each count (if > 0) to make room for section header line items
        self.tracks = tracks + 1 if tracks > 0 else 0
        self.artists = artists + 1 if artists > 0 else 0
        self.albums = albums + 1 if albums > 0 else 0
        self.total_count = self.tracks + self.albums + self.artists
        self.index = 1
        # indices of the section header line items
        self.header_indices = [0, self.tracks, self.artists + self.tracks]

    def total_size(self) -> int:
        return self.total_count

    def page_at(self, index: int) -> Any:
        if self.tracks > 0 and index == 0:
            return PlaceHolderPage("TRACKS", self, has_sub_page=False, is_title=True)
        elif self.artists > 0 and index == self.header_indices[1]:
            return PlaceHolderPage("ARTISTS", self, has_sub_page=False, is_title=True)
        elif self.albums > 0 and index == self.header_indices[2]:
            return PlaceHolderPage("ALBUMS", self, has_sub_page=False, is_title=True)
        elif self.tracks > 0 and index < self.header_indices[1]:
            track = self.results.tracks[index - 1]
            command = NowPlayingCommand(lambda: spotify_manager.play_track(track.uri))
            return NowPlayingPage(self, track.title, command)
        elif self.albums > 0 and index < self.header_indices[2]:
            artist = self.results.artists[index - (self.tracks + 1)]
            command = NowPlayingCommand(lambda: spotify_manager.play_artist(artist.uri))
            return NowPlayingPage(self, artist.name, command)
        else:
            album = self.results.albums[index - (self.artists + self.tracks + 1)]
            tracks = self.results.album_track_map[album.uri]
            return InMemoryPlaylistPage(album, tracks, self)

    def get_index_jump_up(self) -> int:
        if self.index + 1 in self.header_indices:
            return 2
        return 1

    def get_index_jump_down(self) -> int:
        if self.index - 1 in self.header_indices:
            return 2
        return 1


class NewReleasesPage(PlaylistsPage):
    def __init__(self, previous_page: Any) -> None:
        super().__init__(previous_page)

    def get_title(self) -> str:
        return "New Releases"

    def get_content(self) -> list:
        return spotify_manager.DATASTORE.getAllNewReleases()


class ArtistsPage(MenuPage):
    def __init__(self, previous_page: Any) -> None:
        super().__init__("Artists", previous_page, has_sub_page=True)

    def total_size(self) -> int:
        return spotify_manager.DATASTORE.getArtistCount()

    def page_at(self, index: int) -> Any:
        artist = spotify_manager.DATASTORE.getArtist(index)
        command = NowPlayingCommand(lambda: spotify_manager.play_artist(artist.uri))
        return NowPlayingPage(self, artist.name, command)


class SinglePlaylistPage(MenuPage):
    # Credit for the emoji-stripping regex: https://stackoverflow.com/a/49986645
    _EMOJI_RE = re.compile(pattern="["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "]+", flags=re.UNICODE)

    def __init__(self, playlist: Any, previous_page: Any) -> None:
        super().__init__(self._EMOJI_RE.sub(r'', playlist.name), previous_page, has_sub_page=True)
        self.playlist = playlist
        self.tracks: Optional[list] = None

    def get_tracks(self) -> list:
        if self.tracks is None:
            self.tracks = spotify_manager.DATASTORE.getPlaylistTracks(self.playlist.uri) or []
        return self.tracks

    def total_size(self) -> int:
        return self.playlist.track_count

    def page_at(self, index: int) -> Any:
        track = self.get_tracks()[index]
        command = NowPlayingCommand(lambda: spotify_manager.play_from_playlist(self.playlist.uri, track.uri, None))
        return NowPlayingPage(self, track.title, command)


class SingleShowPage(MenuPage):
    def __init__(self, show: Any, previous_page: Any) -> None:
        super().__init__(show.name, previous_page, has_sub_page=True)
        self.show = show
        self.episodes: Optional[list] = None

    def get_episodes(self) -> list:
        if self.episodes is None:
            self.episodes = spotify_manager.DATASTORE.getShowEpisodes(self.show.uri) or []
        return self.episodes

    def total_size(self) -> int:
        return self.show.episode_count

    def page_at(self, index: int) -> Any:
        episode = self.get_episodes()[index]
        command = NowPlayingCommand(lambda: spotify_manager.play_from_show(self.show.uri, episode.uri, None))
        return NowPlayingPage(self, episode.name, command)


class InMemoryPlaylistPage(SinglePlaylistPage):
    def __init__(self, playlist: Any, tracks: list, previous_page: Any) -> None:
        super().__init__(playlist, previous_page)
        self.tracks = tracks


class SingleTrackPage(MenuPage):
    def __init__(self, track: Any, previous_page: Any, playlist: Any = None, album: Any = None) -> None:
        super().__init__(track.title, previous_page, has_sub_page=False)
        self.track = track
        self.playlist = playlist
        self.album = album
        self._played = False

    def render(self) -> Rendering:
        r = super().render()
        if not self._played:
            self._played = True
            if self.playlist:
                spotify_manager.play_from_playlist(self.playlist.uri, self.track.uri, None)
            elif self.album:
                spotify_manager.play_from_playlist(self.album.uri, self.track.uri, None)
            else:
                spotify_manager.play_track(self.track.uri)
        return r


class SingleEpisodePage(MenuPage):
    def __init__(self, episode: Any, previous_page: Any, show: Any = None) -> None:
        super().__init__(episode.name, previous_page, has_sub_page=False)
        self.episode = episode
        self.show = show
        self._played = False

    def render(self) -> Rendering:
        r = super().render()
        if not self._played and self.show:
            self._played = True
            spotify_manager.play_from_show(self.show.uri, self.episode.uri, None)
        return r


class SavedTracksPage(MenuPage):
    def __init__(self, previous_page: Any) -> None:
        super().__init__("Saved Tracks", previous_page, has_sub_page=True)

    def total_size(self) -> int:
        return spotify_manager.DATASTORE.getSavedTrackCount()

    def page_at(self, index: int) -> Any:
        return SingleTrackPage(spotify_manager.DATASTORE.getSavedTrack(index), self)


class PlaceHolderPage(MenuPage):
    def __init__(self, header: str, previous_page: Any,
                 has_sub_page: bool = True, is_title: bool = False) -> None:
        super().__init__(header, previous_page, has_sub_page, is_title)


class RootPage(MenuPage):
    def __init__(self, previous_page: Any) -> None:
        super().__init__("sPot", previous_page, has_sub_page=True)
        self.pages = [
            ArtistsPage(self),
            AlbumsPage(self),
            NewReleasesPage(self),
            PlaylistsPage(self),
            ShowsPage(self),
            SearchPage(self),
            NowPlayingPage(self, "Now Playing", NowPlayingCommand())
        ]
        self.index = 0
        self.page_start = 0

    def get_pages(self) -> list:
        if (not spotify_manager.DATASTORE.now_playing):
            return self.pages[0:-1]
        return self.pages

    def total_size(self) -> int:
        return len(self.get_pages())

    def page_at(self, index: int) -> Any:
        return self.get_pages()[index]
