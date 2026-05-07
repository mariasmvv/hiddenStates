import subprocess
import time
from pathlib import Path
import pandas as pd
import streamlit as st

# --- CONFIGURATION ---
UNITY_EXE = Path(r"C:\Users\latent02\Documents\HiddenStatesPIC\RustBucket_game\Environment.exe")
DATA_ROOT = Path(r"C:\Users\latent02\Documents\HiddenStatesPIC\DadosTask")
BRIDGE_SCRIPT = Path(r"C:\Users\latent02\Documents\HiddenStatesPIC\bridge.py")
POST_PROCESS_SCRIPT = Path(r"C:\Users\latent02\Documents\HiddenStatesPIC\post_process.py")

st.set_page_config(page_title="Rustbucket Command Center", layout="wide")

# Persistent process tracking
if 'unity_proc' not in st.session_state: st.session_state.unity_proc = None
if 'bridge_proc' not in st.session_state: st.session_state.bridge_proc = None

st.title("Rustbucket Command Center")

# ---------------------------------------------------------
# STEP 1: NETWORK BRIDGE (Buttons Side-by-Side)
# ---------------------------------------------------------
st.header("Step 1: Network Bridge")
# Create two small columns for the buttons and one larger one for the status
btn_col1, btn_col2, status_col = st.columns([1, 1, 2])

with btn_col1:
    if st.button("Start Bridge", use_container_width=True):
        if st.session_state.bridge_proc is None:
            try:
                st.session_state.bridge_proc = subprocess.Popen(
                    ["python", str(BRIDGE_SCRIPT)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                st.success("Launched")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("Running")

with btn_col2:
    if st.button("Stop Bridge", use_container_width=True):
        if st.session_state.bridge_proc:
            st.session_state.bridge_proc.terminate()
            st.session_state.bridge_proc = None
            st.info("Stopped")
        else:
            st.info("Not active")

with status_col:
    if st.session_state.bridge_proc:
        st.info("Bridge is currently online.")
    else:
        st.write("Bridge is offline.")

# ---------------------------------------------------------
# STEP 2: Pupil Labs Recording
# ---------------------------------------------------------
st.header("Step 2: Pupil Labs Recording")
st.warning("Start recording pupil labs!")

# ---------------------------------------------------------
# STEP 3: SESSION CONTROL
# ---------------------------------------------------------
st.header("Step 3: Session Control")
participant_name = st.text_input("Enter Participant Name", value="TEST_USER")

c1, c2 = st.columns(2)
with c1:
    if st.button("Launch Unity Game", type="primary", use_container_width=True, key="launch_unity"):
        config_file = DATA_ROOT / "next_session_config.txt"
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w") as f:
            f.write(participant_name)
        
        st.session_state.unity_proc = subprocess.Popen([str(UNITY_EXE)])
        st.success(f"Started: {participant_name}")

with c2:
    if st.button("Quit Unity Session", use_container_width=True, key="quit_unity"):
        if st.session_state.unity_proc and st.session_state.unity_proc.poll() is None:
            st.session_state.unity_proc.kill()
            st.session_state.unity_proc = None
            st.error("Unity Terminated")
        else:
            st.info("No active session.")

# ---------------------------------------------------------
# STEP 4: ANALYSIS
# ---------------------------------------------------------
st.header("Step 4: Analysis")
if st.button("Run Post-Processing", use_container_width=True):
    if st.session_state.unity_proc and st.session_state.unity_proc.poll() is None:
        st.warning("Please close Unity before processing.")
    else:
        with st.spinner("Processing..."):
            try:
                result = subprocess.run(["python", str(POST_PROCESS_SCRIPT)], capture_output=True, text=True)
                if result.returncode == 0:
                    st.success("Complete!")
                    st.code(result.stdout)
                else:
                    st.error("Error detected:")
                    st.code(result.stderr)
            except Exception as e:
                st.error(f"Script failed: {e}")

# ---------------------------------------------------------
# LIVE MONITORING (Fixed Decimals)
# ---------------------------------------------------------
st.divider()
st.header("Live Session Monitor")

def get_latest_trials():
    if not DATA_ROOT.exists(): return None, None
    folders = [p for p in DATA_ROOT.iterdir() if p.is_dir()]
    if not folders: return None, None
    latest_folder = max(folders, key=lambda p: p.stat().st_mtime)
    trial_files = list((latest_folder / "unity").glob("*_trials.csv"))
    if not trial_files: return None, latest_folder.name
    latest_file = max(trial_files, key=lambda p: p.stat().st_mtime)
    
    try:
        # decimal="," fixes the "Unknown format code f" error
        df = pd.read_csv(latest_file, sep=";", comment="#", decimal=",")
        for col in ['totalGold', 'level', 'trial']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df, latest_folder.name
    except:
        return None, latest_folder.name

trials_df, folder_name = get_latest_trials()

if trials_df is not None and not trials_df.empty:
    st.caption(f"Active Session: {folder_name}")
    m1, m2, m3 = st.columns(3)
    # Using iloc[-1] to grab the most recent entry
    m1.metric("Total Gold", f"{trials_df['totalGold'].fillna(0).iloc[-1]:.0f}")
    m2.metric("Level", int(trials_df['level'].fillna(0).iloc[-1]))
    m3.metric("Trials", int(trials_df['trial'].fillna(0).iloc[-1]))
    st.dataframe(trials_df, width="stretch", height=300)
else:
    st.info("Awaiting trial data...")

if st.checkbox("Auto-Refresh", value=True):
    time.sleep(2)
    st.rerun()