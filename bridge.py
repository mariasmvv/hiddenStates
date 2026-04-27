"""
Rustbucket VR — Pupil Labs Bridge
=================================
Run on the laptop BEFORE starting the Unity game.

    pip install pupil-labs-realtime-api
    python bridge.py

What it does:
  1. Connects to Pupil Companion
  2. Estimates laptop↔Companion clock offset
  3. Serves:
       GET  /sync
       GET  /status
       POST /event
"""

import json
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from pupil_labs.realtime_api.simple import Device

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8765

PUPIL_DEVICE_IP = "192.168.137.249"   # <-- set this if needed
PUPIL_DEVICE_PORT = 8080

OFFSET_REFRESH_SEC = 10.0

device = None
device_lock = threading.Lock()

offset_lock = threading.Lock()
host_minus_companion_ns = 0
offset_std_ms = None
offset_last_updated_ns = 0


# ──────────────────────────────────────────────
# Pupil connection / offset refresh
# ──────────────────────────────────────────────
def connect_device():
    global device
    try:
        device = Device(address=PUPIL_DEVICE_IP, port=PUPIL_DEVICE_PORT)
        print(f"Connected to Pupil device at {PUPIL_DEVICE_IP}:{PUPIL_DEVICE_PORT}")
    except Exception as e:
        sys.exit(f"Could not connect to Pupil device: {e}")


def refresh_offset():
    global host_minus_companion_ns, offset_std_ms, offset_last_updated_ns

    try:
        with device_lock:
            estimate = device.estimate_time_offset()

        if estimate is None:
            print("[warn] No time-offset estimate returned.")
            return

        # host_minus_companion_ns: add to companion time -> host time
        mean_ms = float(estimate.time_offset_ms.mean)
        std_ms = float(estimate.time_offset_ms.std)

        with offset_lock:
            host_minus_companion_ns = int(mean_ms * 1_000_000)
            offset_std_ms = std_ms
            offset_last_updated_ns = time.time_ns()

        print(
            f"[offset] host-companion = {mean_ms:.2f} ms "
            f"(std={std_ms:.2f} ms)"
        )

    except Exception as e:
        print(f"[warn] Failed to refresh offset: {e}")


def offset_loop():
    while True:
        refresh_offset()
        time.sleep(OFFSET_REFRESH_SEC)


# ──────────────────────────────────────────────
# HTTP handler
# ──────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send_json(self, obj, code=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/sync":
            t_recv = time.time_ns()
            with offset_lock:
                hmcn = host_minus_companion_ns
                std = offset_std_ms
                upd = offset_last_updated_ns
            t_send = time.time_ns()

            self._send_json({
                "ok": True,
                "server_receive_ns": t_recv,
                "server_send_ns": t_send,
                "host_minus_companion_ns": hmcn,
                "offset_std_ms": std,
                "offset_last_updated_ns": upd,
            })
            return

        if path == "/status":
            with offset_lock:
                self._send_json({
                    "ok": True,
                    "host_minus_companion_ns": host_minus_companion_ns,
                    "offset_std_ms": offset_std_ms,
                    "offset_last_updated_ns": offset_last_updated_ns,
                })
            return

        self._send_json({"ok": False, "error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/event":
            try:
                body = self._read_json()
                name = str(body["name"])
                ts_ns = int(body["companion_timestamp_ns"])

                with device_lock:
                    event = device.send_event(name, event_timestamp_unix_ns=ts_ns)

                print(f"[event] {name[:120]}")
                self._send_json({
                    "ok": True,
                    "event_name": event.name,
                    "event_timestamp_unix_ns": int(event.timestamp_unix_ns),
                    "recording_id": getattr(event, "recording_id", None),
                })
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        self._send_json({"ok": False, "error": "Not found"}, 404)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    connect_device()
    refresh_offset()
    threading.Thread(target=offset_loop, daemon=True).start()

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Bridge running on http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping bridge...")
    finally:
        server.shutdown()
        if device is not None:
            with device_lock:
                try:
                    device.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()