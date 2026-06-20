"""Spotify Web API layer for sPot (wraps spotipy).

Changes vs. the original:
  * The spotipy client is created lazily and accessed through a thread-safe proxy.
    The original shared one client across the background poller and user-action
    threads with no locking; requests' session is not thread-safe. ``sp`` now
    serializes every call with a re-entrant lock.
  * ``import spotipy`` is deferred to first use so this module (and everything that
    imports it) loads without spotipy installed — which is what makes the test suite
    runnable on a bare Python.
  * Network calls are wrapped so a transient error logs and returns instead of
    killing a worker thread.
  * Module import no longer performs any network I/O or starts threads; call
    ``start()`` once at app startup instead.
  * Bug fixes: ``get_album_tracks`` used the playlist endpoint; the now-playing
    track-index lookup raised ``StopIteration``; new-releases/shows weren't paginated.
"""
import logging
import threading
import time

import config
import datastore
import serialization

log = logging.getLogger("spot.manager")


@serialization.register
class UserDevice():
    __slots__ = ['id', 'name', 'is_active']
    def __init__(self, id, name, is_active):
        self.id = id
        self.name = name
        self.is_active = is_active


@serialization.register
class UserTrack():
    __slots__ = ['title', 'artist', 'album', 'uri']
    def __init__(self, title, artist, album, uri):
        self.title = title
        self.artist = artist
        self.album = album
        self.uri = uri

    def __str__(self):
        return self.title + " - " + self.artist + " - " + self.album


@serialization.register
class UserAlbum():
    __slots__ = ['name', 'artist', 'track_count', 'uri']
    def __init__(self, name, artist, track_count, uri):
        self.name = name
        self.artist = artist
        self.uri = uri
        self.track_count = track_count

    def __str__(self):
        return self.name + " - " + self.artist


@serialization.register
class UserEpisode():
    __slots__ = ['name', 'publisher', 'show', 'uri']
    def __init__(self, name, publisher, show, uri):
        self.name = name
        self.publisher = publisher
        self.show = show
        self.uri = uri

    def __str__(self):
        return self.name + " - " + self.publisher


@serialization.register
class UserShow():
    __slots__ = ['name', 'publisher', 'episode_count', 'uri']
    def __init__(self, name, publisher, episode_count, uri):
        self.name = name
        self.publisher = publisher
        self.episode_count = episode_count
        self.uri = uri

    def __str__(self):
        return self.name + " - " + self.publisher


@serialization.register
class UserArtist():
    __slots__ = ['name', 'uri']
    def __init__(self, name, uri):
        self.name = name
        self.uri = uri

    def __str__(self):
        return self.name


@serialization.register
class UserPlaylist():
    __slots__ = ['name', 'idx', 'uri', 'track_count']
    def __init__(self, name, idx, uri, track_count):
        self.name = name
        self.idx = idx
        self.uri = uri
        self.track_count = track_count

    def __str__(self):
        return self.name


class SearchResults():
    __slots__ = ['tracks', 'artists', 'albums', 'album_track_map']
    def __init__(self, tracks, artists, albums, album_track_map):
        self.tracks = tracks
        self.artists = artists
        self.albums = albums
        self.album_track_map = album_track_map


scope = "user-follow-read," \
        "user-library-read," \
        "user-library-modify," \
        "user-modify-playback-state," \
        "user-read-playback-state," \
        "user-read-currently-playing," \
        "app-remote-control," \
        "playlist-read-private," \
        "playlist-read-collaborative," \
        "playlist-modify-public," \
        "playlist-modify-private," \
        "streaming"

DATASTORE = datastore.Datastore()

pageSize = config.PAGE_SIZE
has_internet = False

# ---------------------------------------------------------------------------
# Thread-safe, lazily-initialised spotipy client.
# ---------------------------------------------------------------------------
_sp = None
_sp_lock = threading.RLock()


def _create_spotify():
    import spotipy  # deferred so this module imports without spotipy installed
    from spotipy.oauth2 import SpotifyOAuth
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(scope=scope),
        requests_timeout=config.REQUESTS_TIMEOUT,
        retries=config.REQUESTS_RETRIES,
    )


def get_sp():
    global _sp
    with _sp_lock:
        if _sp is None:
            _sp = _create_spotify()
        return _sp


class _SpotifyProxy():
    """Forwards attribute access to the real client, serialising every call."""
    def __getattr__(self, name):
        target = getattr(get_sp(), name)
        if not callable(target):
            return target

        def locked(*args, **kwargs):
            with _sp_lock:
                return target(*args, **kwargs)
        return locked


sp = _SpotifyProxy()


def check_internet(request):
    global has_internet
    try:
        result = request()
        has_internet = True
    except Exception as e:
        log.warning("network request failed: %s", e)
        result = None
        has_internet = False
    return result


def _safe_action(fn):
    """Wrap a transport/playback function so an error logs instead of killing a thread."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            log.warning("%s failed: %s", fn.__name__, e)
            return None
    wrapper.__name__ = fn.__name__
    return wrapper


# ---------------------------------------------------------------------------
# Single-item fetch + parse
# ---------------------------------------------------------------------------
def get_playlist(id):
    results = sp.playlist(id)
    tracks = []
    for item in results['tracks']['items']:
        track = item['track']
        tracks.append(UserTrack(track['name'], track['artists'][0]['name'], track['album']['name'], track['uri']))
    # index 0 because we don't have/need the library sort index when fetching directly
    return (UserPlaylist(results['name'], 0, results['uri'], len(tracks)), tracks)


def get_show(id):
    results = sp.show(id)
    show = results['name']
    publisher = results['publisher']
    episodes = []
    for item in results['episodes']['items']:
        episodes.append(UserEpisode(item['name'], publisher, show, item['uri']))
    return (UserShow(results['name'], publisher, len(episodes), results['uri']), episodes)


def get_album(id):
    results = sp.album(id)
    album = results['name']
    artist = results['artists'][0]['name']
    tracks = []
    for item in results['tracks']['items']:
        tracks.append(UserTrack(item['name'], artist, album, item['uri']))
    return (UserAlbum(results['name'], artist, len(tracks), results['uri']), tracks)


def get_playlist_tracks(id):
    tracks = []
    results = sp.playlist_tracks(id, limit=pageSize)
    while results:
        for item in results['items']:
            track = item['track']
            if track is None:
                continue  # local files / unavailable tracks come back as null
            tracks.append(UserTrack(track['name'], track['artists'][0]['name'], track['album']['name'], track['uri']))
        results = sp.next(results) if results['next'] else None
    return tracks


def get_album_tracks(id):
    # NOTE: the original used sp.playlist_tracks on an album id (wrong endpoint).
    tracks = []
    album = sp.album(id)
    album_name = album['name']
    artist = album['artists'][0]['name']
    results = album['tracks']
    while results:
        for item in results['items']:
            tracks.append(UserTrack(item['name'], artist, album_name, item['uri']))
        results = sp.next(results) if results['next'] else None
    return tracks


def refresh_devices():
    results = sp.devices()
    DATASTORE.clearDevices()
    for item in results['devices']:
        if config.DEVICE_NAME_FILTER in item['name']:
            log.info("found device %s", item['name'])
            DATASTORE.setUserDevice(UserDevice(item['id'], item['name'], item['is_active']))


def parse_album(album):
    artist = album['artists'][0]['name']
    tracks = []
    if 'tracks' not in album:
        return get_album(album['id'])
    for track in album['tracks']['items']:
        tracks.append(UserTrack(track['name'], artist, album['name'], track['uri']))
    return (UserAlbum(album['name'], artist, len(tracks), album['uri']), tracks)


def parse_show(show):
    publisher = show['publisher']
    episodes = []
    if 'episodes' not in show:
        return get_show(show['id'])
    for episode in show['episodes']['items']:
        episodes.append(UserEpisode(episode['name'], publisher, show['name'], episode['uri']))
    return (UserShow(show['name'], publisher, len(episodes), show['uri']), episodes)


# ---------------------------------------------------------------------------
# Full library sync
# ---------------------------------------------------------------------------
def _refresh_saved_tracks():
    results = sp.current_user_saved_tracks(limit=pageSize, offset=0)
    while results:
        offset = results['offset']
        for idx, item in enumerate(results['items']):
            track = item['track']
            DATASTORE.setSavedTrack(idx + offset, UserTrack(
                track['name'], track['artists'][0]['name'], track['album']['name'], track['uri']))
        results = sp.next(results) if results['next'] else None
    log.info("saved tracks fetched: %d", DATASTORE.getSavedTrackCount())


def _refresh_artists():
    offset = 0
    results = sp.current_user_followed_artists(limit=pageSize)
    while results:
        artists = results['artists']
        for idx, item in enumerate(artists['items']):
            DATASTORE.setArtist(idx + offset, UserArtist(item['name'], item['uri']))
        if artists['next']:
            results = sp.next(artists)
            offset += pageSize
        else:
            results = None
    log.info("artists fetched: %d", DATASTORE.getArtistCount())


def _refresh_playlists():
    results = sp.current_user_playlists(limit=pageSize)
    totalindex = 0  # preserves Spotify library order across pages
    while results:
        offset = results['offset']
        for idx, item in enumerate(results['items']):
            tracks = get_playlist_tracks(item['id'])
            DATASTORE.setPlaylist(
                UserPlaylist(item['name'], totalindex, item['uri'], len(tracks)),
                tracks, index=idx + offset)
            totalindex += 1
        results = sp.next(results) if results['next'] else None
    log.info("playlists fetched: %d", DATASTORE.getPlaylistCount())


def _refresh_albums():
    results = sp.current_user_saved_albums(limit=pageSize)
    while results:
        offset = results['offset']
        for idx, item in enumerate(results['items']):
            album, tracks = parse_album(item['album'])
            DATASTORE.setAlbum(album, tracks, index=idx + offset)
        results = sp.next(results) if results['next'] else None
    log.info("albums fetched")


def _refresh_new_releases():
    page = sp.new_releases(limit=pageSize)['albums']
    idx = 0
    while page:
        for item in page['items']:
            album, tracks = parse_album(item)
            DATASTORE.setNewRelease(album, tracks, index=idx)
            idx += 1
        page = sp.next(page) if page['next'] else None
    log.info("new releases fetched")


def _refresh_shows():
    results = sp.current_user_saved_shows(limit=pageSize)
    idx = 0
    while results:
        for item in results['items']:
            show, episodes = parse_show(item['show'])
            DATASTORE.setShow(show, episodes, index=idx)
            idx += 1
        results = sp.next(results) if results['next'] else None
    log.info("shows fetched")


def refresh_data():
    DATASTORE.clear()
    # Each section is isolated so one failure doesn't abort the whole sync.
    for section in (_refresh_saved_tracks, _refresh_artists, _refresh_playlists,
                    _refresh_albums, _refresh_new_releases, _refresh_shows, refresh_devices):
        try:
            section()
        except Exception as e:
            log.warning("refresh section %s failed: %s", section.__name__, e)
    log.info("refresh_data complete")


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------
def _default_device():
    devices = DATASTORE.getAllSavedDevices()
    if not devices:
        log.warning("no Spotify devices available — start raspotify / a Connect device")
        return None
    return devices[0].id


@_safe_action
def play_artist(artist_uri, device_id=None):
    device_id = device_id or _default_device()
    if not device_id:
        return
    sp.start_playback(device_id=device_id, context_uri=artist_uri)
    refresh_now_playing()


@_safe_action
def play_track(track_uri, device_id=None):
    device_id = device_id or _default_device()
    if not device_id:
        return
    sp.start_playback(device_id=device_id, uris=[track_uri])
    refresh_now_playing()


@_safe_action
def play_episode(episode_uri, device_id=None):
    device_id = device_id or _default_device()
    if not device_id:
        return
    sp.start_playback(device_id=device_id, uris=[episode_uri])
    refresh_now_playing()


@_safe_action
def play_from_playlist(playist_uri, track_uri, device_id=None):
    log.info("playing %s from %s", track_uri, playist_uri)
    device_id = device_id or _default_device()
    if not device_id:
        return
    sp.start_playback(device_id=device_id, context_uri=playist_uri, offset={"uri": track_uri})
    refresh_now_playing()


@_safe_action
def play_from_show(show_uri, episode_uri, device_id=None):
    log.info("playing %s from %s", episode_uri, show_uri)
    device_id = device_id or _default_device()
    if not device_id:
        return
    sp.start_playback(device_id=device_id, context_uri=show_uri, offset={"uri": episode_uri})
    refresh_now_playing()


# ---------------------------------------------------------------------------
# Now playing
# ---------------------------------------------------------------------------
def get_now_playing():
    response = check_internet(lambda: sp.current_playback(additional_types='episode'))
    if not response:
        return None
    if response.get('currently_playing_type') == 'episode':
        return get_now_playing_episode(response=response)
    return get_now_playing_track(response=response)


def _track_index(tracks, track_uri):
    """1-based index of track_uri in tracks, or -1 if not found (no exception)."""
    idx = next((i for i, val in enumerate(tracks) if val.uri == track_uri), None)
    return idx + 1 if idx is not None else -1


def get_now_playing_track(response=None):
    if not response or not response.get('item'):
        return None
    context = response['context']
    track = response['item']
    track_uri = track['uri']
    artist = track['artists'][0]['name']
    now_playing = {
        'name': track['name'],
        'track_uri': track_uri,
        'artist': artist,
        'album': track['album']['name'],
        'duration': track['duration_ms'],
        'is_playing': response['is_playing'],
        'progress': response['progress_ms'],
        'context_name': artist,
        'track_index': -1,
        'timestamp': time.time(),
    }
    if not context:
        return now_playing
    try:
        if context['type'] == 'playlist':
            uri = context['uri']
            playlist = DATASTORE.getPlaylistUri(uri)
            tracks = DATASTORE.getPlaylistTracks(uri)
            if not playlist:
                playlist, tracks = get_playlist(uri.split(":")[-1])
                DATASTORE.setPlaylist(playlist, tracks)
            tracks = tracks or []
            now_playing['track_index'] = _track_index(tracks, track_uri)
            now_playing['track_total'] = len(tracks)
            now_playing['context_name'] = playlist.name if playlist else artist
        elif context['type'] == 'album':
            uri = context['uri']
            album = DATASTORE.getAlbumUri(uri)
            tracks = DATASTORE.getPlaylistTracks(uri)
            if not album:
                album, tracks = get_album(uri.split(":")[-1])
                DATASTORE.setAlbum(album, tracks)
            tracks = tracks or []
            now_playing['track_index'] = _track_index(tracks, track_uri)
            now_playing['track_total'] = len(tracks)
            now_playing['context_name'] = album.name if album else artist
    except Exception as e:
        log.warning("could not resolve now-playing context: %s", e)
    return now_playing


def get_now_playing_episode(response=None):
    if not response or not response.get('item'):
        return None
    episode = response['item']
    return {
        'name': episode['name'],
        'track_uri': episode['uri'],
        'artist': episode['show']['publisher'],
        'album': episode['show']['name'],
        'duration': episode['duration_ms'],
        'is_playing': response['is_playing'],
        'progress': response['progress_ms'],
        'context_name': episode['show']['publisher'],
        'track_index': -1,
        'timestamp': time.time(),
    }


def search(query):
    try:
        track_results = sp.search(query, limit=config.SEARCH_LIMIT, type='track')
        tracks = [UserTrack(i['name'], i['artists'][0]['name'], i['album']['name'], i['uri'])
                  for i in track_results['tracks']['items']]
        artist_results = sp.search(query, limit=config.SEARCH_LIMIT, type='artist')
        artists = [UserArtist(i['name'], i['uri'])
                   for i in artist_results['artists']['items']]
        album_results = sp.search(query, limit=config.SEARCH_LIMIT, type='album')
        albums = []
        album_track_map = {}
        for item in album_results['albums']['items']:
            album, album_tracks = parse_album(item)
            albums.append(album)
            album_track_map[album.uri] = album_tracks
        return SearchResults(tracks, artists, albums, album_track_map)
    except Exception as e:
        log.warning("search failed: %s", e)
        return SearchResults([], [], [], {})


def refresh_now_playing():
    DATASTORE.now_playing = get_now_playing()


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
sleep_time = config.NOW_PLAYING_MIN_INTERVAL


@_safe_action
def play_next():
    global sleep_time
    sp.next_track()
    sleep_time = config.ACTION_INTERVAL
    refresh_now_playing()


@_safe_action
def play_previous():
    global sleep_time
    sp.previous_track()
    sleep_time = config.ACTION_INTERVAL
    refresh_now_playing()


@_safe_action
def pause():
    global sleep_time
    sp.pause_playback()
    sleep_time = config.ACTION_INTERVAL
    refresh_now_playing()


@_safe_action
def resume():
    global sleep_time
    sp.start_playback()
    sleep_time = config.ACTION_INTERVAL
    refresh_now_playing()


def toggle_play():
    now_playing = DATASTORE.now_playing
    if not now_playing:
        return
    if now_playing['is_playing']:
        pause()
    else:
        resume()


# ---------------------------------------------------------------------------
# Background polling + lifecycle
# ---------------------------------------------------------------------------
_bg_thread = None


def bg_loop():
    global sleep_time
    while True:
        try:
            refresh_now_playing()
        except Exception as e:
            log.warning("bg_loop refresh failed: %s", e)
        time.sleep(sleep_time)
        sleep_time = min(config.NOW_PLAYING_MAX_INTERVAL, sleep_time * 2)


def start(refresh_full=False):
    """Initialise data and start the background now-playing poller.

    Call once at application startup. ``refresh_full=True`` runs a full library
    sync (slow); otherwise only the Connect device list is refreshed.
    """
    global _bg_thread
    try:
        if refresh_full:
            refresh_data()
        else:
            refresh_devices()
    except Exception as e:
        log.warning("startup refresh failed: %s", e)
    if _bg_thread is None:
        _bg_thread = threading.Thread(target=bg_loop, daemon=True)
        _bg_thread.start()


def run_async(fun):
    threading.Thread(target=fun, daemon=True).start()
