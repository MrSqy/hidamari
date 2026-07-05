import sys
import glob
import time
import random
import ctypes
import logging
import pathlib
import subprocess
from threading import Timer

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, Gdk, GLib

import vlc
from pydbus import SessionBus
from PIL import Image, ImageFilter

try:
    import os
    sys.path.insert(1, os.path.join(sys.path[0], '..'))
    from player.base_player import BasePlayer
    from player.playlist import VideoPlaylist
    from menu import build_menu
    from commons import *
    from utils import ActiveHandler, ConfigUtil, is_gnome, is_wayland, is_nvidia_proprietary, is_vdpau_ok, is_flatpak
    from yt_utils import get_formats, get_best_audio, get_optimal_video
except ModuleNotFoundError:
    from hidamari.player.base_player import BasePlayer
    from hidamari.player.playlist import VideoPlaylist
    from hidamari.menu import build_menu
    from hidamari.commons import *
    from hidamari.utils import ActiveHandler, ConfigUtil, is_gnome, is_wayland, is_nvidia_proprietary, is_vdpau_ok, is_flatpak
    from hidamari.yt_utils import get_formats, get_best_audio, get_optimal_video

logger = logging.getLogger(LOGGER_NAME)

if is_wayland():
    # TODO: Window event monitoring for GNOME Wayland is broken
    class WindowHandler:
        def __init__(self, _: callable):
            pass
else:
    try:
        from utils import WindowHandler
    except ModuleNotFoundError:
        from hidamari.utils import WindowHandler


class Fade:
    def __init__(self):
        self.timer = None
        self.is_active = False

    def start(self, cur, target, step, fade_interval, update_callback: callable = None,
              complete_callback: callable = None):
        # Cancel any existing timer first
        self.cancel()
        self.is_active = True
        self._fade_step(cur, target, step, fade_interval, update_callback, complete_callback)

    def _fade_step(self, cur, target, step, fade_interval, update_callback, complete_callback):
        if not self.is_active:
            return
            
        new_cur = cur + step
        if (step < 0 and new_cur <= target) or (step > 0 and new_cur >= target):
            new_cur = target
            if update_callback:
                update_callback(int(new_cur))
            if complete_callback:
                complete_callback()
            self.is_active = False
        else:
            if update_callback:
                update_callback(int(new_cur))
            self.timer = Timer(fade_interval, self._fade_step,
                               args=[new_cur, target, step, fade_interval, update_callback, complete_callback])
            self.timer.daemon = True  # Make timer daemon to prevent blocking shutdown
            self.timer.start()

    def cancel(self):
        self.is_active = False
        if self.timer:
            self.timer.cancel()
            self.timer = None


class VLCWidget(Gtk.DrawingArea):
    """
    Simple VLC widget.
    Its player can be controlled through the 'player' attribute, which
    is a vlc.MediaPlayer() instance.
    """
    __gtype_name__ = "VLCWidget"

    def __init__(self, width, height):
        Gtk.DrawingArea.__init__(self)

        # Spawn a VLC instance and create a new media player to embed.
        # Some options need to be specified when instantiating VLC.
        # --no-disable-screensaver: Allow screensaver.
        vlc_options = ["--no-disable-screensaver"]
        self.instance = vlc.Instance(vlc_options)
        self.player = self.instance.media_player_new()

        def handle_embed(*args):
            self.player.set_xwindow(self.get_window().get_xid())
            return True

        # Embed and set size.
        self.connect("realize", handle_embed)
        self.set_size_request(width, height)

    def cleanup(self):
        """Cleanup VLC resources to prevent memory leaks"""
        try:
            if self.player:
                self.player.stop()
                self.player.release()
                self.player = None
            if self.instance:
                self.instance.release()
                self.instance = None
        except Exception as e:
            logger.warning(f"[VLCWidget] Cleanup error: {e}")


class PlayerWindow(Gtk.ApplicationWindow):
    def __init__(self, name, width, height, *args, **kwargs):
        super(PlayerWindow, self).__init__(*args, **kwargs)
        # Setup a VLC widget given the provided width and height.
        self.width = width
        self.height = height
        self.name = name
        self.__vlc_widget = VLCWidget(width, height)
        self.add(self.__vlc_widget)
        self.__vlc_widget.show()

        # These are to allow us to right click. VLC can't hijack mouse input, and probably not key inputs either in
        # Case we want to add keyboard shortcuts later on.
        self.__vlc_widget.player.video_set_mouse_input(False)
        self.__vlc_widget.player.video_set_key_input(False)

        # A timer that handling fade-in/out
        self.fade = Fade()

        self._media_events_attached = False
        self.menu = None
        self.connect("button-press-event", self._on_button_press_event)

    def play(self):
        self.__vlc_widget.player.play()

    def play_fade(self, target, fade_duration_sec, fade_interval):
        self.play()
        cur = 0
        step = (target - cur) / (fade_duration_sec / fade_interval)
        self.fade.cancel()
        self.fade.start(cur=cur, target=target, step=step,
                        fade_interval=fade_interval, update_callback=self.set_volume)

    def is_playing(self):
        return self.__vlc_widget.player.is_playing()

    def pause(self):
        if self.is_playing():
            self.__vlc_widget.player.pause()

    def pause_fade(self, fade_duration_sec, fade_interval):
        cur = self.get_volume()
        target = 0
        step = (target - cur) / (fade_duration_sec / fade_interval)
        self.fade.cancel()
        self.fade.start(cur=cur, target=target, step=step, fade_interval=fade_interval, update_callback=self.set_volume,
                        complete_callback=self.pause)

    def volume_fade(self, target, fade_duration_sec, fade_interval):
        cur = self.get_volume()
        step = (target - cur) / (fade_duration_sec / fade_interval)
        self.fade.cancel()
        self.fade.start(cur=cur, target=target, step=step, fade_interval=fade_interval, update_callback=self.set_volume)

    def media_new(self, *args):
        return self.__vlc_widget.instance.media_new(*args)

    def set_media(self, *args):
        self.__vlc_widget.player.set_media(*args)

    def attach_media_events(self, on_end_reached, on_error):
        if self._media_events_attached:
            return
        event_manager = self.__vlc_widget.player.event_manager()
        event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, on_end_reached)
        event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, on_error)
        self._media_events_attached = True

    def set_volume(self, *args):
        self.__vlc_widget.player.audio_set_volume(*args)

    def get_volume(self):
        return self.__vlc_widget.player.audio_get_volume()

    def set_mute(self, is_mute):
        return self.__vlc_widget.player.audio_set_mute(is_mute)

    def get_position(self):
        return self.__vlc_widget.player.get_position()

    def set_position(self, *args):
        self.__vlc_widget.player.set_position(*args)

    def snapshot(self, *args):
        return self.__vlc_widget.player.video_take_snapshot(*args)

    def centercrop(self, video_width=None, video_height=None):
        # Getting dimension from libvlc is not reliable enough (need to consider timing)
        if (video_width, video_height) == (None, None):
            video_width, video_height = self.__vlc_widget.player.video_get_size()
            if video_width == 0 or video_height == 0:
                logger.warning("[CenterCrop] video_get_size is not ready yet")
                return
        logger.debug(f"[CenterCrop] Dimension {video_width}x{video_height}")
        window_ratio = self.width / self.height
        video_ratio = video_width / video_height
        if window_ratio == video_ratio:
            return
        elif video_ratio < window_ratio:
            # If window is wider than video
            # For example video ratio (4:3)=1.33..., window ratio (16:9)=1.77...
            crop_height = video_width / window_ratio
            top_offset = (video_height - crop_height) / 2
            crop_geometry = f"{int(video_width)}x{int(crop_height+top_offset)}+0+{int(top_offset)}"

        else:
            # If video is wider than window
            crop_width = video_height * window_ratio
            left_offset = (video_width - crop_width) / 2
            crop_geometry = f"{int(crop_width+left_offset)}x{int(video_height)}+{int(left_offset)}+0"

        # Crop geometry WxH+L+T: Width x Height + Left Offset + top Offset
        logger.debug(f"[CenterCrop] Crop geometry: {crop_geometry}")
        self.__vlc_widget.player.video_set_crop_geometry(crop_geometry)

    def add_audio_track(self, audio):
        self.__vlc_widget.player.add_slave(vlc.MediaSlaveType(1), audio, True)

    def _on_button_press_event(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            if not self.menu:
                self.menu = build_menu(MODE_VIDEO)
            self.menu.popup_at_pointer()
            return True
        return False

    def get_name(self):
        return self.name

    def cleanup(self):
        """Cleanup resources to prevent memory leaks"""
        self.fade.cancel()
        if self.__vlc_widget:
            self.__vlc_widget.cleanup()


class VideoPlayer(BasePlayer):
    """
    <node>
    <interface name='io.github.jeffshee.hidamari.player'>
        <property name="mode" type="s" access="read"/>
        <property name="data_source" type="s" access="readwrite"/>
        <property name="volume" type="i" access="readwrite"/>
        <property name="is_mute" type="b" access="readwrite"/>
        <property name="is_playing" type="b" access="read"/>
        <property name="is_paused_by_user" type="b" access="readwrite"/>
        <method name='reload_config'/>
        <method name='pause_playback'/>
        <method name='start_playback'/>
        <method name='quit_player'/>
    </interface>
    </node>
    """

    def __init__(self, *args, **kwargs):
        super(VideoPlayer, self).__init__(*args, **kwargs)

        # We need to initialize X11 threads so we can use hardware decoding.
        # `libX11.so.6` fix for Fedora 33
        x11 = None
        if is_wayland() and is_nvidia_proprietary() and not is_vdpau_ok():
            logger.warning(
                "Proprietary Nvidia driver detected! HW Acceleration is not yet working in Wayland.")
        else:
            for lib in ["libX11.so", "libX11.so.6"]:
                try:
                    x11 = ctypes.cdll.LoadLibrary(lib)
                except OSError:
                    pass
                if x11 is not None:
                    x11.XInitThreads()
                    break

        self.playlist = None
        self.current_playlist_source = None
        self.playlist_error_count = 0
        self.config = None
        self.reload_config()

        # Static wallpaper (currently for GNOME only)
        if is_gnome():
            self.original_wallpaper_uri = None
            self.original_wallpaper_uri_dark = None
            if is_flatpak():
                try:
                    self.original_wallpaper_uri = subprocess.check_output(
                        "flatpak-spawn --host gsettings get org.gnome.desktop.background picture-uri", shell=True, encoding='UTF-8')
                    self.original_wallpaper_uri_dark = subprocess.check_output(
                        "flatpak-spawn --host gsettings get org.gnome.desktop.background picture-uri-dark", shell=True, encoding='UTF-8')
                except subprocess.CalledProcessError as e:
                    logger.error(f"[StaticWallpaper] {e}")
            else:
                gso = Gio.Settings.new("org.gnome.desktop.background")
                self.original_wallpaper_uri = gso.get_string("picture-uri")
                self.original_wallpaper_uri_dark = gso.get_string(
                    "picture-uri-dark")

        # Handler should be created after everything initialized
        self.active_handler, self.window_handler = None, None
        self.is_any_maximized, self.is_any_fullscreen = False, False
        self.is_paused_by_user = False

    def new_window(self, gdk_monitor):
        rect = gdk_monitor.get_geometry()
        return PlayerWindow(gdk_monitor.get_model(), rect.width, rect.height, application=self)

    def do_activate(self):
        super().do_activate()
        self.data_source = self.config[CONFIG_KEY_DATA_SOURCE]

    def _on_monitor_added(self, _, gdk_monitor, *args):
        super()._on_monitor_added(_, gdk_monitor, *args)
        self.monitor_sync()

    def _on_active_changed(self, active):
        if active:
            self.pause_playback()
        else:
            if self._should_playback_start():
                self.start_playback()
            else:
                self.pause_playback()

    def _on_window_state_changed(self, state):
        self.is_any_maximized, self.is_any_fullscreen = state["is_any_maximized"], state["is_any_fullscreen"]
        logger.info(f"is_any_maximized: {self.is_any_maximized}, is_any_fullscreen: {self.is_any_fullscreen}")

        if self.config[CONFIG_KEY_PAUSE_WHEN_MAXIMIZED]:
            if self._should_playback_start():
                self.start_playback()
            else:
                self.pause_playback()
        elif self.config[CONFIG_KEY_MUTE_WHEN_MAXIMIZED]:
            for monitor, window in self.windows.items():
                if not monitor.is_primary():
                    continue
                if self.is_any_fullscreen or self.is_any_maximized:
                    window.volume_fade(target=0, fade_duration_sec=self.config[CONFIG_KEY_FADE_DURATION_SEC],
                                fade_interval=self.config[CONFIG_KEY_FADE_INTERVAL])
                else:
                    window.volume_fade(target=self.volume, fade_duration_sec=self.config[CONFIG_KEY_FADE_DURATION_SEC],
                                fade_interval=self.config[CONFIG_KEY_FADE_INTERVAL])
        
    def _should_playback_start(self):
        if self.config[CONFIG_KEY_PAUSE_WHEN_MAXIMIZED] and (self.is_any_maximized or self.is_any_fullscreen):
            return False
        if self.is_paused_by_user:
            return False
        return True

    def _playlist_mode(self):
        return self.config.get(CONFIG_KEY_PLAYBACK_MODE, PLAYBACK_MODE_SINGLE)

    def _is_playlist_mode(self):
        return self._playlist_mode() in [PLAYBACK_MODE_SEQUENTIAL, PLAYBACK_MODE_RANDOM]

    def _setup_playlist(self):
        self.playlist = None
        self.current_playlist_source = None
        self.playlist_error_count = 0

        if not self._is_playlist_mode():
            return False

        playlist_paths = self.config.get(CONFIG_KEY_PLAYLIST_PATHS, [])
        if not isinstance(playlist_paths, list):
            logger.warning("[Playlist] playlist_paths must be a list. Ignoring it.")
            playlist_paths = []

        playlist_folder = self.config.get(CONFIG_KEY_PLAYLIST_FOLDER, "")
        if not isinstance(playlist_folder, str):
            logger.warning("[Playlist] playlist_folder must be a string. Ignoring it.")
            playlist_folder = ""

        self.playlist = VideoPlaylist(
            paths=playlist_paths,
            folder=playlist_folder,
            mode=self._playlist_mode()
        )
        logger.info(f"[Playlist] Created playlist with {len(self.playlist)} video(s)")

        if self.playlist.is_empty():
            logger.warning("[Playlist] Playlist is empty. Falling back to single video mode.")
            self.playlist = None
            return False

        self.current_playlist_source = self.playlist.get_current()
        logger.info(f"[Playlist] Initial video: {self.current_playlist_source}")
        return True

    @staticmethod
    def _normalize_data_source(data_source):
        if isinstance(data_source, dict):
            data_source.setdefault('Default', '')
            return data_source
        return {'Default': data_source or ''}

    @staticmethod
    def _source_for_monitor(data_source, monitor):
        monitor_name = monitor.get_model()
        source = data_source.get(monitor_name, '')
        if source:
            return source, monitor_name
        return data_source.get('Default', ''), 'Default'

    def _probe_video_dimensions(self, source):
        if not source:
            return None, None
        try:
            dimension = subprocess.check_output([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height', '-of',
                'csv=s=x:p=0', source
                ], shell=False, encoding='UTF-8').replace('\n', '')
            width, height = dimension.split("x")
            return int(width), int(height)
        except (subprocess.CalledProcessError, ValueError, OSError) as e:
            logger.warning(f"[Video] Unable to probe dimensions for {source}: {e}")
            return None, None

    def _set_window_video_source(self, monitor, window, source, video_width=None, video_height=None, repeat=True):
        if not source:
            logger.warning(f"[Video] Empty source for {monitor.get_model()}. Skipping media update.")
            return False

        logger.info(f"Setting source {source} to {monitor.get_model()}")
        media = window.media_new(source)
        if repeat:
            """
            This loops the media itself. Using -R / --repeat and/or -L / --loop don't seem to work. However,
            based on reading, this probably only repeats 65535 times, which is still a lot of time, but might
            cause the program to stop playback if it's left on for a very long time.
            """
            media.add_option("input-repeat=65535")
        # Prevent awful ear-rape with multiple instances.
        if not monitor.is_primary():
            media.add_option("no-audio")
        window.set_media(media)
        window.set_position(0.0)
        window.centercrop(video_width, video_height)
        return True

    def _set_single_video_sources(self, data_source):
        video_width, video_height = {}, {}
        for monitor_name, video in data_source.items():
            source = video or data_source.get('Default', '')
            video_width[monitor_name], video_height[monitor_name] = self._probe_video_dimensions(source)

        for monitor, window in self.windows.items():
            source, source_key = self._source_for_monitor(data_source, monitor)
            self._set_window_video_source(
                monitor, window, source,
                video_width.get(source_key), video_height.get(source_key),
                repeat=True
            )

    def _set_playlist_video_source(self, source):
        if not source:
            logger.warning("[Playlist] Empty playlist source. Skipping media update.")
            return False

        video_width, video_height = self._probe_video_dimensions(source)
        is_applied = False
        for monitor, window in self.windows.items():
            is_applied = self._set_window_video_source(
                monitor, window, source, video_width, video_height, repeat=False
            ) or is_applied

        if is_applied:
            self.current_playlist_source = source
            logger.info(f"[Playlist] Switched to video: {source}")
        return is_applied

    def _attach_playlist_events(self):
        if not self.config.get(CONFIG_KEY_CHANGE_ON_VIDEO_END, True):
            return

        controller_window = None
        for monitor, window in self.windows.items():
            if monitor.is_primary():
                controller_window = window
                break
        if controller_window is None and self.windows:
            controller_window = next(iter(self.windows.values()))

        if controller_window:
            controller_window.attach_media_events(
                self._on_playlist_end_reached,
                self._on_playlist_error
            )

    def _on_playlist_end_reached(self, *_):
        GLib.idle_add(self._advance_playlist, False, None)

    def _on_playlist_error(self, *_):
        failed_source = self.current_playlist_source
        logger.warning(f"[Playlist] VLC encountered an error for: {failed_source}")
        GLib.idle_add(self._advance_playlist, True, failed_source)

    def _advance_playlist(self, is_error=False, failed_source=None):
        if not self.playlist or self.playlist.is_empty():
            return False
        if not self.config.get(CONFIG_KEY_CHANGE_ON_VIDEO_END, True):
            return False

        if is_error:
            if failed_source:
                logger.warning(f"[Playlist] Skipping failed video: {failed_source}")
            self.playlist_error_count += 1
            if self.playlist_error_count >= len(self.playlist):
                logger.error("[Playlist] All playlist videos failed. Stopping playlist advance.")
                return False
        else:
            self.playlist_error_count = 0

        next_source = self.playlist.next()
        if not next_source:
            logger.warning("[Playlist] No next video available.")
            return False

        logger.info(f"[Playlist] Advancing to next video: {next_source}")
        if self._set_playlist_video_source(next_source):
            self.volume = self.config[CONFIG_KEY_VOLUME]
            self.is_mute = self.config[CONFIG_KEY_MUTE]
            self.start_playback()
        return False

    def _current_video_source(self):
        if self.playlist and not self.playlist.is_empty():
            return self.playlist.get_current()
        data_source = self._normalize_data_source(self.data_source)
        return data_source.get('Default', '')

    @property
    def mode(self):
        return self.config[CONFIG_KEY_MODE]

    @property
    def data_source(self):
        return self.config[CONFIG_KEY_DATA_SOURCE]

    @data_source.setter
    def data_source(self, data_source):
        data_source = self._normalize_data_source(data_source)
        self.config[CONFIG_KEY_DATA_SOURCE] = data_source

        if self.mode == MODE_VIDEO:
            if self._setup_playlist():
                self._set_playlist_video_source(self.playlist.get_current())
                self._attach_playlist_events()
            else:
                self._set_single_video_sources(data_source)

        elif self.mode == MODE_STREAM:
            source = data_source['Default']
            formats = get_formats(source)
            max_height = max(
                self.windows, key=lambda m: m.get_geometry().height).get_geometry().height
            video_url, video_width, video_height = get_optimal_video(
                formats, max_height)
            audio_url = get_best_audio(formats)

            for monitor, window in self.windows.items():
                media = window.media_new(video_url)
                media.add_option("input-repeat=65535")
                window.set_media(media)
                if monitor.is_primary():
                    window.add_audio_track(audio_url)
                else:
                    # `get_optimal_video` now might return video with audio.
                    media.add_option("no-audio")
                window.set_position(0.0)
                window.centercrop(video_width, video_height)
        else:
            raise ValueError("Invalid mode")

        self.volume = self.config[CONFIG_KEY_VOLUME]
        self.is_mute = self.config[CONFIG_KEY_MUTE]
        self.start_playback()

        # Everything is initialized. Create handlers if haven't (singleton pattern).
        if not self.active_handler:
            self.active_handler = ActiveHandler(self._on_active_changed)
        if not self.window_handler and not is_wayland():
            # Only create WindowHandler on X11, not Wayland
            self.window_handler = WindowHandler(self._on_window_state_changed)

        if self.config[CONFIG_KEY_STATIC_WALLPAPER] and self.mode == MODE_VIDEO:
            self.set_static_wallpaper()
        else:
            self.set_original_wallpaper()

    @property
    def volume(self):
        return self.config[CONFIG_KEY_VOLUME]

    @volume.setter
    def volume(self, volume):
        self.config[CONFIG_KEY_VOLUME] = volume
        for monitor in self.windows:
            if monitor.is_primary():
                self.windows[monitor].set_volume(volume)

    @property
    def is_mute(self):
        return self.config[CONFIG_KEY_MUTE]

    @is_mute.setter
    def is_mute(self, is_mute):
        self.config[CONFIG_KEY_MUTE] = is_mute
        for monitor, window in self.windows.items():
            if monitor.is_primary():
                window.set_mute(is_mute)

    @property
    def is_playing(self):
        return not self.is_paused_by_user

    def pause_playback(self):
        for monitor, window in self.windows.items():
            window.pause_fade(fade_duration_sec=self.config[CONFIG_KEY_FADE_DURATION_SEC],
                              fade_interval=self.config[CONFIG_KEY_FADE_INTERVAL])

    def start_playback(self):
        if self._should_playback_start():
            for monitor, window in self.windows.items():
                window.play_fade(target=self.volume, fade_duration_sec=self.config[CONFIG_KEY_FADE_DURATION_SEC],
                            fade_interval=self.config[CONFIG_KEY_FADE_INTERVAL])

    def monitor_sync(self):
        primary_monitor = None
        for monitor, window in self.windows.items():
            if monitor.is_primary:
                primary_monitor = monitor
                break
        if primary_monitor:
            for monitor, window in self.windows.items():
                if monitor == primary_monitor:
                    continue
                # `set_position()` method require the playback to be enabled before calling
                window.play()
                window.set_position(
                    self.windows[primary_monitor].get_position())
                window.play() if self.windows[primary_monitor].is_playing(
                ) else window.pause()

    def set_static_wallpaper(self):
        # Currently for GNOME only
        if not is_gnome():
            return
        source = self._current_video_source()
        if not source:
            logger.warning("[StaticWallpaper] No video source available")
            return
        # Get the duration of the video
        try:
            duration = float(subprocess.check_output([
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', source
            ], shell = False))
        except subprocess.CalledProcessError:
            duration = 0
        # Find the golden ratio
        ss = time.strftime('%H:%M:%S', time.gmtime(duration / 3.14))
        # Extract the frame
        static_wallpaper_path = os.path.join(
            CONFIG_DIR, "static-{:06d}.png".format(random.randint(0, 999999)))
        ret = subprocess.run([
            'ffmpeg', '-y', '-ss', ss, '-i', source,
            '-vframes', '1', static_wallpaper_path
        ], shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if ret.returncode == 0 and os.path.isfile(static_wallpaper_path):
            blur_wallpaper = Image.open(static_wallpaper_path)
            blur_wallpaper = blur_wallpaper.filter(
                ImageFilter.GaussianBlur(self.config["static_wallpaper_blur_radius"]))
            blur_wallpaper.save(static_wallpaper_path)
            static_wallpaper_uri = pathlib.Path(
                static_wallpaper_path).resolve().as_uri()
            if is_flatpak():
                try:
                    subprocess.run(
                        ['flatpak-spawn', '--host', 'gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri', static_wallpaper_uri], shell=False)
                    subprocess.run(
                        ['flatpak-spawn', '--host', 'gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri-dark', static_wallpaper_uri], shell=False)
                except subprocess.CalledProcessError as e:
                    logger.error(f"[StaticWallpaper] {e}")
            else:
                gso = Gio.Settings.new("org.gnome.desktop.background")
                gso.set_string("picture-uri", static_wallpaper_uri)
                gso.set_string("picture-uri-dark", static_wallpaper_uri)

    def set_original_wallpaper(self):
        # Currently for GNOME only
        if not is_gnome():
            return
        if is_flatpak():
            try:
                if self.original_wallpaper_uri is not None:
                    subprocess.run(
                        ['flatpak-spawn', '--host', 'gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri', self.original_wallpaper_uri], shell=False)
                if self.original_wallpaper_uri_dark is not None:
                    subprocess.run(
                        ['flatpak-spawn', '--host', 'gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri-dark', self.original_wallpaper_uri], shell=False)
            except subprocess.CalledProcessError as e:
                logger.error(f"[StaticWallpaper] {e}")
        else:
            gso = Gio.Settings.new("org.gnome.desktop.background")
            gso.set_string("picture-uri", self.original_wallpaper_uri)
            gso.set_string("picture-uri-dark",
                           self.original_wallpaper_uri_dark)
        # Purge the generated static wallpaper (and leftover if any)
        for f in glob.glob(os.path.join(CONFIG_DIR, "static-*.png")):
            os.remove(f)

    def reload_config(self):
        self.config = ConfigUtil().load()

    def quit_player(self):
        self.set_original_wallpaper()
        
        # Cleanup handlers
        if self.active_handler:
            self.active_handler.cleanup()
            self.active_handler = None
            
        if self.window_handler:
            self.window_handler.cleanup()
            self.window_handler = None
        
        # Cleanup all windows
        for monitor, window in self.windows.items():
            if window:
                window.cleanup()
        
        super().quit_player()


def main():
    bus = SessionBus()
    app = VideoPlayer()
    try:
        bus.publish(DBUS_NAME_PLAYER, app)
    except RuntimeError as e:
        logger.error(e)
    app.run(sys.argv)


if __name__ == "__main__":
    main()
