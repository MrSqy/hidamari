import logging
import os
import random

logger = logging.getLogger("Hidamari")

# Display-duration bounds (seconds) for playlist videos. 0 is a valid value
# meaning "play the video to its natural end". Single source of truth so the
# GUI spin button and the player clamp agree.
INTERVAL_MIN_SEC = 0
INTERVAL_MAX_SEC = 3600


def _clamp_interval(value, fallback):
    """Coerce *value* to an int within [INTERVAL_MIN_SEC, INTERVAL_MAX_SEC];
    return *fallback* if it is not a usable number."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return fallback
    if seconds < INTERVAL_MIN_SEC:
        return fallback
    return min(seconds, INTERVAL_MAX_SEC)


def effective_interval(path, default_sec, overrides):
    """Return the display duration in seconds for *path*.

    Uses the per-video override when one exists for *path* (0 = play to end),
    otherwise the default. Values are clamped to [0, INTERVAL_MAX_SEC]; invalid
    input falls back (a bad override to the default, a bad default to 0 = end).
    Override keys are matched by realpath so they line up with the playlist's
    resolved paths even if the caller passes a non-canonical path.
    """
    default_sec = _clamp_interval(default_sec, INTERVAL_MIN_SEC)
    if not isinstance(overrides, dict) or not isinstance(path, str) or not path:
        return default_sec

    if path in overrides:
        return _clamp_interval(overrides[path], default_sec)
    try:
        resolved = os.path.realpath(os.path.expanduser(path))
    except (TypeError, ValueError):
        resolved = None
    if resolved is not None and resolved in overrides:
        return _clamp_interval(overrides[resolved], default_sec)
    return default_sec


class VideoPlaylist:
    SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
    VALID_MODES = {"single", "sequential", "random"}

    def __init__(self, paths=None, folder=None, mode="single"):
        self.mode = mode if mode in self.VALID_MODES else "single"
        self.current_index = 0
        self.paths = self._load_paths(paths, folder)

    def _load_paths(self, paths, folder):
        candidates = []

        if paths:
            if isinstance(paths, list):
                candidates.extend(paths)
            else:
                logger.warning("[Playlist] paths must be a list. Ignoring it.")

        if folder:
            candidates.extend(self._load_folder(folder))

        unique_paths = []
        seen = set()
        for path in candidates:
            normalized = self._normalize_path(path)
            if not normalized:
                continue
            if normalized in seen:
                continue
            if not self._is_valid_video(normalized):
                logger.warning(f"[Playlist] Invalid video path skipped: {path}")
                continue
            seen.add(normalized)
            unique_paths.append(normalized)

        return unique_paths

    def _load_folder(self, folder):
        normalized_folder = self._normalize_path(folder)
        if not normalized_folder or not os.path.isdir(normalized_folder):
            logger.warning(f"[Playlist] Invalid playlist folder skipped: {folder}")
            return []

        filenames = sorted(os.listdir(normalized_folder), key=str.lower)
        return [os.path.join(normalized_folder, filename) for filename in filenames]

    @staticmethod
    def _normalize_path(path):
        if not isinstance(path, str) or not path:
            return None
        return os.path.abspath(os.path.expanduser(path))

    def _is_valid_video(self, path):
        _, ext = os.path.splitext(path)
        return os.path.isfile(path) and ext.lower() in self.SUPPORTED_EXTENSIONS

    def is_empty(self):
        return len(self.paths) == 0

    def get_current(self):
        if self.is_empty():
            return None
        return self.paths[self.current_index]

    def next(self):
        if self.is_empty():
            return None

        if self.mode == "random":
            self.current_index = self._next_random_index()
        elif self.mode == "sequential":
            self.current_index = (self.current_index + 1) % len(self.paths)

        return self.get_current()

    def previous(self):
        if self.is_empty():
            return None

        if self.mode == "random":
            self.current_index = self._next_random_index()
        elif self.mode == "sequential":
            self.current_index = (self.current_index - 1) % len(self.paths)

        return self.get_current()

    def _next_random_index(self):
        if len(self.paths) <= 1:
            return self.current_index

        choices = list(range(len(self.paths)))
        choices.remove(self.current_index)
        return random.choice(choices)

    def __len__(self):
        return len(self.paths)
