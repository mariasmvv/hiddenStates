import pandas as pd
import numpy as np
import argparse
import os
import re
 
# ── Config ────────────────────────────────────────────────────────────────────
MINE_WINDOW_NS = 2_000_000_000   # 2 seconds in nanoseconds
PARTICIPANT_ID = "pilot_01"       # change per participant
 
# ── Argument parsing ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", default="/Users/matildegarcia/Desktop/Lebiom/PIC/pupil_export/data",
                    help="Folder containing events.csv, gaze.csv, etc.")
parser.add_argument("--participant", default="pilot_01")
args = parser.parse_args()
 
DATA_DIR = args.data_dir
PARTICIPANT = args.participant
 
print(f"Reading data from: {DATA_DIR}")
 
# ── 1. Load raw files ─────────────────────────────────────────────────────────
def fix_ts(series):
    """Convert Pupil Labs timestamp (may use comma as decimal) to int64 ns."""
    return pd.to_numeric(series.astype(str).str.replace(',', '.'), errors='coerce').astype('Int64')
 
df_evt = pd.read_csv(os.path.join(DATA_DIR, "events.csv"))
df_gaze = pd.read_csv(os.path.join(DATA_DIR, "gaze.csv"))
 
df_evt['timestamp_ns'] = fix_ts(df_evt['timestamp [ns]'])
df_gaze['timestamp_ns'] = fix_ts(df_gaze['timestamp [ns]'])
 
# ── 2. Parse trial events ─────────────────────────────────────────────────────
def parse_kv_event(name_str):
    """'trial;trial=1;level=1;rewarded=True;...' → dict"""
    parts = str(name_str).split(';')
    d = {'event_type': parts[0]}
    for part in parts[1:]:
        if '=' in part:
            k, v = part.split('=', 1)
            # normalise European decimal comma → dot
            v = v.replace(',', '.')
            d[k] = v
    return d
 
trial_rows = df_evt[df_evt['name'].str.startswith('trial;', na=False)].copy()
parsed = trial_rows['name'].apply(parse_kv_event)
trial_df = pd.DataFrame(list(parsed))
trial_df['timestamp_ns'] = trial_rows['timestamp_ns'].values
 
# Cast numeric columns
num_cols = ['trial', 'level', 'rock', 'levelTime', 'totalTime',
            'goldGained', 'levelGold', 'totalGold', 'depletionCount']
for col in num_cols:
    if col in trial_df.columns:
        trial_df[col] = pd.to_numeric(trial_df[col], errors='coerce')
 
bool_cols = ['rewarded', 'anyFlipOccurred', 'rock0ActiveAfter', 'rock1ActiveAfter', 'wasActive']
for col in bool_cols:
    if col in trial_df.columns:
        trial_df[col] = trial_df[col].map({'True': True, 'False': False})
 
trial_df = trial_df.sort_values('timestamp_ns').reset_index(drop=True)
trial_df['participant'] = PARTICIPANT
 
print(f"  Parsed {len(trial_df)} trials across {trial_df['level'].nunique()} levels")
 
# ── 3. Assign bout numbers ────────────────────────────────────────────────────
# A bout = consecutive trials on the same rock (same as Dataframes.py logic but
# applied purely to the trial-level frame)
trial_df['rock_switch'] = trial_df['rock'] != trial_df['rock'].shift()
trial_df.loc[0, 'rock_switch'] = False
trial_df['bout_number'] = trial_df['rock_switch'].astype(int).cumsum()
 
print(f"  Found {trial_df['bout_number'].nunique()} bouts")
 
# ── 4. Decision variables per trial ──────────────────────────────────────────
consecutive_failures = []
cumulative_rewards   = []
 
consec_fail = 0
cum_reward  = 0.0
current_bout = trial_df['bout_number'].iloc[0]
 
for _, row in trial_df.iterrows():
    # Reset on new bout
    if row['bout_number'] != current_bout:
        consec_fail  = 0
        cum_reward   = 0.0
        current_bout = row['bout_number']
 
    # Record BEFORE updating (value going INTO this trial)
    consecutive_failures.append(consec_fail)
    cumulative_rewards.append(cum_reward)
 
    # Update AFTER this trial
    if row['rewarded']:
        consec_fail = 0          # full reset on reward
        cum_reward += row['goldGained'] if not np.isnan(row['goldGained']) else 0
    else:
        consec_fail += 1
 
trial_df['consecutive_failures'] = consecutive_failures
trial_df['cumulative_rewards']   = cumulative_rewards
 
# ── 5. Label last trial before switch ────────────────────────────────────────
# A trial is "last in bout" if the next trial is a different rock
trial_df['is_last_before_switch'] = (
    trial_df['bout_number'] != trial_df['bout_number'].shift(-1)
).astype(int)
# Last row of the whole session is also "last" (session end)
trial_df.loc[trial_df.index[-1], 'is_last_before_switch'] = 1
 
n_switches = trial_df['is_last_before_switch'].sum()
print(f"  Labelled {n_switches} switch decisions")
 
# ── 6. Get mine_start timestamps for each trial ───────────────────────────────
# Strategy: each trial event follows its mine_start event.
# We match each trial to the most recent mine_start on the same rock.
mine_starts = df_evt[df_evt['name'].str.startswith('mine_start', na=False)].copy()
mine_starts['rock_ms'] = mine_starts['name'].str.extract(r'rock=(\d)')[0].astype(float)
mine_starts = mine_starts.sort_values('timestamp_ns').reset_index(drop=True)
 
def find_mine_start_ts(trial_ts, rock):
    """Return timestamp of most recent mine_start for this rock before trial_ts."""
    candidates = mine_starts[
        (mine_starts['rock_ms'] == rock) &
        (mine_starts['timestamp_ns'] < trial_ts)
    ]
    if candidates.empty:
        return np.nan
    return candidates.iloc[-1]['timestamp_ns']
 
trial_df['mine_start_ts'] = trial_df.apply(
    lambda r: find_mine_start_ts(r['timestamp_ns'], r['rock']), axis=1
)
trial_df['mine_end_ts'] = trial_df['mine_start_ts'] + MINE_WINDOW_NS
 
found_windows = trial_df['mine_start_ts'].notna().sum()
print(f"  Matched mine_start timestamps for {found_windows}/{len(trial_df)} trials")
 
# ── 7. Extract 2-second gaze window per trial ─────────────────────────────────
# For each trial, summarise gaze metrics in [mine_start_ts, mine_end_ts]
gaze_sorted = df_gaze.sort_values('timestamp_ns').reset_index(drop=True)
 
gaze_windows = []
for _, row in trial_df.iterrows():
    if pd.isna(row['mine_start_ts']):
        gaze_windows.append({})
        continue
 
    w = gaze_sorted[
        (gaze_sorted['timestamp_ns'] >= row['mine_start_ts']) &
        (gaze_sorted['timestamp_ns'] <= row['mine_end_ts'])
    ]
 
    if w.empty:
        gaze_windows.append({})
        continue
 
    entry = {
        'gaze_n_samples':        len(w),
        'gaze_mean_x':           w['gaze x [px]'].mean(),
        'gaze_mean_y':           w['gaze y [px]'].mean(),
        'gaze_std_x':            w['gaze x [px]'].std(),
        'gaze_std_y':            w['gaze y [px]'].std(),
        'gaze_mean_az':          w['azimuth [deg]'].mean(),
        'gaze_mean_el':          w['elevation [deg]'].mean(),
        'n_fixations_in_window': w['fixation id'].notna().sum(),
        'n_blinks_in_window':    w['blink id'].notna().sum(),
        'blink_occurred':        int(w['blink id'].notna().any()),
    }
    gaze_windows.append(entry)
 
gaze_window_df = pd.DataFrame(gaze_windows, index=trial_df.index)
trial_df = pd.concat([trial_df, gaze_window_df], axis=1)
 
print(f"  Gaze window columns added: {list(gaze_window_df.columns)}")
 
# ── 8. Save ───────────────────────────────────────────────────────────────────
output_cols = [
    'participant', 'trial', 'level', 'bout_number', 'rock',
    'wasActive', 'rewarded', 'goldGained', 'levelGold', 'totalGold',
    'anyFlipOccurred', 'depletionCount', 'levelTime', 'totalTime',
    'consecutive_failures', 'cumulative_rewards', 'is_last_before_switch',
    'mine_start_ts', 'timestamp_ns',
    'gaze_n_samples', 'gaze_mean_x', 'gaze_mean_y', 'gaze_std_x', 'gaze_std_y',
    'gaze_mean_az', 'gaze_mean_el',
    'n_fixations_in_window', 'n_blinks_in_window', 'blink_occurred',
]
available = [c for c in output_cols if c in trial_df.columns]
out = trial_df[available].copy()
 
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trials_with_decision_vars.csv")
out.to_csv(out_path, index=False)
print(f"\nSaved: {out_path}")
print(f"Final shape: {out.shape}")
print("\nPreview:")
print(out[['trial', 'level', 'bout_number', 'rock', 'rewarded',
           'consecutive_failures', 'cumulative_rewards',
           'is_last_before_switch', 'gaze_n_samples']].to_string())
 