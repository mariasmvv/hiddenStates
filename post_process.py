"""
Offline post-processing for one Rustbucket session folder.

Usage:
    python post_process.py "C:\\path\\to\\PLAYERNAME_YYYYMMDD_HHMMSS"

Expected structure:
    SESSION/
      unity/
        *_trials.csv
      pupil_export/
        events.csv
        gaze.csv
        world.mp4
      derived/
"""

import sys
from pathlib import Path
import math

import cv2
import pandas as pd


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def find_one(folder: Path, pattern: str):
    matches = sorted(folder.glob(pattern))
    return matches[0] if matches else None


def parse_event_name(name: str):
    parts = str(name).split(";")
    out = {"event_type": parts[0] if parts else ""}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k] = v
    return out


def load_trials(unity_folder: Path):
    trials_file = find_one(unity_folder, "*_trials.csv")
    if trials_file is None:
        raise FileNotFoundError(f"No *_trials.csv found in {unity_folder}")
    trials = pd.read_csv(trials_file, sep=";", comment="#")
    return trials_file, trials


def load_pupil_events(pupil_folder: Path):
    events_file = pupil_folder / "events.csv"
    if not events_file.exists():
        raise FileNotFoundError(f"Missing {events_file}")

    events = pd.read_csv(events_file)

    required = {"recording id", "timestamp [ns]", "name", "type"}
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f"events.csv missing columns: {sorted(missing)}")

    parsed = events["name"].apply(parse_event_name).apply(pd.Series)
    events = pd.concat([events, parsed], axis=1)

    # Keep only rows that look like your injected game events
    game_events = events[events["event_type"].notna()].copy()
    game_events = game_events[
        game_events["event_type"].astype(str).str.len() > 0
    ].copy()

    # Remove recording.begin and similar non-game rows from the main event table
    excluded = {"recording.begin", "recording.end"}
    game_events = game_events[
        ~game_events["event_type"].isin(excluded)
    ].copy()

    game_events = game_events.sort_values("timestamp [ns]").reset_index(drop=True)
    return events_file, events, game_events


def label_gaze(gaze_file: Path, game_events: pd.DataFrame):
    gaze = pd.read_csv(gaze_file)

    if "timestamp [ns]" in gaze.columns:
        gaze_ts = gaze["timestamp [ns]"].astype("int64")
    elif "timestamp" in gaze.columns:
        gaze_ts = (gaze["timestamp"].astype(float) * 1e9).round().astype("int64")
        gaze["timestamp [ns]"] = gaze_ts
    else:
        raise ValueError("gaze.csv has neither 'timestamp [ns]' nor 'timestamp' column.")

    game_events_sorted = game_events.sort_values("timestamp [ns]").copy()

    event_times = game_events_sorted["timestamp [ns]"].astype("int64").tolist()
    event_labels = game_events_sorted["event_type"].astype(str).tolist()

    current_labels = []
    current_idx = []

    j = -1
    for ts in gaze_ts:
        while (j + 1) < len(event_times) and event_times[j + 1] <= ts:
            j += 1

        if j >= 0:
            current_labels.append(event_labels[j])
            current_idx.append(j)
        else:
            current_labels.append("pre_session")
            current_idx.append(-1)

    gaze["current_game_event"] = current_labels
    gaze["current_game_event_index"] = current_idx
    return gaze


def annotate_video(video_file: Path, output_file: Path, game_events: pd.DataFrame):
    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_file}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        raise RuntimeError("Invalid FPS in video.")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_file), fourcc, fps, (width, height))

    # Use the first event timestamp as reference start
    if len(game_events) == 0:
        raise RuntimeError("No game events found in Pupil events.csv.")

    first_ts = int(game_events.iloc[0]["timestamp [ns]"])
    event_times = game_events["timestamp [ns]"].astype("int64").tolist()
    event_labels = game_events["event_type"].astype(str).tolist()

    frame_idx = 0
    current_event_i = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame_ts = first_ts + int((frame_idx / fps) * 1e9)

        while (current_event_i + 1) < len(event_times) and event_times[current_event_i + 1] <= frame_ts:
            current_event_i += 1

        current_label = event_labels[current_event_i]
        current_event_ts = event_times[current_event_i]
        delta_ms = (frame_ts - current_event_ts) / 1e6

        overlay1 = f"Event: {current_label}"
        overlay2 = f"t since event: {delta_ms:8.1f} ms"
        overlay3 = f"frame {frame_idx+1}/{frame_count}"

        cv2.rectangle(frame, (20, 20), (720, 130), (0, 0, 0), -1)
        cv2.putText(frame, overlay1, (35, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, overlay2, (35, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)
        cv2.putText(frame, overlay3, (35, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 2, cv2.LINE_AA)

        out.write(frame)
        frame_idx += 1

    cap.release()
    out.release()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    if len(sys.argv) != 2:
        print('Usage: python post_process.py "PATH_TO_SESSION_FOLDER"')
        sys.exit(1)

    session_dir = Path(sys.argv[1])
    if not session_dir.exists():
        sys.exit(f"Session folder does not exist: {session_dir}")

    unity_dir = session_dir / "unity"
    pupil_dir = session_dir / "pupil_export"
    derived_dir = session_dir / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    print(f"Session: {session_dir}")

    trials_file, trials = load_trials(unity_dir)
    print(f"Trials: {trials_file.name} ({len(trials)} rows)")

    events_file, raw_events, game_events = load_pupil_events(pupil_dir)
    print(f"Pupil events: {events_file.name} ({len(raw_events)} rows total)")
    print(f"Game events parsed: {len(game_events)} rows")

    out_events = derived_dir / "game_events_from_pupil.csv"
    game_events.to_csv(out_events, index=False)
    print(f"Saved: {out_events}")

    out_trials = derived_dir / "game_trials_copy.csv"
    trials.to_csv(out_trials, index=False, sep=";")
    print(f"Saved: {out_trials}")

    gaze_file = pupil_dir / "gaze.csv"
    if gaze_file.exists():
        gaze_labeled = label_gaze(gaze_file, game_events)
        out_gaze = derived_dir / "gaze_labeled.csv"
        gaze_labeled.to_csv(out_gaze, index=False)
        print(f"Saved: {out_gaze}")
    else:
        print("No gaze.csv found — skipping gaze labeling.")

    video_file = pupil_dir / "world.mp4"
    if video_file.exists():
        out_video = derived_dir / "world_annotated.mp4"
        annotate_video(video_file, out_video, game_events)
        print(f"Saved: {out_video}")
    else:
        print("No world.mp4 found — skipping video annotation.")

    print("Done.")


if __name__ == "__main__":
    main()