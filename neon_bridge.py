import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from pupil_labs.realtime_api.simple import Device, discover_one_device

HOST = "0.0.0.0"
PORT = 8765
USE_DISCOVERY = True
NEON_IP = "192.168.1.50"  # ignored if USE_DISCOVERY=True
NEON_PORT = 8080
OFFSET_REFRESH_SEC = 5.0
DISCOVERY_TIMEOUT_SEC = 10.0

device = None
device_lock = threading.Lock()

offset_lock = threading.Lock()
host_minus_companion_ns = 0
offset_std_ms = 0.0
offset_last_updated_ns = 0


def connect_device():
    global device
    if USE_DISCOVERY:
        d = discover_one_device(max_search_duration_seconds=DISCOVERY_TIMEOUT_SEC)
        if d is None:
            raise RuntimeError("No Neon device found on the network.")
        device = d
    else:
        device = Device(address=NEON_IP, port=NEON_PORT)
    print(f"Connected to {device.address}:{device.port}")


def refresh_offset():
    global host_minus_companion_ns, offset_std_ms, offset_last_updated_ns
    with device_lock:
        est = device.estimate_time_offset()
    mean_ms = float(est.time_offset_ms.mean)
    std_ms = float(getattr(est.time_offset_ms, "std", 0.0))
    with offset_lock:
        host_minus_companion_ns = int(round(mean_ms * 1_000_000))
        offset_std_ms = std_ms
        offset_last_updated_ns = time.time_ns()


def offset_loop():
    while True:
        try:
            refresh_offset()
        except Exception as e:
            print(f"[offset] refresh failed: {e}")
        time.sleep(OFFSET_REFRESH_SEC)


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
                "offset_last_updated_ns": upd
            })
            return

        if path == "/status":
            with offset_lock:
                self._send_json({
                    "ok": True,
                    "host_minus_companion_ns": host_minus_companion_ns,
                    "offset_std_ms": offset_std_ms,
                    "offset_last_updated_ns": offset_last_updated_ns
                })
            return

        self._send_json({"ok": False, "error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/recording/start":
            try:
                with device_lock:
                    recording_id = device.recording_start()
                self._send_json({"ok": True, "recording_id": recording_id})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if path == "/recording/stop_and_save":
            try:
                with device_lock:
                    device.recording_stop_and_save()
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if path == "/event":
            try:
                body = self._read_json()
                name = str(body["name"])
                ts_ns = int(body["companion_timestamp_ns"])

                with device_lock:
                    event = device.send_event(name, event_timestamp_unix_ns=ts_ns)

                self._send_json({
                    "ok": True,
                    "event_name": event.name,
                    "event_timestamp_unix_ns": int(event.timestamp_unix_ns),
                    "recording_id": getattr(event, "recording_id", None)
                })
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        self._send_json({"ok": False, "error": "Not found"}, 404)


def main():
    connect_device()
    refresh_offset()
    threading.Thread(target=offset_loop, daemon=True).start()

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Bridge running on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()