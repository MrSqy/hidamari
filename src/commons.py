import os
import subprocess

LOGGER_NAME = "Hidamari"

PROJECT = "io.github.jeffshee.Hidamari"
DBUS_NAME_SERVER = f"{PROJECT}.server"
DBUS_NAME_PLAYER = f"{PROJECT}.player"

HOME = os.environ.get("HOME")
try:
    xdg_video_dir = subprocess.check_output(
        "xdg-user-dir VIDEOS", shell=True, encoding="UTF-8"
    ).replace("\n", "")
    VIDEO_WALLPAPER_DIR = os.path.join(xdg_video_dir, "Hidamari")
except FileNotFoundError:
    # xdg-user-dir not found, use $HOME/Hidamari for Video directory instead
    VIDEO_WALLPAPER_DIR = os.path.join(HOME, "Hidamari")


# Single source of truth for the video file types Hidamari recognises. Both the
# GUI file listing and the playlist loader import this instead of redefining it.
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}


# --- Local video sandbox ---------------------------------------------------
# Playback sources are restricted to the Hidamari video folder. These helpers
# resolve symlinks (realpath) *before* comparing against the folder root, so
# symlink escapes and ".." traversal are rejected regardless of whether the
# path comes from the GUI or a hand-edited config file. Keeping them in
# commons.py (which has no GTK/VLC imports) lets the pure-Python playlist layer
# enforce the same rule at its own load point.
def get_video_root():
    return os.path.realpath(VIDEO_WALLPAPER_DIR)


def is_path_inside_video_root(candidate):
    if not isinstance(candidate, str) or not candidate:
        return False
    root = get_video_root()
    resolved = os.path.realpath(os.path.expanduser(candidate))
    try:
        return os.path.commonpath([root, resolved]) == root
    except ValueError:
        # Different drive/mount or otherwise incomparable paths.
        return False


def normalize_video_path(candidate):
    """Resolve *candidate* and return it only if it stays inside the Hidamari
    video folder; otherwise return None."""
    if not isinstance(candidate, str) or not candidate:
        return None
    resolved = os.path.realpath(os.path.expanduser(candidate))
    if not is_path_inside_video_root(resolved):
        return None
    return resolved


xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config"))
AUTOSTART_DIR = os.path.join(xdg_config_home, "autostart")
AUTOSTART_DESKTOP_PATH = os.path.join(AUTOSTART_DIR, f"{PROJECT}.desktop")
AUTOSTART_DESKTOP_CONTENT = """[Desktop Entry]
Name=Hidamari
Exec=hidamari -b
Icon=io.github.jeffshee.Hidamari
Terminal=false
Type=Application
Categories=GTK;Utility;
StartupNotify=true
"""
AUTOSTART_DESKTOP_CONTENT_FLATPAK = """[Desktop Entry]
Name=Hidamari
Exec=/usr/bin/flatpak run --command=hidamari io.github.jeffshee.Hidamari -b
Icon=io.github.jeffshee.Hidamari
Terminal=false
Type=Application
Categories=GTK;Utility;
StartupNotify=true
X-Flatpak=io.github.jeffshee.Hidamari
"""

CONFIG_DIR = os.path.join(xdg_config_home, "hidamari")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

MODE_NULL = "MODE_NULL"
MODE_VIDEO = "MODE_VIDEO"
MODE_STREAM = "MODE_STREAM"
MODE_WEBPAGE = "MODE_WEBPAGE"

CONFIG_VERSION = 5
CONFIG_KEY_VERSION = "version"
CONFIG_KEY_MODE = "mode"
CONFIG_KEY_DATA_SOURCE = "data_source"
CONFIG_KEY_MUTE = "is_mute"
CONFIG_KEY_VOLUME = "audio_volume"
CONFIG_KEY_STATIC_WALLPAPER = "is_static_wallpaper"
CONFIG_KEY_BLUR_RADIUS = "static_wallpaper_blur_radius"
CONFIG_KEY_PAUSE_WHEN_MAXIMIZED = "is_pause_when_maximized"
CONFIG_KEY_MUTE_WHEN_MAXIMIZED = "is_mute_when_maximized"
CONFIG_KEY_FADE_DURATION_SEC = "fade_duration_sec"
CONFIG_KEY_FADE_INTERVAL = "fade_interval"
CONFIG_KEY_SYSTRAY = "is_show_systray"
CONFIG_KEY_FIRST_TIME = "is_first_time"
CONFIG_KEY_PLAYBACK_MODE = "playback_mode"
CONFIG_KEY_PLAYLIST_FOLDER = "playlist_folder"
CONFIG_KEY_PLAYLIST_PATHS = "playlist_paths"
CONFIG_KEY_CHANGE_ON_VIDEO_END = "change_on_video_end"
CONFIG_KEY_CHANGE_INTERVAL_MINUTES = "change_interval_minutes"
PLAYBACK_MODE_SINGLE = "single"
PLAYBACK_MODE_SEQUENTIAL = "sequential"
PLAYBACK_MODE_RANDOM = "random"
CONFIG_TEMPLATE = {
    CONFIG_KEY_VERSION: CONFIG_VERSION,
    CONFIG_KEY_MODE: MODE_NULL,
    CONFIG_KEY_DATA_SOURCE: None,
    CONFIG_KEY_MUTE: False,
    CONFIG_KEY_VOLUME: 50,
    CONFIG_KEY_STATIC_WALLPAPER: True,
    CONFIG_KEY_BLUR_RADIUS: 5,
    CONFIG_KEY_PAUSE_WHEN_MAXIMIZED: True,
    CONFIG_KEY_MUTE_WHEN_MAXIMIZED: False,
    CONFIG_KEY_FADE_DURATION_SEC: 1.5,
    CONFIG_KEY_FADE_INTERVAL: 0.1,
    CONFIG_KEY_SYSTRAY: False,
    CONFIG_KEY_FIRST_TIME: True,
    CONFIG_KEY_PLAYBACK_MODE: PLAYBACK_MODE_SINGLE,
    CONFIG_KEY_PLAYLIST_FOLDER: "",
    CONFIG_KEY_PLAYLIST_PATHS: [],
    CONFIG_KEY_CHANGE_ON_VIDEO_END: True,
    CONFIG_KEY_CHANGE_INTERVAL_MINUTES: 0,
}

try:
    from monitor import Monitor, Monitors, MonitorInfo
except ModuleNotFoundError:
    from hidamari.monitor import Monitor, Monitors, MonitorInfo

# initialize config according to monitors
info = MonitorInfo()
monitors = info.monitors()
data_sources = {}
# create an 
for monitor in monitors:
    data_sources[monitor['name']] = ""
data_sources['Default'] = ""

CONFIG_TEMPLATE[CONFIG_KEY_DATA_SOURCE] = data_sources
