"""
Rustbucket VR — Pupil Labs Bridge
===================================
Run on the laptop BEFORE starting the Unity game.

    pip install pupil-labs-realtime-api pandas opencv-python
    python bridge.py

What it does:
  1. Connects to Pupil Companion on the phone
  2. Calculates the clock offset (Quest time → Companion time)
  3. Serves a tiny HTTP server the Quest talks to:
       GET  /sync   → returns offset so Unity can correct its timestamps
       POST /event  → receives a game event, injects it into the recording
  4. After the session, merges game CSVs with gaze export and annotates
     the eye video with event markers.

Requirements:
  - Pupil Companion app open and streaming on the phone
  - Phone and laptop on the same Wi-Fi
  - Unity Quest talking to this laptop's IP on port 8765
"""

import json
import time
import threading
import csv
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

import pandas as pd
import cv2

from pupil_labs.realtime_api.simple import Device

# ──────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────
PORT = 8765
OUTPUT_DIR = "session_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ──────────────────────────────────────────────
#  Step 1 — Connect to Pupil Companion & sync
# ──────────────────────────────────────────────
device = Device(address="192.168.137.249", port=8080)

print("Calculating time offset...")
estimate = device.estimate_time_offset()
if estimate is None:
    device.close()
    sys.exit("Pupil Companion app is too old — please update it.")

# host_minus_companion_ns: add this to companion time to get host (laptop) time
# We want companion_ns = host_ns - host_minus_companion_ns
host_minus_companion_ns = int(estimate.time_offset_ms.mean * 1_000_000)
print(f"  Offset (host - companion): {host_minus_companion_ns / 1e6:.3f} ms")
print(f"  Roundtrip: {estimate.roundtrip_duration_ms.mean:.3f} ms")

# ──────────────────────────────────────────────
#  Shared state (thread-safe via lock)
# ──────────────────────────────────────────────
lock = threading.Lock()
events = []  # list of dicts saved by /event handler
session_start_time = datetime.now().strftime("%Y%m%d_%H%M%S")

# ──────────────────────────────────────────────
#  Step 2 — HTTP server the Quest talks to
# ──────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default access log noise

    # ── GET /sync ──────────────────────────────
    # Unity calls this to measure Quest↔laptop offset.
    # Returns laptop timestamps so Unity can compute quest_minus_host.
    def do_GET(self):
        if self.path != "/sync":
            self._send(404, {"error": "not found"})
            return

        receive_ns = time.time_ns()
        send_ns = time.time_ns()

        self._send(200, {
            "ok": True,
            "server_receive_ns": receive_ns,
            "server_send_ns": send_ns,
            "host_minus_companion_ns": host_minus_companion_ns,
        })

    # ── POST /event ────────────────────────────
    # Unity sends: { "name": "trial;...", "companion_timestamp_ns": 12345 }
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        if self.path == "/event":
            try:
                data = json.loads(body)
                name = data.get("name", "unknown")
                companion_ts_ns = int(data.get("companion_timestamp_ns", time.time_ns()))

                # Inject into Pupil recording
                try:
                    device.send_event(name, event_timestamp_unix_ns=companion_ts_ns)
                except Exception as e:
                    print(f"  [warn] Could not send event to Pupil: {e}")

                # Save locally too
                with lock:
                    events.append({
                        "companion_timestamp_ns": companion_ts_ns,
                        "name": name,
                        "received_host_ns": time.time_ns(),
                    })

                print(f"  [event] {name[:80]}")
                self._send(200, {"ok": True})

            except Exception as e:
                print(f"  [error] /event: {e}")
                self._send(400, {"ok": False, "error": str(e)})

        elif self.path == "/csv":
            # Unity can POST its game CSV here for safe-keeping
            filename = self.headers.get("X-Filename", f"game_{session_start_time}.csv")
            path = os.path.join(OUTPUT_DIR, filename)
            with open(path, "wb") as f:
                f.write(body)
            print(f"  [csv] Saved {filename}")
            self._send(200, {"ok": True})

        else:
            self._send(404, {"error": "not found"})

    def _send(self, code, obj):
        payload = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(payload))
        self.end_headers()
        self.wfile.write(payload)


server = HTTPServer(("0.0.0.0", PORT), Handler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
print(f"\nBridge running on port {PORT}. Press Ctrl+C when the session is done.\n")

# ──────────────────────────────────────────────
#  Step 3 — Wait for session to finish
# ──────────────────────────────────────────────
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nSession ended. Saving events and running post-processing...")

server.shutdown()
device.close()

# ──────────────────────────────────────────────
#  Save events log
# ──────────────────────────────────────────────
events_path = os.path.join(OUTPUT_DIR, f"bridge_events_{session_start_time}.csv")
with open(events_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["companion_timestamp_ns", "name", "received_host_ns"])
    writer.writeheader()
    writer.writerows(events)
print(f"Saved {len(events)} bridge events → {events_path}")

# ──────────────────────────────────────────────
#  Step 4 — Post-processing
#  Looks for files the Quest sent (or dropped manually into OUTPUT_DIR)
# ──────────────────────────────────────────────
def find_file(pattern):
    """Return the most recent file in OUTPUT_DIR matching a substring."""
    matches = [f for f in os.listdir(OUTPUT_DIR) if pattern in f]
    if not matches:
        return None
    matches.sort(reverse=True)
    return os.path.join(OUTPUT_DIR, matches[0])

trials_file = find_file("_trials.csv")
gaze_file   = find_file("gaze.csv")          # from Pupil recording export
video_file  = find_file("world.mp4")         # scene/eye camera video

if trials_file is None:
    print("\nNo trials CSV found in session_output/ — skipping post-processing.")
    print("Copy the Quest's _trials.csv and Pupil export files here, then run:")
    print("  python bridge.py --postprocess")
    sys.exit(0)

print(f"\nPost-processing...")
print(f"  Trials: {trials_file}")
print(f"  Gaze:   {gaze_file or 'NOT FOUND'}")
print(f"  Video:  {video_file or 'NOT FOUND'}")

# ── 4a: Load game trials ───────────────────────
trials = pd.read_csv(trials_file, sep=";", comment="#")
trials["timestamp_ns"] = trials["unixTimeNs"]

# ── 4b: Load bridge events (already companion-time) ──
bridge_events = pd.read_csv(events_path)

# Parse the event name string into columns
def parse_event(name):
    parts = name.split(";")
    d = {"event_type": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            d[k] = v
    return d

parsed = bridge_events["name"].apply(parse_event).apply(pd.Series)
bridge_events = pd.concat([bridge_events, parsed], axis=1)

# ── 4c: Merge with gaze if available ──────────
if gaze_file:
    gaze = pd.read_csv(gaze_file)

    # Pupil gaze export uses seconds; convert to ns
    if "timestamp [ns]" in gaze.columns:
        gaze["timestamp_ns"] = gaze["timestamp [ns]"]
    elif "timestamp" in gaze.columns:
        gaze["timestamp_ns"] = (gaze["timestamp"] * 1e9).astype(int)

    # For each gaze sample, find the most recent game event
    bridge_events_sorted = bridge_events.sort_values("companion_timestamp_ns")

    def assign_event(gaze_ts):
        before = bridge_events_sorted[
            bridge_events_sorted["companion_timestamp_ns"] <= gaze_ts
        ]
        if before.empty:
            return "pre_session"
        return before.iloc[-1]["event_type"]

    gaze["current_game_event"] = gaze["timestamp_ns"].apply(assign_event)

    out_gaze = os.path.join(OUTPUT_DIR, f"eyetracking_{session_start_time}.csv")
    gaze.to_csv(out_gaze, index=False)
    print(f"  → Eye tracking CSV: {out_gaze}")
else:
    print("  → Skipping gaze merge (no gaze.csv found)")

# ── 4d: Save enriched game CSV ─────────────────
out_trials = os.path.join(OUTPUT_DIR, f"game_data_{session_start_time}.csv")
trials.to_csv(out_trials, index=False, sep=";")
print(f"  → Game data CSV:    {out_trials}")

# ── 4e: Annotate eye video ────────────────────
if video_file and bridge_events is not None:

    cap = cv2.VideoCapture(video_file)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_video = os.path.join(OUTPUT_DIR, f"eye_video_annotated_{session_start_time}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_video, fourcc, fps, (w, h))

    # Video start time: use first gaze timestamp if available, else first event
    if gaze_file and "timestamp_ns" in gaze.columns:
        video_start_ns = int(gaze["timestamp_ns"].iloc[0])
    else:
        video_start_ns = int(bridge_events["companion_timestamp_ns"].iloc[0])

    ns_per_frame = int(1_000_000_000 / fps)
    frame_idx = 0
    current_label = ""

    print("  Annotating video...", end="", flush=True)
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame_ns = video_start_ns + frame_idx * ns_per_frame

        # Find the most recent event before this frame
        before = bridge_events[bridge_events["companion_timestamp_ns"] <= frame_ns]
        if not before.empty:
            row = before.iloc[-1]
            current_label = row["event_type"]
            # Add extra detail for trial events
            if current_label == "trial" and "rock" in row:
                current_label = f"trial | rock={row.get('rock','')} rewarded={row.get('rewarded','')}"

        if current_label:
            cv2.rectangle(frame, (0, h - 36), (w, h), (0, 0, 0), -1)
            cv2.putText(frame, current_label, (8, h - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 100), 2)

        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()
    print(f" done.\n  → Annotated video:  {out_video}")

print("\nAll done.")