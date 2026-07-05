import os
import sys
import types

# Make the source tree importable both as top-level modules (commons, playlist)
# and via the src/player package layout used at runtime.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "player"))

# commons.py imports `monitor` at module load, which pulls in GTK/gi and needs a
# running display. Stub it so the pure-Python playlist/sandbox logic can be
# tested headlessly (no GTK, no VLC, no display server).
if "monitor" not in sys.modules:
    monitor = types.ModuleType("monitor")

    class MonitorInfo:
        def monitors(self):
            return []

    class Monitor:
        ...

    class Monitors:
        ...

    monitor.MonitorInfo = MonitorInfo
    monitor.Monitor = Monitor
    monitor.Monitors = Monitors
    sys.modules["monitor"] = monitor
