"""Redis-backed cache for sPot's Spotify library.

Changes vs. the original:
  * Stores JSON (via ``serialization``) instead of ``pickle`` — no RCE risk and
    resilient to class changes.
  * The redis client is created lazily and can be injected (tests pass a fake), so
    importing this module does not require redis-py to be installed or a server up.
  * Connection parameters come from ``config`` (overridable via environment).
  * Reads are resilient: if Redis is unreachable the app degrades to empty menus
    instead of crashing (a single warning is logged).
  * ``keys()`` is replaced by non-blocking ``scan_iter``; ``clear()`` only removes
    sPot's own keys instead of wiping the whole database.
"""
import logging

import config
import serialization

log = logging.getLogger("spot.datastore")


class Datastore():
    def __init__(self, client=None):
        self.now_playing = None
        self._client = client
        self._logged_unavailable = False

    # -- connection ------------------------------------------------------------
    @property
    def r(self):
        """Lazily-created redis client. Imported here so the module loads without redis-py."""
        if self._client is None:
            import redis  # local import: only needed when actually talking to Redis
            self._client = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD,
            )
        return self._client

    def ping(self):
        """Return True if Redis is reachable, False otherwise (never raises)."""
        try:
            return bool(self.r.ping())
        except Exception as e:
            self._on_error("ping", e)
            return False

    def _on_error(self, op, exc):
        if not self._logged_unavailable:
            log.warning("Redis unavailable (%s): %s — serving empty data", op, exc)
            self._logged_unavailable = True

    # -- low-level resilient helpers ------------------------------------------
    def _get(self, key):
        try:
            value = self.r.get(key)
            self._logged_unavailable = False
            return value
        except Exception as e:
            self._on_error("get", e)
            return None

    def _keys(self, pattern):
        try:
            keys = list(self.r.scan_iter(match=pattern))
            self._logged_unavailable = False
            return keys
        except Exception as e:
            self._on_error("scan", e)
            return []

    def _count(self, pattern):
        return len(self._keys(pattern))

    def _load(self, key):
        return serialization.loads(self._get(key))

    @staticmethod
    def _id(uri):
        return str(uri).split(":")[-1]

    # -- counts ----------------------------------------------------------------
    def getPlaylistCount(self):
        return self._count("playlist-index:*")

    def getSavedTrackCount(self):
        return self._count("track:*")

    def getArtistCount(self):
        return self._count("artist:*")

    def getAlbumCount(self):
        return self._count("album-index:*")

    def getNewReleasesCount(self):
        return self._count("nr-index:*")

    def getShowsCount(self):
        return self._count("show-index:*")

    # -- setters ---------------------------------------------------------------
    def setShow(self, show, episodes, index=-1):
        show_id = self._id(show.uri)
        self.r.set("show-uri:" + show_id, serialization.dumps(show))
        self.r.set("show-episodes:" + show_id, serialization.dumps(episodes))
        if index > -1:
            self.r.set("show-index:" + str(index), show_id)

    def setNewRelease(self, album, tracks, index=-1):
        album_id = self._id(album.uri)
        self.r.set("nr-uri:" + album_id, serialization.dumps(album))
        self.r.set("playlist-tracks:" + album_id, serialization.dumps(tracks))
        if index > -1:
            self.r.set("nr-index:" + str(index), album_id)

    def setAlbum(self, album, tracks, index=-1):
        album_id = self._id(album.uri)
        self.r.set("album-uri:" + album_id, serialization.dumps(album))
        self.r.set("playlist-tracks:" + album_id, serialization.dumps(tracks))
        if index > -1:
            self.r.set("album-index:" + str(index), album_id)

    def setPlaylist(self, playlist, tracks, index=-1):
        playlist_id = self._id(playlist.uri)
        self.r.set("playlist-uri:" + playlist_id, serialization.dumps(playlist))
        self.r.set("playlist-tracks:" + playlist_id, serialization.dumps(tracks))
        if index > -1:
            self.r.set("playlist-index:" + str(index), playlist_id)

    def setArtist(self, index, artist):
        self.r.set("artist:" + str(index), serialization.dumps(artist))

    def setSavedTrack(self, index, track):
        self.r.set("track:" + str(index), serialization.dumps(track))

    def setUserDevice(self, device):
        log.debug("storing device %s", device.id)
        self.r.set("device:" + str(device.id), serialization.dumps(device))

    # -- index getters ---------------------------------------------------------
    def getShow(self, index):
        show_id = self._get("show-index:" + str(index))
        if show_id is None:
            return None
        return self.getShowUri(show_id.decode("utf-8"))

    def getPlaylist(self, index):
        playlist_id = self._get("playlist-index:" + str(index))
        if playlist_id is None:
            return None
        return self.getPlaylistUri(playlist_id.decode("utf-8"))

    def getAlbum(self, index):
        album_id = self._get("album-index:" + str(index))
        if album_id is None:
            return None
        return self.getAlbumUri(album_id.decode("utf-8"))

    def getNewRelease(self, index):
        album_id = self._get("nr-index:" + str(index))
        if album_id is None:
            return None
        return self.getNewReleaseUri(album_id.decode("utf-8"))

    # -- uri getters -----------------------------------------------------------
    def getShowUri(self, uri):
        return self._load("show-uri:" + self._id(uri))

    def getPlaylistUri(self, uri):
        return self._load("playlist-uri:" + self._id(uri))

    def getAlbumUri(self, uri):
        return self._load("album-uri:" + self._id(uri))

    def getNewReleaseUri(self, uri):
        return self._load("nr-uri:" + self._id(uri))

    def getShowEpisodes(self, show_uri):
        return self._load("show-episodes:" + self._id(show_uri))

    def getPlaylistTracks(self, playlist_uri):
        return self._load("playlist-tracks:" + self._id(playlist_uri))

    def getArtist(self, index):
        return self._load("artist:" + str(index))

    def getSavedTrack(self, index):
        return self._load("track:" + str(index))

    def getSavedDevice(self, id):
        return self._getSavedItem("device:" + id)

    def _getSavedItem(self, key):
        return serialization.loads(self._get(key))

    # -- bulk listers ----------------------------------------------------------
    def _list(self, pattern):
        return [self._getSavedItem(key) for key in self._keys(pattern)]

    def getAllSavedDevices(self):
        return [item for item in self._list("device:*") if item is not None]

    def getAllSavedPlaylists(self):
        return [item for item in self._list("playlist-uri:*") if item is not None]

    def getAllSavedAlbums(self):
        return [item for item in self._list("album-uri:*") if item is not None]

    def getAllNewReleases(self):
        return [item for item in self._list("nr-uri:*") if item is not None]

    def getAllSavedShows(self):
        return [item for item in self._list("show-uri:*") if item is not None]

    # -- maintenance -----------------------------------------------------------
    def clearDevices(self):
        keys = self._keys("device:*")
        if keys:
            self.r.delete(*keys)

    def clear(self):
        """Remove only sPot's own keys (never flush the whole database)."""
        for prefix in config.REDIS_KEY_PREFIXES:
            keys = self._keys(prefix + "*")
            if keys:
                self.r.delete(*keys)
