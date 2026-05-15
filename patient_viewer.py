#python -m streamlit run C:\Users\VIRTUALIAI\Documents\HiddenStates\patient_viewer.py

import streamlit as st
from pathlib import Path
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(r"C:\Users\VIRTUALIAI\Documents\HiddenStates\DadosTask")

st.set_page_config(
    page_title="HiddenStates · Patient Viewer",
    page_icon="👁️",
    layout="wide",
)

if "df" not in st.session_state:
    st.session_state.df = None
if "load_errors" not in st.session_state:
    st.session_state.load_errors = []

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
}

/* Dark medical aesthetic */
.stApp {
    background: #0a0d12;
    color: #e8edf5;
}

h1, h2, h3 { font-family: 'Syne', sans-serif; font-weight: 800; }

.title-block {
    padding: 2.5rem 0 1.5rem 0;
    border-bottom: 1px solid #1e2530;
    margin-bottom: 2rem;
}

.title-block h1 {
    font-size: 2.4rem;
    letter-spacing: -0.04em;
    color: #e8edf5;
    margin: 0;
}

.title-block p {
    color: #5a6478;
    font-family: 'DM Mono', monospace;
    font-size: 0.78rem;
    margin: 0.4rem 0 0 0;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.patient-card {
    background: #111620;
    border: 1px solid #1e2530;
    border-radius: 10px;
    padding: 1.5rem 1.8rem;
    margin-bottom: 1.5rem;
}

.patient-card .label {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #3d8bff;
    margin-bottom: 0.3rem;
}

.patient-card .name {
    font-size: 1.6rem;
    font-weight: 800;
    color: #e8edf5;
    letter-spacing: -0.02em;
}

.patient-card .path {
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    color: #3a4255;
    margin-top: 0.5rem;
    word-break: break-all;
}

.stats-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.stat-box {
    background: #111620;
    border: 1px solid #1e2530;
    border-radius: 8px;
    padding: 1rem 1.4rem;
    flex: 1;
}

.stat-box .stat-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #5a6478;
    margin-bottom: 0.2rem;
}

.stat-box .stat-value {
    font-size: 1.5rem;
    font-weight: 800;
    color: #3d8bff;
    letter-spacing: -0.03em;
}

.event-pill {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 20px;
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    margin: 0.2rem;
}

.pill-fixation  { background: #0d2a4a; color: #3d8bff; border: 1px solid #1a4a7a; }
.pill-blink     { background: #2a1a0d; color: #ff8c3d; border: 1px solid #7a3a0d; }
.pill-saccade   { background: #0d2a1a; color: #3dff8c; border: 1px solid #0d7a3a; }
.pill-default   { background: #1e1a2a; color: #c87aff; border: 1px solid #4a2a7a; }

/* Override Streamlit dataframe colors */
.stDataFrame { border-radius: 8px; overflow: hidden; }

div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label {
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #5a6478 !important;
}

div[data-testid="stSelectbox"] > div > div,
div[data-testid="stTextInput"] > div > div > input {
    background: #111620 !important;
    border-color: #1e2530 !important;
    color: #e8edf5 !important;
    border-radius: 8px !important;
}

.stButton > button {
    background: #3d8bff;
    color: #0a0d12;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 0.85rem;
    letter-spacing: 0.05em;
    border: none;
    border-radius: 8px;
    padding: 0.55rem 1.6rem;
    width: 100%;
    transition: background 0.2s;
}
.stButton > button:hover { background: #5fa3ff; }

.error-box {
    background: #2a0d0d;
    border: 1px solid #7a1a1a;
    border-radius: 8px;
    padding: 1rem 1.4rem;
    color: #ff6b6b;
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    margin: 1rem 0;
}

.folder-list {
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: #5a6478;
    line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_patient_folders(base: Path) -> dict[str, Path]:
    """
    Scan BASE_DIR for sub-folders.
    Returns {display_name: folder_path} sorted alphabetically.
    """
    if not base.exists():
        return {}
    folders = {}
    for p in sorted(base.iterdir()):
        if p.is_dir():
            # Use the full folder name as key, and first word as display hint
            folders[p.name] = p
    return folders


def load_events(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    
    # 1. Rename 'name' to 'event_type' and move to front
    df.insert(0, "event_type", df.pop("name"))
    df["event_type"] = df["event_type"].astype(str)

    # 2. Define our logic:
    # If it's a mine_finished row, we FORCE it to one of two clean names.
    # Otherwise, we just take the first word before the semicolon.
    def clean_event_names(val):
        if "mine_finished" in val:
            if "rewarded=True" in val:
                return "mine_finished_reward"
            elif "rewarded=False" in val:
                return "mine_finished_fail"
            return "mine_finished" # Fallback if neither found
        
        # For everything else (axe_pickup, etc.), take first word
        return val.split(';')[0].strip()

    df["event_type"] = df["event_type"].apply(clean_event_names)

    # 3. Rename the timestamp
    df = df.rename(columns={"timestamp [ns]": "start timestamp [ns]"})
    
    return df


#def load_fixations(path: Path) -> pd.DataFrame:
#    df = pd.read_csv(path)
#    df.insert(0, "event_type", "fixation")
#    return df


#def load_blinks(path: Path) -> pd.DataFrame:
#    df = pd.read_csv(path)
#    df.insert(0, "event_type", "blink")
#    return df


#def load_saccades(path: Path) -> pd.DataFrame:
#    df = pd.read_csv(path)
#    df.insert(0, "event_type", "saccade")
#    return df

    
@st.cache_data
def build_dataframe(folder: Path) -> pd.DataFrame:
    pupil_dir = folder / "pupil"
    if not pupil_dir.exists():
        pupil_dir = folder          # fallback: csvs directly in folder

    parts = []
    errors = []

    for loader, fname in [
        (load_events,    "events.csv"),
        #(load_fixations, "fixations.csv"),
        #(load_blinks,    "blinks.csv"),
        #(load_saccades,  "saccades.csv"),
    ]:
        fp = pupil_dir / fname
        if fp.exists():
            try:
                parts.append(loader(fp))
            except Exception as e:
                errors.append(f"{fname}: {e}")
        else:
            errors.append(f"{fname}: not found")

    if not parts:
        raise FileNotFoundError(
            f"No CSV files found in {pupil_dir}.\n" + "\n".join(errors)
        )

    combined = pd.concat(parts, ignore_index=True, sort=False)
    cols_to_remove = ["type", "section id"]
    combined = combined.drop(columns=[c for c in cols_to_remove if c in combined.columns])
    combined = combined.sort_values("start timestamp [ns]", ignore_index=True)
    combined = assign_bouts(combined)

    combined = calculate_decision_variables(combined)

    return combined, errors


def assign_bouts(df: pd.DataFrame) -> pd.DataFrame:
    """
    A bout is the interval between consecutive axe pickups (alternating hands).
    Pickup markers: 'axe_pickup_left' and 'axe_pickup_right' in event_type.
    Rows before the first pickup get bout=0 (pre-task).
    bout column is inserted as the second column.
    """
    PICKUPS = {"axe_pickup_left", "axe_pickup_right"}

    pickup_mask = df["event_type"].isin(PICKUPS)
    pickup_locs = [i for i, v in enumerate(pickup_mask) if v]

    bout_vals = [0] * len(df)   # 0 = pre-task (before first pickup)

    for bout_num, (start_loc, end_loc) in enumerate(
        zip(pickup_locs, pickup_locs[1:]), start=1
    ):
        for i in range(start_loc, end_loc):
            bout_vals[i] = bout_num

    # Last pickup onward → final open bout
    if pickup_locs:
        for i in range(pickup_locs[-1], len(df)):
            bout_vals[i] = len(pickup_locs)

    df = df.copy()
    df.insert(1, "bout", pd.array(bout_vals, dtype="Int64"))
    return df


def event_pill(event_type: str) -> str:
    cls = {
        "fixation": "pill-fixation",
        "blink":    "pill-blink",
        "saccade":  "pill-saccade",
    }.get(str(event_type).lower(), "pill-default")
    return f'<span class="event-pill {cls}">{event_type}</span>'

def calculate_decision_variables(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df['is_success'] = (df['event_type'] == 'mine_finished_reward').astype(int)
    df['is_failure'] = (df['event_type'] == 'mine_finished_fail').astype(int)
    
    df['total_rewards'] = df.groupby('bout')['is_success'].cumsum()
    df['success_block'] = df.groupby('bout')['is_success'].cumsum()
    df['consecutive_failures'] = df.groupby(['bout', 'success_block'])['is_failure'].cumsum()

    df['consecutive_failures'] = df.groupby('bout')['consecutive_failures'].shift(1).fillna(0)
    df['total_rewards'] = df.groupby('bout')['total_rewards'].shift(1).fillna(0)

    # ── Min-max normalisation (within-session max as denominator) ─────────────
    cf_max = df['consecutive_failures'].abs().max()
    tr_max = df['total_rewards'].abs().max()

    df['consecutive_failures_norm'] = df['consecutive_failures'] / cf_max if cf_max else 0.0
    df['total_rewards_norm']        = df['total_rewards']        / tr_max if tr_max else 0.0
    # ─────────────────────────────────────────────────────────────────────────

    return df.drop(columns=['is_success', 'is_failure', 'success_block'])


# ── UI ────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="title-block">
  <h1>👁️ HiddenStates · Patient Viewer</h1>
  <p>Eye-tracking data explorer · Pupil Labs CSV pipeline</p>
</div>
""", unsafe_allow_html=True)

# Scan for available patients
all_folders = find_patient_folders(BASE_DIR)

col_left, col_right = st.columns([1, 2.5], gap="large")

with col_left:
    st.markdown("#### Select Patient")

    if all_folders:
        folder_names = list(all_folders.keys())
        selected_name = st.selectbox(
            "Available patients",
            options=["— choose —"] + folder_names,
            label_visibility="collapsed",
        )
    else:
        selected_name = "— choose —"
        st.markdown(f"""
        <div class="error-box">
        BASE_DIR not found or empty:<br>
        <code>{BASE_DIR}</code>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("**or type a name directly:**")
    typed_name = st.text_input(
        "Patient name / folder prefix",
        placeholder="e.g. MariaVilela",
        label_visibility="collapsed",
    )

    load_btn = st.button("Load Patient Data")

    # Resolve which folder to open
    resolved_folder = None
    resolved_label  = None

    if typed_name.strip():
        # Match typed prefix against folder names (case-insensitive)
        matches = [
            (name, path) for name, path in all_folders.items()
            if name.lower().startswith(typed_name.strip().lower())
        ]
        if len(matches) == 1:
            resolved_label, resolved_folder = matches[0]
        elif len(matches) > 1:
            # Show all matches and let user pick
            st.markdown("**Multiple matches — pick one:**")
            choice = st.selectbox(
                "Matches",
                options=[m[0] for m in matches],
                label_visibility="collapsed",
            )
            resolved_label  = choice
            resolved_folder = all_folders[choice]
        else:
            # Try exact folder under BASE_DIR even if not yet scanned
            candidate = BASE_DIR / typed_name.strip()
            if candidate.exists():
                resolved_label  = typed_name.strip()
                resolved_folder = candidate

    elif selected_name != "— choose —":
        resolved_label  = selected_name
        resolved_folder = all_folders[selected_name]

    if all_folders:
        st.markdown("---")
        st.markdown(
            '<div class="folder-list">'
            + "<b style='color:#3d8bff;font-size:0.7rem;letter-spacing:0.12em;text-transform:uppercase;'>Available folders</b><br>"
            + "<br>".join(f"· {n}" for n in list(all_folders.keys())[:20])
            + ("…" if len(all_folders) > 20 else "")
            + "</div>",
            unsafe_allow_html=True,
        )

# ── Right panel ───────────────────────────────────────────────────────────────

with col_right:
    # 1. Handle the Loading Action
    if load_btn and resolved_folder:
        with st.spinner("Loading CSVs…"):
            try:
                # Store results in session state so they persist
                st.session_state.df, st.session_state.load_errors = build_dataframe(resolved_folder)
            except Exception as e:
                st.error(f"Failed to load: {e}")

    # 2. Display Data (Check if we have data in session state)
    if st.session_state.df is not None:
        df = st.session_state.df
        load_errors = st.session_state.load_errors

        # Patient Info Card
        st.markdown(f"""
        <div class="patient-card">
          <div class="label">Patient folder</div>
          <div class="name">{resolved_label}</div>
          <div class="path">{resolved_folder}</div>
        </div>
        """, unsafe_allow_html=True)

        # Stats Calculations
        counts = df["event_type"].value_counts()
        unique_types = counts.index.tolist()
        n_bouts = int(df["bout"].max()) if df["bout"].notna().any() else 0

        # Stats Row
        cols_stat = st.columns(5)

        total_gold = 0
        level_end_rows = df[df["event_type"] == "level_end"] if "event_type" in df.columns else pd.DataFrame()
        if not level_end_rows.empty:
            # Parse totalGold from the raw name column — it's already processed so we need original
            # Actually pull from the raw CSV name field via the original df
            last_level_end = level_end_rows.iloc[-1]
            # Re-parse from event_type isn't enough; we need to read from the original name before cleaning.
            # Instead, count rewards * gold_per_reward (each reward = 10 gold based on level_end data)
            pass

        # Better: count directly from mine_finished_reward events
        n_rewards = int((df["event_type"] == "mine_finished_reward").sum())
        n_failures = int((df["event_type"] == "mine_finished_fail").sum())
        n_trials = n_rewards + n_failures
        success_rate = (n_rewards / n_trials * 100) if n_trials > 0 else 0

        stat_items = [
            ("Total Gold 🪙", f"{n_rewards * 10:,}"),   # each reward = 10 gold
            ("Bouts", str(n_bouts)),
            ("Trials", f"{n_trials:,}"),
            ("Success Rate", f"{success_rate:.1f}%"),
            ("Interruptions", str(int((df["event_type"] == "mine_interrupted").sum()))),
        ]

        for col, (lbl, val) in zip(cols_stat, stat_items):
            with col:
                st.markdown(f"""<div class="stat-box"><div class="stat-label">{lbl}</div><div class="stat-value">{val}</div></div>""", unsafe_allow_html=True)

        # Event Type Pills
        pills_html = "".join(event_pill(et) + f"&nbsp;<small style='color:#3a4255;font-size:0.7rem;'>{cnt:,}</small>&nbsp;&nbsp;" for et, cnt in counts.items())
        st.markdown(pills_html, unsafe_allow_html=True)

        # --- THE FILTER (Crucial Step) ---
        st.markdown("#### Filter View")
        all_event_types = sorted(df["event_type"].unique().tolist())
        selected_types = st.multiselect("Show only specific event types:", options=all_event_types, default=all_event_types)
        
        # Apply filter
        filtered_df = df[df["event_type"].isin(selected_types)]

        # Tabs
        tab_labels = ["All events", "By Bout"] + unique_types
        tabs = st.tabs(tab_labels)

        with tabs[0]:
            st.data_editor(filtered_df, use_container_width=True, height=480)
            st.caption(f"{len(filtered_df):,} rows · {filtered_df.shape[1]} columns")

        with tabs[1]:
            bout_nums = sorted(filtered_df["bout"].dropna().unique().tolist())
            if n_bouts == 0:
                st.warning("No bouts found.")
            else:
                selected_bout = st.selectbox("Select bout", options=bout_nums, format_func=lambda b: f"Bout {b}" if b > 0 else "Bout 0")
                bout_df = filtered_df[filtered_df["bout"] == selected_bout]
                st.data_editor(bout_df, use_container_width=True, height=430)
                st.caption(f"{len(bout_df):,} rows · {bout_df.shape[1]} columns")

        for tab, etype in zip(tabs[2:], unique_types):
            with tab:
                etype_df = df[df["event_type"] == etype]
                st.data_editor(etype_df, use_container_width=True, height=480)
                st.caption(f"{len(etype_df):,} rows · {etype_df.shape[1]} columns")

        if load_errors:
            with st.expander("⚠️ Load warnings"):
                for e in load_errors: st.markdown(f"`{e}`")

    # 3. Empty State (Show when no data is loaded yet)
    elif not load_btn:
        st.markdown("""
        <div style="padding:4rem 2rem; text-align:center; color:#3a4255;">
          <div style="font-size:3rem;">👁️</div>
          <div style="font-family:'DM Mono',monospace; font-size:0.8rem; letter-spacing:0.15em; text-transform:uppercase; margin-top:1rem;">
            Select a patient and click Load
          </div>
        </div>
        """, unsafe_allow_html=True)


# ── Batch Export ──────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("#### 📦 Export All Patients")

export_btn = st.button("Export all patients → CSV")

if export_btn:
    all_rows = []
    export_errors = []

    for folder_name, folder_path in all_folders.items():
        try:
            df_patient, _ = build_dataframe(folder_path)

            # Last row of each bout
            last_rows = (
                df_patient
                .sort_values("start timestamp [ns]")
                .groupby("bout", as_index=False)
                .last()
            )

            last_rows = last_rows[["bout", "total_rewards_norm", "consecutive_failures_norm"]].copy()
            last_rows.insert(0, "recording_id", folder_name)
            last_rows["constant_bias"] = 1

            all_rows.append(last_rows)

        except Exception as e:
            export_errors.append(f"{folder_name}: {e}")

    if all_rows:
        export_df = pd.concat(all_rows, ignore_index=True)
        export_df = export_df[["recording_id", "bout", "total_rewards_norm", "consecutive_failures_norm", "constant_bias"]]

        csv_bytes = export_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="⬇️ Download export.csv",
            data=csv_bytes,
            file_name="hidden_states_export.csv",
            mime="text/csv",
        )
        st.success(f"✅ Exported {len(export_df)} rows across {len(all_rows)} patients.")
        st.dataframe(export_df.head(20))

    if export_errors:
        with st.expander("⚠️ Export warnings"):
            for e in export_errors:
                st.markdown(f"`{e}`")

# ── Batch Export ──────────────────────────────────────────────────────────────

st.markdown("#### 📦 Export All Patients 2")

export_btn = st.button("Export all patients 2 → CSV")

if export_btn:
    all_rows = []
    export_errors = []

    for folder_name, folder_path in all_folders.items():
        try:
            df_patient, _ = build_dataframe(folder_path)

            # Last row of each bout
            last_rows = (
                df_patient
                .sort_values("start timestamp [ns]")
                .groupby("bout", as_index=False)
                .last()
            )

            last_rows = last_rows[["bout", "total_rewards_norm", "consecutive_failures_norm"]].copy()
            last_rows.insert(0, "recording_id", folder_name)

            all_rows.append(last_rows)

        except Exception as e:
            export_errors.append(f"{folder_name}: {e}")

    if all_rows:
        export_df = pd.concat(all_rows, ignore_index=True)
        export_df = export_df[["recording_id", "bout", "total_rewards_norm", "consecutive_failures_norm"]]

        csv_bytes = export_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="⬇️ Download export 2.csv",
            data=csv_bytes,
            file_name="hidden_states_export2.csv",
            mime="text/csv",
        )
        st.success(f"✅ Exported {len(export_df)} rows across {len(all_rows)} patients.")
        st.dataframe(export_df.head(20))

    if export_errors:
        with st.expander("⚠️ Export warnings"):
            for e in export_errors:
                st.markdown(f"`{e}`")
    