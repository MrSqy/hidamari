import logging
import os
import random

try:
    from commons import normalize_video_path
except ModuleNotFoundError:
    from hidamari.commons import normalize_video_path

logger = logging.getLogger("Hidamari")


class VideoPlaylist:
    SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
    VALID_MODES = {"single", "sequential", "random"}

    def __init__(self, paths=None, folder=None, mode="single"):
        self.mode = mode if mode in self.VALID_MODES else "single"
        self.current_index = 0
        self.paths = self._load_paths(paths, folder)

    def _load_paths(self, paths, folder):
        candidates = []

        if folder:
            candidates.extend(self._load_folder(folder))

        if paths:
            if isinstance(paths, list):
                candidates.extend(paths)
            else:
                logger.warning("[Playlist] paths must be a list. Ignoring it.")

        unique_paths = []
        seen = set()
        for path in candidates:
            normalized = normalize_video_path(path)
            if not normalized:
                logger.warning(f"[Playlist] Path outside Hidamari folder or invalid, skipped: {path}")
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
        normalized_folder = normalize_video_path(folder)
        if not normalized_folder or not os.path.isdir(normalized_folder):
            logger.warning(f"[Playlist] Invalid or out-of-root playlist folder skipped: {folder}")
            return []

        filenames = sorted(os.listdir(normalized_folder), key=str.lower)
        return [os.path.join(normalized_folder, filename) for filename in filenames]

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
