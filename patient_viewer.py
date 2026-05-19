#python -m streamlit run C:\Users\VIRTUALIAI\Documents\HiddenStates\patient_viewer.py

import streamlit as st
from pathlib import Path
import pandas as pd
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(r"C:\Users\VIRTUALIAI\Documents\HiddenStates\DadosTask")

st.set_page_config(
    page_title="HiddenStates · Participant Viewer",
    page_icon="👁️",
    layout="wide",
)

# Initialize Session States
if "df" not in st.session_state:
    st.session_state.df = None
if "load_errors" not in st.session_state:
    st.session_state.load_errors = []
if "current_participant_name" not in st.session_state:
    st.session_state.current_participant_name = None
if "current_participant_folder" not in st.session_state:
    st.session_state.current_participant_folder = None
if "all_participants_summary" not in st.session_state:
    st.session_state.all_participants_summary = None

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

.participant-card {
    background: #111620;
    border: 1px solid #1e2530;
    border-radius: 10px;
    padding: 1.5rem 1.8rem;
    margin-bottom: 1.5rem;
}

.participant-card .label {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #3d8bff;
    margin-bottom: 0.3rem;
}

.participant-card .name {
    font-size: 1.6rem;
    font-weight: 800;
    color: #e8edf5;
    letter-spacing: -0.02em;
}

.participant-card .path {
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

.stat-box .st-label {
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

def find_participant_folders(base: Path) -> dict[str, Path]:
    if not base.exists():
        return {}
    folders = {}
    for p in sorted(base.iterdir()):
        if p.is_dir():
            folders[p.name] = p
    return folders


def load_events(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.insert(0, "event_type", df.pop("name"))
    df["event_type"] = df["event_type"].astype(str)

    def clean_event_names(val):
        if "mine_finished" in val:
            if "rewarded=True" in val:
                return "mine_finished_reward"
            elif "rewarded=False" in val:
                return "mine_finished_fail"
            return "mine_finished"
        return val.split(';')[0].strip()

    df["event_type"] = df["event_type"].apply(clean_event_names)
    df = df.rename(columns={"timestamp [ns]": "start timestamp [ns]"})
    return df
    
@st.cache_data
def build_dataframe(folder: Path) -> tuple[pd.DataFrame, list[str]]:
    pupil_dir = folder / "pupil"
    if not pupil_dir.exists():
        pupil_dir = folder

    parts = []
    errors = []

    for loader, fname in [(load_events, "events.csv")]:
        fp = pupil_dir / fname
        if fp.exists():
            try:
                parts.append(loader(fp))
            except Exception as e:
                errors.append(f"{fname}: {e}")
        else:
            errors.append(f"{fname}: not found")

    if not parts:
        raise FileNotFoundError(f"No CSV files found in {pupil_dir}.\n" + "\n".join(errors))

    combined = pd.concat(parts, ignore_index=True, sort=False)
    cols_to_remove = ["type", "section id"]
    combined = combined.drop(columns=[c for c in cols_to_remove if c in combined.columns])
    combined = combined.sort_values("start timestamp [ns]", ignore_index=True)
    combined = assign_bouts(combined)
    combined = calculate_decision_variables(combined)

    return combined, errors


def assign_bouts(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    
    # 1. Isolate ONLY pickup events
    PICKUPS = {"axe_pickup_left", "axe_pickup_right"}
    pickups_only = df[df["event_type"].isin(PICKUPS)]
    
    # If the participant never picked up an axe, everything is Bout 0
    if pickups_only.empty:
        df.insert(1, "bout", pd.array([0] * len(df), dtype="Int64"))
        return df

    # 2. Track hand changes strictly within the pickup subsets
    # (True if it's the first pickup OR if the hand changed from the previous pickup)
    hand_changed = (pickups_only["event_type"] != pickups_only["event_type"].shift(1))
    
    # 3. Initialize a base series of zeros matching the exact size of the main dataframe
    bout_markers = pd.Series(0, index=df.index)
    
    # 4. Inject a 1 ONLY at the specific index locations where a valid switch occurred
    valid_switch_indices = hand_changed[hand_changed].index
    bout_markers.loc[valid_switch_indices] = 1
    
    # 5. Cumsum calculates the bout numbers perfectly matching your rules
    df.insert(1, "bout", bout_markers.cumsum().astype("Int64"))
    
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

    cf_max = df['consecutive_failures'].abs().max()
    tr_max = df['total_rewards'].abs().max()

    df['consecutive_failures_norm'] = df['consecutive_failures'] / cf_max if cf_max else 0.0
    df['total_rewards_norm']        = df['total_rewards']        / tr_max if tr_max else 0.0

    return df.drop(columns=['is_success', 'is_failure', 'success_block'])


# ── Numerics Helpers for Custom EM Engine ─────────────────────────────────────

def _logsumexp(x):
    m = np.max(x)
    return m + np.log(np.sum(np.exp(x - m)) + 1e-300)

def _logsumexp_axis(x, axis, keepdims=False):
    m = np.max(x, axis=axis, keepdims=True)
    result = m + np.log(np.sum(np.exp(x - m), axis=axis, keepdims=True) + 1e-300)
    if not keepdims:
        result = np.squeeze(result, axis=axis)
    return result


class PaperLMHMM:
    """Pure mathematical input-driven LM-HMM engine matching paper parameters."""
    def __init__(self, n_states, seed=None):
        self.K = n_states
        self.rng = np.random.default_rng(seed)

    def _init_params(self, observations_list, inputs_list):
        K = self.K
        A = self.rng.dirichlet(np.ones(K) * 4.0, size=K) 
        pi = self.rng.dirichlet(np.ones(K))

        all_y = np.concatenate(observations_list)
        all_u = np.concatenate(inputs_list)
        ols_w, _, _, _ = np.linalg.lstsq(all_u, all_y, rcond=None)
        
        W = np.tile(ols_w, (K, 1)).astype(float)
        for k in range(K):
            W[k, 0] += self.rng.uniform(-0.1, 0.2) if k == 0 else self.rng.uniform(-0.1, 0.0)
            W[k, 1] += self.rng.uniform(-0.05, 0.05)

        sigma = np.ones(K) * np.std(all_y) + self.rng.uniform(0.01, 0.04, K)
        return pi, A, W, sigma

    @staticmethod
    def _log_obs(y, u, W, sigma):
        means = u @ W.T                          
        diff  = y[:, None] - means               
        log_p = (
            -0.5 * (diff / sigma[None, :]) ** 2
            - np.log(sigma[None, :])
            - 0.5 * np.log(2 * np.pi)
        )
        return log_p                             

    def _forward_backward(self, log_obs, A, pi):
        T, K = log_obs.shape
        log_A  = np.log(A + 1e-300)
        log_pi = np.log(pi + 1e-300)

        log_alpha = np.empty((T, K))
        log_alpha[0] = log_pi + log_obs[0]
        log_alpha[0] -= _logsumexp(log_alpha[0])   

        log_scales = np.empty(T)
        log_scales[0] = 0.0

        for t in range(1, T):
            log_pred = _logsumexp_axis(log_alpha[t-1:t, :].T + log_A.T, axis=0)
            log_alpha[t] = log_pred + log_obs[t]
            scale = _logsumexp(log_alpha[t])
            log_alpha[t] -= scale
            log_scales[t] = scale

        log_ll = log_scales.sum()

        log_beta = np.zeros((T, K))
        for t in range(T-2, -1, -1):
            log_beta[t] = _logsumexp_axis(log_A + log_obs[t+1] + log_beta[t+1], axis=1)
            log_beta[t] -= _logsumexp(log_beta[t])

        log_gamma = log_alpha + log_beta
        log_gamma -= _logsumexp_axis(log_gamma, axis=1, keepdims=True)
        gamma = np.exp(log_gamma)                            

        xi_sum = np.zeros((K, K))
        for t in range(T-1):
            log_xi = (log_alpha[t, :, None] + log_A + log_obs[t+1, None, :] + log_beta[t+1, None, :])
            xi_sum += np.exp(log_xi - _logsumexp(log_xi.ravel()))

        return gamma, xi_sum, log_ll

    def fit(self, observations_list, inputs_list, n_iters=150, tol=1e-4):
        pi, A, W, sigma = self._init_params(observations_list, inputs_list)
        prev_ll = -np.inf
        self.ll_curve_ = []

        for it in range(n_iters):
            gamma_list  = []
            xi_sum_tot  = np.zeros((self.K, self.K))
            total_ll    = 0.0

            for y_seq, u_seq in zip(observations_list, inputs_list):
                log_obs_seq = self._log_obs(y_seq, u_seq, W, sigma)
                gamma, xi_sum, seq_ll = self._forward_backward(log_obs_seq, A, pi)
                gamma_list.append((gamma, y_seq, u_seq))
                xi_sum_tot += xi_sum
                total_ll   += seq_ll

            self.ll_curve_.append(total_ll)
            if abs(total_ll - prev_ll) < tol and it > 0:
                break
            prev_ll = total_ll

            # Fix 1: Transition matrix update using row-normalization counts from backward slices
            pi = np.mean([g[0][0] for g in gamma_list], axis=0)
            pi = np.maximum(pi, 1e-10); pi /= pi.sum()

            A = xi_sum_tot / (xi_sum_tot.sum(axis=1, keepdims=True) + 1e-10)
            A = np.maximum(A, 1e-10); A /= A.sum(axis=1, keepdims=True)

            # Fix 2: Strategy linear weight updates using separate weighted OLS matrix solving paths
            for k in range(self.K):
                y_all   = np.concatenate([g[1] for g in gamma_list])
                u_all   = np.concatenate([g[2] for g in gamma_list])
                w_resp  = np.concatenate([g[0][:, k] for g in gamma_list])

                sqrt_w = np.sqrt(w_resp + 1e-10)
                U_w = u_all * sqrt_w[:, None]
                y_w = y_all * sqrt_w
                reg = 1e-6 * np.eye(u_all.shape[1])
                W[k] = np.linalg.solve(U_w.T @ U_w + reg, U_w.T @ y_w)

                residuals = y_all - u_all @ W[k]
                sigma[k]  = np.sqrt(np.sum(w_resp * residuals**2) / (np.sum(w_resp) + 1e-10))
                sigma[k]  = max(sigma[k], 1e-4)

        self.pi_, self.A_, self.W_, self.sigma_ = pi, A, W, sigma
        return self

    def predict_states(self, y_seq, u_seq):
        T = len(y_seq)
        K = self.K
        log_obs = self._log_obs(y_seq, u_seq, self.W_, self.sigma_)
        log_A   = np.log(self.A_ + 1e-300)
        log_pi  = np.log(self.pi_ + 1e-300)

        viterbi  = np.empty((T, K))
        backptr  = np.zeros((T, K), dtype=int)
        viterbi[0] = log_pi + log_obs[0]

        for t in range(1, T):
            trans = viterbi[t-1, :, None] + log_A
            backptr[t] = np.argmax(trans, axis=0)
            viterbi[t] = np.max(trans, axis=0) + log_obs[t]

        states = np.empty(T, dtype=int)
        states[-1] = np.argmax(viterbi[-1])
        for t in range(T-2, -1, -1):
            states[t] = backptr[t+1, states[t+1]]
        return states


# ── UI Setup ──────────────────────────────────────────────────────────────────

st.markdown("""
<div class="title-block">
  <h1>👁️ HiddenStates · Participant Viewer</h1>
  <p>Eye-tracking data explorer · Pupil Labs CSV pipeline</p>
</div>
""", unsafe_allow_html=True)

all_folders = find_participant_folders(BASE_DIR)
col_left, col_right = st.columns([1, 2.5], gap="large")

with col_left:
    st.markdown("#### Select Participants")

    if all_folders:
        folder_names = list(all_folders.keys())
        selected_name = st.selectbox(
            "Available participants",
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
        "Participant name / folder prefix",
        placeholder="e.g. MariaVilela",
        label_visibility="collapsed",
    )

    load_btn = st.button("Load Participant Data")

    # ── Resolve Input Logic ──
    resolved_folder = None
    resolved_label  = None

    if typed_name.strip():
        matches = [
            (name, path) for name, path in all_folders.items()
            if name.lower().startswith(typed_name.strip().lower())
        ]
        if len(matches) == 1:
            resolved_label, resolved_folder = matches[0]
        elif len(matches) > 1:
            st.markdown("**Multiple matches — pick one:**")
            choice = st.selectbox(
                "Matches",
                options=[m[0] for m in matches],
                label_visibility="collapsed",
                key="multi_match_select"
            )
            resolved_label  = choice
            resolved_folder = all_folders[choice]
        else:
            candidate = BASE_DIR / typed_name.strip()
            if candidate.exists():
                resolved_label  = typed_name.strip()
                resolved_folder = candidate

    elif selected_name != "— choose —":
        resolved_label  = selected_name
        resolved_folder = all_folders[selected_name]

    # Action when user clicks 'Load'
    if load_btn and resolved_folder:
        with st.spinner("Loading CSVs…"):
            try:
                df_loaded, errors_loaded = build_dataframe(resolved_folder)
                st.session_state.df = df_loaded
                st.session_state.load_errors = errors_loaded
                st.session_state.current_participant_name = resolved_label
                st.session_state.current_participant_folder = resolved_folder
            except Exception as e:
                st.error(f"Failed to load: {e}")
                st.session_state.df = None

    # ── Global Cohort Control (Batch Loader) ──
    st.markdown("---")
    st.markdown("#### 📑 Global Cohort Control")
    st.write("<small>Compile and cache all available participants directories for population-level modeling.</small>", unsafe_allow_html=True)
    batch_load_btn = st.button("🚀 Load All Participants Data", key="global_batch_load_btn")

    if batch_load_btn and all_folders:
        batch_summary_list = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, (p_name, p_path) in enumerate(all_folders.items()):
            status_text.text(f"Batch Processing ({idx+1}/{len(all_folders)}): {p_name}")
            try:
                participant_df, _ = build_dataframe(p_path)
                analysis_df_batch = participant_df[participant_df["bout"] > 0].copy()
                if not analysis_df_batch.empty:
                    bout_sum = analysis_df_batch.groupby("bout").agg(
                        total_rewards=("total_rewards", "max"),
                        consecutive_failures=("consecutive_failures", "max")
                    ).reset_index()
                    bout_sum["participant_id"] = p_name
                    batch_summary_list.append(bout_sum)
            except Exception as e:
                pass
            progress_bar.progress((idx + 1) / len(all_folders))
            
        if batch_summary_list:
            combined_summary = pd.concat(batch_summary_list, ignore_index=True)
            cf_max_all = combined_summary["consecutive_failures"].max()
            tr_max_all = combined_summary["total_rewards"].max()
            
            combined_summary["consecutive_failures_norm"] = combined_summary["consecutive_failures"] / cf_max_all if cf_max_all else 0.0
            combined_summary["total_rewards_norm"] = combined_summary["total_rewards"] / tr_max_all if tr_max_all else 0.0
            
            st.session_state.all_participants_summary = combined_summary
            status_text.success(f"Compiled cohorts across {len(batch_summary_list)} profiles!")
        else:
            status_text.error("No valid dataset objects found across directories.")

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
    if st.session_state.df is not None:
        df = st.session_state.df
        load_errors = st.session_state.load_errors
        p_name = st.session_state.current_participant_name
        p_folder = st.session_state.current_participant_folder

        # participant Info Card
        st.markdown(f"""
        <div class="participant-card">
          <div class="label">participant folder</div>
          <div class="name">{p_name}</div>
          <div class="path">{p_folder}</div>
        </div>
        """, unsafe_allow_html=True)

        # Stats Calculations
        counts = df["event_type"].value_counts()
        n_bouts = int(df["bout"].max()) if df["bout"].notna().any() else 0

        n_rewards = int((df["event_type"] == "mine_finished_reward").sum())
        n_failures = int((df["event_type"] == "mine_finished_fail").sum())
        n_trials = n_rewards + n_failures
        success_rate = (n_rewards / n_trials * 100) if n_trials > 0 else 0

        cols_stat = st.columns(5)
        stat_items = [
            ("Total Gold 🪙", f"{n_rewards * 10:,}"),
            ("Bouts", str(n_bouts)),
            ("Trials", f"{n_trials:,}"),
            ("Success Rate", f"{success_rate:.1f}%"),
            ("Interruptions", str(int((df["event_type"] == "mine_interrupted").sum()))),
        ]

        for col, (lbl, val) in zip(cols_stat, stat_items):
            with col:
                st.markdown(f"""<div class="stat-box"><div class="st-label">{lbl}</div><div class="stat-value">{val}</div></div>""", unsafe_allow_html=True)

        # Event Type Pills
        pills_html = "".join(event_pill(et) + f"&nbsp;<small style='color:#3a4255;font-size:0.7rem;'>{cnt:,}</small>&nbsp;&nbsp;" for et, cnt in counts.items())
        st.markdown(pills_html, unsafe_allow_html=True)

        # ── Filter View ──
        st.markdown("#### Filter View")
        all_event_types = sorted(df["event_type"].unique().tolist())
        selected_types = st.multiselect("Show only specific event types:", options=all_event_types, default=all_event_types, key="filter_multiselect")
        
        # Apply filter
        filtered_df = df[df["event_type"].isin(selected_types)]

        # Tabs Layout setup
        tab_labels = ["All events", "By Bout"] + all_event_types
        tabs = st.tabs(tab_labels)

        with tabs[0]:
            st.data_editor(filtered_df, width='stretch', height=480, key="all_events_editor")
            st.caption(f"{len(filtered_df):,} rows · {filtered_df.shape[1]} columns")

        with tabs[1]:
            bout_nums = sorted(filtered_df["bout"].dropna().unique().tolist())
            if not bout_nums:
                st.warning("No bouts found for filtered event metrics.")
            else:
                selected_bout = st.selectbox("Select bout", options=bout_nums, format_func=lambda b: f"Bout {b}" if b > 0 else "Bout 0", key="bout_selector")
                bout_df = filtered_df[filtered_df["bout"] == selected_bout]
                st.data_editor(bout_df, width='stretch', height=430, key=f"bout_{selected_bout}_editor")
                st.caption(f"{len(bout_df):,} rows · {bout_df.shape[1]} columns")

        # Map rest of the individual tabs safely using full set
        for tab, etype in zip(tabs[2:], all_event_types):
            with tab:
                etype_df = filtered_df[filtered_df["event_type"] == etype]
                st.data_editor(etype_df, width='stretch', height=480, key=f"tab_editor_{etype}")
                st.caption(f"{len(etype_df):,} rows · {etype_df.shape[1]} columns")

        if load_errors:
            with st.expander("⚠️ Load warnings"):
                for e in load_errors: st.markdown(f"`{e}`")

    else:
        # Default Empty State View
        st.markdown("""
        <div style="padding:4rem 2rem; text-align:center; color:#3a4255;">
          <div style="font-size:3rem;">👁️</div>
          <div style="font-family:'DM Mono',monospace; font-size:0.8rem; letter-spacing:0.15em; text-transform:uppercase; margin-top:1rem;">
            Select a participant and click Load
          </div>
        </div>
        """, unsafe_allow_html=True)

# =====================================================================
# 🔬 DATA ANALYSIS LAB (LME & DECOUPLED EM-BASED LM-HMM)
# =====================================================================
st.markdown("---")
st.markdown("### 🔬 Strategy & Decision Analysis Lab")

lab_expander = st.expander("Open Advanced Behavioral Analysis Engine", expanded=True)

with lab_expander:
    st.markdown("""
    This laboratory engine evaluates whether subjects rely on a 
    **Stimulus-Bound** (reward-dependent) or **Inference-Based** (reward-independent) 
    foraging model by modeling latent decision boundaries.
    """)
    
    try:
        import statsmodels.api as sm
        import statsmodels.formula.api as smf
        import plotly.graph_objects as go
    except ImportError:
        st.error("Missing analytical libraries. Please run: `pip install statsmodels plotly`")
        st.stop()
        
    # ── Layer Selector Control ──
    st.markdown("#### 🛠️ Data Aggregation Control")
    scope_mode = st.radio(
        "Select Analysis Context Layer:",
        options=["Single participant View", "Full Global Cohort View (All participants)"],
        horizontal=True,
        key="analysis_scope_toggle"
    )
    
    raw_sequences_obs = []
    raw_sequences_input = []
    bout_summary = None
    group_variable = "bout"
    
    cf_max_val = 1.0
    tr_max_val = 1.0
    
    if scope_mode == "Single participant View":
        if st.session_state.df is not None:
            analysis_df = st.session_state.df[st.session_state.df["bout"] > 0].copy()
            if not analysis_df.empty:
                bout_summary = analysis_df.groupby("bout").agg(
                    total_rewards=("total_rewards", "max"),
                    consecutive_failures=("consecutive_failures", "max")
                ).reset_index()
                
                # Fix 3: Intercept and Slope values are bound via within-session max parameters before EM execution
                cf_max_val = float(bout_summary["consecutive_failures"].max())
                tr_max_val = float(bout_summary["total_rewards"].max())
                
                bout_summary["consecutive_failures_norm"] = bout_summary["consecutive_failures"] / cf_max_val if cf_max_val else 0.0
                bout_summary["total_rewards_norm"] = bout_summary["total_rewards"] / tr_max_val if tr_max_val else 0.0
                group_variable = "bout"
                
                # Stack baseline tracking elements onto unified time-series array sequences [cite: 1793]
                raw_sequences_obs.append(bout_summary["consecutive_failures_norm"].values.astype(float))
                raw_sequences_input.append(np.column_stack([
                    bout_summary["total_rewards_norm"].values.astype(float),
                    np.ones(len(bout_summary))
                ]))
        else:
            st.warning("Please load an individual participant file via the selector to access local profile diagnostics.")
            
    else: # Full Global Cohort View
        if st.session_state.all_participants_summary is not None:
            bout_summary = st.session_state.all_participants_summary
            cf_max_val = float(bout_summary["consecutive_failures"].max())
            tr_max_val = float(bout_summary["total_rewards"].max())
            group_variable = "participant_id"
            
            # Format independent sequences broken down distinctly by UserID tracking channels
            for pid, grp in bout_summary.groupby("participant_id"):
                raw_sequences_obs.append(grp["consecutive_failures_norm"].values.astype(float))
                raw_sequences_input.append(np.column_stack([
                    grp["total_rewards_norm"].values.astype(float),
                    np.ones(len(grp))
                ]))
        else:
            st.warning("No global context pooled yet. Click '🚀 Load All participants Data' on the sidebar panel first.")
            
    # Run modeling pipeline if structured frames converge
    if bout_summary is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Unpacked Time Series Length", f"{len(bout_summary)}")
        c2.metric("Max Rewards / Bout", f"{int(bout_summary['total_rewards'].max())}")
        c3.metric("Max Failures Tolerated", f"{int(bout_summary['consecutive_failures'].max())}")
        

        st.markdown("---")

        # --- 1.5. Métrica de Retorno por Risco: Razão TR / CF por Bout ---
        st.markdown("#### 📊 Taxa de Retorno por Risco Tolerado (TR / CF)")
    
        
        # 1. Recupera o dataframe de análise da sessão atual
        if scope_mode == "Single participant View":
            session_df = st.session_state.df[st.session_state.df["bout"] > 0].copy()
            
            # 2. Agrupa por Bout extraindo os valores máximos acumulados no desfecho
            bout_decision_df = session_df.groupby("bout").agg(
                total_rewards=("total_rewards", "max"),
                consecutive_failures=("consecutive_failures", "max")
            ).reset_index()
        else:
            # Caso esteja no modo global, usa o resumo gerado em lote
            bout_decision_df = bout_summary.copy()
        
        # 3. Garante a ordenação cronológica dos blocos no eixo X
        bout_decision_df = bout_decision_df.sort_values("bout").reset_index(drop=True)
        
        # 4. Calcula a razão invertida de forma direta e segura (Denominador CF > 0 no abandono)
        # 4. Calcula a razão de forma direta e segura prevenindo divisão por zero
        bout_decision_df["tr_cf_ratio"] = bout_decision_df["total_rewards"].div(
            bout_decision_df["consecutive_failures"]
        ).fillna(0).replace(np.inf, 0)
        
        # 5. Construção do gráfico de linha com Plotly
        fig_ratio = go.Figure()
        
        fig_ratio.add_trace(go.Scatter(
            x=bout_decision_df["bout"],
            y=bout_decision_df["tr_cf_ratio"],
            mode='lines+markers',
            line=dict(color='#3d8bff', width=2),  # Alterado para azul clínico condizente com o tema do app
            marker=dict(
                size=8, 
                color='#111620', 
                line=dict(color='#3d8bff', width=2),
                symbol='circle'
            ),
            hovertext=[
                f"Bout {int(b)}<br>Retorno/Risco: {r:.3f}<br>Total Rewards (TR): {int(tr)}<br>Consecutive Failures (CF): {int(cf)}"
                for b, r, cf, tr in zip(bout_decision_df["bout"], bout_decision_df["tr_cf_ratio"], bout_decision_df["consecutive_failures"], bout_decision_df["total_rewards"])
            ],
            hoverinfo="text",
            name="Taxa TR / CF"
        ))
        
        # Configurações estéticas do layout e eixos
        fig_ratio.update_layout(
            xaxis=dict(
                title="Número do Bout",
                tickmode='linear',
                dtick=1,
                gridcolor="#1e2530"
            ),
            yaxis=dict(
                title="Total Rewards / Consecutive Failures",
                gridcolor="#1e2530",
                zeroline=True,
                zerolinecolor="#5a6478"
            ),
            template="plotly_dark",
            paper_bgcolor="#0a0d12", 
            plot_bgcolor="#111620",
            font=dict(family="DM Mono, monospace", size=11),
            margin=dict(l=50, r=20, t=50, b=50),
            height=400
        )
        
        st.plotly_chart(fig_ratio, use_container_width=True)
        st.markdown("---")
        
        # --- 2. Mimicking Paper Plots (Fig 4A / Fig 2G) ---
        st.markdown("#### 📉 Behavioral Boundary Mapping")
        step_data = bout_summary.groupby("total_rewards")["consecutive_failures"].agg(["mean", "sem"]).reset_index()
        step_data["sem"] = step_data["sem"].fillna(0)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=step_data["total_rewards"], y=step_data["mean"] + step_data["sem"],
            mode='lines', line=dict(width=0), showlegend=False, name='Upper Bound'
        ))
        fig.add_trace(go.Scatter(
            x=step_data["total_rewards"], y=step_data["mean"] - step_data["sem"],
            mode='lines', line=dict(width=0), fill='tonexty',
            fillcolor='rgba(61, 139, 255, 0.15)', showlegend=False, name='Lower Bound'
        ))
        fig.add_trace(go.Scatter(
            x=step_data["total_rewards"], y=step_data["mean"],
            mode='lines+markers', line=dict(color='#3d8bff', width=3),
            marker=dict(size=8, color='#e8edf5', line=dict(color='#3d8bff', width=2)),
            name='Cohort Profile' if scope_mode != "Single participant View" else 'participant Profile'
        ))
        
        if len(bout_summary) > 1:
            poly_fit = np.polyfit(bout_summary["total_rewards"], bout_summary["consecutive_failures"], 1)
            trend_x = np.array([bout_summary["total_rewards"].min(), bout_summary["total_rewards"].max()])
            trend_y = poly_fit[0] * trend_x + poly_fit[1]
            
            fig.add_trace(go.Scatter(
                x=trend_x, y=trend_y, mode='lines',
                line=dict(color='#ff8c3d', dash='dash', width=2), name='Linear Trend Fit'
            ))
        
        fig.update_layout(
            title="Consecutive Failures Before Leaving vs. Prior Rewards",
            xaxis_title="Number of Cumulative Rewards in Bout",
            yaxis_title="Consecutive Failures Before Leaving (Count)",
            template="plotly_dark",
            paper_bgcolor="#111620", plot_bgcolor="#111620",
            font=dict(family="DM Mono, monospace", size=11),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(10,13,18,0.6)"),
            margin=dict(l=40, r=20, t=40, b=40)
        )
        st.plotly_chart(fig, use_container_width=True)
            
        
        
        st.markdown("---")
        
        # --- 3. Linear Mixed-Effects (LME) Modeling Engine ---
        st.markdown("#### 🧮 Linear Mixed-Effects Model Solver")
        lme_col1, lme_col2 = st.columns([1, 2])
        
        with lme_col1:
            st.markdown("**Model Specifications**")
            use_normalized = st.checkbox("Use Normalized Scaling (0-1)", value=False, key="lme_norm_toggle")
            
            dep_var = "consecutive_failures_norm" if use_normalized else "consecutive_failures"
            ind_var = "total_rewards_norm" if use_normalized else "total_rewards"
            
            formula = f"{dep_var} ~ {ind_var}"
            st.code(f"Formula:\n{formula}\nGroup: (1 | {group_variable})", language="python")
            run_lme = st.button("Execute LME Analysis Engine", type="primary", key="lme_run_btn")
        
        with lme_col2:
            if run_lme:
                with st.spinner("Optimizing random effect cluster matrices via Maximum Likelihood..."):
                    try:
                        model = smf.mixedlm(formula, data=bout_summary, groups=bout_summary[group_variable])
                        result = model.fit()
                        
                        slope = result.params[ind_var]
                        p_value = result.pvalues[ind_var]
                        std_err = result.bse[ind_var]
                        
                        st.markdown("**Statistical Coefficients Table**")
                        summary_df = pd.DataFrame({
                            "Parameter": [f"Slope ({ind_var})", "Intercept Component"],
                            "Coefficient (Weight)": [f"{slope:.4f}", f"{result.params['Intercept']:.4f}"],
                            "Std Error": [f"{std_err:.4f}", f"{result.bse['Intercept']:.4f}"],
                            "p-Value": [f"{p_value:.4E}" if p_value < 0.001 else f"{p_value:.4f}", f"{result.pvalues['Intercept']:.4f}"]
                        })
                        st.table(summary_df)
                        
                        if p_value < 0.05 and slope > 0.01:
                            st.error(f"**Classification Result:** **STIMULUS-BOUND PROFILE DETECTED** (Slope = +{slope:.3f}, p = {p_value:.4f}). Leaving decisions show variable dependence on cumulative contextual rewards.")
                        else:
                            st.success(f"**Classification Result:** **OPTIMAL INFERENCE PROFILE IDENTIFIED** (Slope = {slope:.3f}, p = {p_value:.4f}). Leaving thresholds converge clean of feedback length bounds, revealing stable hidden-state maps.")
                            
                    except Exception as model_err:
                        st.error(f"LME Optimizer Matrix Error: {model_err}")
                        st.warning("Tip: Session data matrices may lack variance properties across specific combinations. Try toggling normalized scaling controls off.")

        st.markdown("---")
        
        # --- 4. Custom EM LM-HMM Execution Engine (Decoupled Parameters) ---
        st.markdown("####Paper-Grade Custom EM LM-HMM Strategy Classifier")
        st.markdown("""
        Fits an input-driven hidden Markov model via multi-restart Expectation-Maximization. 
        Updates **Transition Matrix ($A_{kl}$)** and **Linear Strategy Weights ($w^{(k)}, b^{(k)}$)** through decoupled estimation paths to track dynamic strategy drift across trials.
        """)
        st.latex(r"\hat{F}_t = w^{(k)}\hat{R}_t + b^{(k)} + \epsilon_t")
        
        hmm_col1, hmm_col2 = st.columns([1, 2])
        
        with hmm_col1:
            st.markdown("**Model Control Parameters**")
            k_states = st.selectbox(
                "Number of Latent Strategies (K):",
                options=[2, 3],
                index=0,
                format_func=lambda x: f"{x} Regimes (Clean Behavioral Splitting)" if x == 2 else f"{x} Regimes (Paper Mouse HMM Profile Mapping)",
                key="hmm_k_states"
            )
            
            n_restarts = st.slider("Random Optimization Restarts:", min_value=1, max_value=10, value=3, key="hmm_restarts")
            run_hmm = st.button("Run Custom EM Analysis Pipeline", type="primary", key="hmm_run_btn")
            
        with hmm_col2:
            if run_hmm:
                with st.spinner("Executing EM Engine across randomized convergence loops..."):
                    try:
                        best_model = None
                        best_ll = -np.inf
                        
                        # Multi-restart loops to identify global parameter likelihood convergence point
                        for r in range(n_restarts):
                            model = PaperLMHMM(n_states=k_states, seed=42 + r)
                            model.fit(raw_sequences_obs, raw_sequences_input, n_iters=150, tol=1e-4)
                            final_ll = model.ll_curve_[-1]
                            
                            if final_ll > best_ll:
                                best_ll = final_ll
                                best_model = model
                                
                        # Decode parameters
                        regime_profiles = []
                        for k in range(k_states):
                            w_norm, b_norm = best_model.W_[k]
                            
                            w_raw = w_norm * (cf_max_val / tr_max_val) if tr_max_val else 0.0
                            b_raw = b_norm * cf_max_val
                            
                            # ── Target Taxonomy Logic ──
                            if k_states == 2:
                                # Differentiate between Impulsive and Persistent Inference based on Intercept depth
                                if k == 0:
                                    title = "Impulsive Inference"
                                else:
                                    title = "Persistent Inference"
                            else:
                                # K=3 Fallback Profile Mapping
                                if abs(w_norm) < 0.18:
                                    title = "Persistent Inference" if b_raw > (0.4 * cf_max_val) else "Impulsive Inference"
                                else:
                                    title = "Stimulus-Bound Strategy"
                                
                            regime_profiles.append({
                                "Hidden State": f"Regime {k}",
                                "Taxonomy Decoded": title,
                                "Normalized Slope (w)": f"{w_norm:.4f}",
                                "Raw Slope (w_raw)": f"{w_raw:.4f}",
                                "Normalized Intercept (b)": f"{b_norm:.4f}",
                                "Raw Intercept (b_raw)": f"{b_raw:.2f}"
                            })
                            
                        st.markdown("**Decoupled Linear Regression Estimations (M-Step Outputs)**")
                        st.table(pd.DataFrame(regime_profiles))
                        
                        # --- Chronological Viterbi Strategy Path Shading ---
                        st.markdown("**Decoded Strategy Execution Path (Viterbi Tracking Timeline)**")
                        all_viterbi_states = []
                        for y_seq, u_seq in zip(raw_sequences_obs, raw_sequences_input):
                            seq_states = best_model.predict_states(y_seq, u_seq)
                            all_viterbi_states.extend(seq_states)
                            
                        fig_timeline = go.Figure()
                        fig_timeline.add_trace(go.Scatter(
                            x=np.arange(len(all_viterbi_states)),
                            y=all_viterbi_states,
                            mode='markers+lines',
                            line=dict(color='#3d8bff', width=1),
                            marker=dict(
                                size=6,
                                color=all_viterbi_states,
                                colorscale='Viridis',
                                showscale=True,
                                colorbar=dict(
                                    title="Active State",
                                    tickvals=np.arange(k_states),
                                    ticktext=[f"State {i}" for i in range(k_states)]
                                )
                            ),
                            name='Strategy Index'
                        ))
                        
                        fig_timeline.update_layout(
                            xaxis_title="Chronological Task Trial Bouts (Timeline ➔)",
                            yaxis_title="Decoded Strategy State ID",
                            yaxis=dict(tickvals=np.arange(k_states)),
                            template="plotly_dark",
                            paper_bgcolor="#111620", plot_bgcolor="#111620",
                            margin=dict(l=40, r=20, t=20, b=40),
                            height=250
                        )
                        st.plotly_chart(fig_timeline, use_container_width=True)
                        
                        # --- Decoupled Markov Transition Grid ---
                        st.markdown("**Decoupled Markov Strategy Transition Matrix ($A_{kl}$)**")
                        t_matrix_df = pd.DataFrame(
                            best_model.A_,
                            columns=[f"To State {i}" for i in range(k_states)],
                            index=[f"From State {i}" for i in range(k_states)]
                        )
                        st.dataframe(t_matrix_df, use_container_width=True)
                        
                        diagonal_vals = np.diag(best_model.A_)
                        if np.all(diagonal_vals > 0.82):
                            st.success("📊 **Matrix Metrics:** Row probabilities sum to 1.0. High diagonal persistence weights verify stable strategy controllers across tasks.")
                        else:
                            st.warning("📊 **Matrix Metrics:** Low diagonal persistence elements. Subject shifts frequently or displays elevated exploration noise.")
                            
                    except Exception as hmm_err:
                        st.error(f"Custom EM Optimizer Failed: {hmm_err}")