
import pandas as pd
import numpy as np
import argparse
import os
import warnings
warnings.filterwarnings('ignore')

import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.linear_model import LogisticRegressionCV
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline

from hmmlearn import hmm

# ── Config ────────────────────────────────────────────────────────────────────
N_HMM_STATES   = 2    # 2 strategies: inference-based vs stimulus-bound
HMM_N_ITER     = 200
RANDOM_STATE    = 42

parser = argparse.ArgumentParser()
parser.add_argument("--input", default="/Users/matildegarcia/Desktop/Lebiom/PIC/trials_with_decision_vars.csv")
args = parser.parse_args()

INPUT_PATH = args.input
OUT_DIR    = os.path.dirname(os.path.abspath(INPUT_PATH))
PLOT_DIR   = os.path.join(OUT_DIR, "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

print(f"Loading: {INPUT_PATH}")
df = pd.read_csv(INPUT_PATH)
print(f"  {len(df)} trials | {df['participant'].nunique()} participant(s) | "
      f"{df['bout_number'].nunique()} bouts\n")

# ── Shared feature sets ───────────────────────────────────────────────────────
DECISION_VARS   = ['consecutive_failures', 'cumulative_rewards']
GAZE_FEATURES   = ['gaze_mean_x', 'gaze_mean_y', 'gaze_std_x', 'gaze_std_y',
                    'gaze_mean_az', 'gaze_mean_el',
                    'n_fixations_in_window', 'n_blinks_in_window']

scaler = StandardScaler()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Logistic Regression
# Predict: is this trial the last before a switch?
# Predictors: consecutive_failures, cumulative_rewards
# ═══════════════════════════════════════════════════════════════════════════════
print("STEP 3 — Logistic Regression")

X_log = df[DECISION_VARS].values
y_log = df['is_last_before_switch'].values

X_log_scaled = scaler.fit_transform(X_log)

# Cross-validated logistic regression
# If multiple participants, use Leave-One-Participant-Out
n_participants = df['participant'].nunique()

if n_participants > 1:
    groups = df['participant'].values
    cv = LeaveOneGroupOut()
    cv_kwargs = dict(groups=groups)
else:
    # Single participant: leave-one-bout-out
    groups = df['bout_number'].values
    cv = LeaveOneGroupOut()
    cv_kwargs = dict(groups=groups)

model_log = LogisticRegressionCV(
    Cs=10, cv=5, penalty='l2',
    class_weight='balanced',   # handles the imbalance (few switches vs many trials)
    solver='lbfgs', max_iter=1000,
    random_state=RANDOM_STATE
)
model_log.fit(X_log_scaled, y_log)

# Predict probabilities for each trial
y_pred_prob = model_log.predict_proba(X_log_scaled)[:, 1]
y_pred      = model_log.predict(X_log_scaled)

try:
    auc = roc_auc_score(y_log, y_pred_prob)
except Exception:
    auc = np.nan

coef_df = pd.DataFrame({
    'predictor':   DECISION_VARS,
    'coefficient': model_log.coef_[0],
    'odds_ratio':  np.exp(model_log.coef_[0])
})
print(coef_df.to_string(index=False))
print(f"\n  ROC-AUC: {auc:.3f}")

# Save trial-level predictions
df['switch_prob'] = y_pred_prob
df['switch_pred'] = y_pred

coef_df.to_csv(os.path.join(OUT_DIR, "results_logistic_regression.csv"), index=False)

# Plot: coefficients
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

axes[0].bar(DECISION_VARS, model_log.coef_[0], color=['#4C72B0', '#DD8452'])
axes[0].axhline(0, color='black', linewidth=0.8)
axes[0].set_title("Logistic Regression Coefficients\n(predicting switch decision)")
axes[0].set_ylabel("Coefficient (standardised)")

# Plot: switch probability over trials
axes[1].plot(df['trial'], df['switch_prob'], marker='o', color='#4C72B0', linewidth=1.5)
axes[1].scatter(df.loc[df['is_last_before_switch']==1, 'trial'],
                df.loc[df['is_last_before_switch']==1, 'switch_prob'],
                color='red', zorder=5, label='Actual switch', s=80)
axes[1].set_xlabel("Trial")
axes[1].set_ylabel("P(switch)")
axes[1].set_title("Predicted Switch Probability per Trial")
axes[1].legend()

plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "step3_logistic_regression.png"), dpi=150)
plt.close()
print(f"  Plot saved → plots/step3_logistic_regression.png\n")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — LM-HMM: Identify Behavioral Strategies
# Observations: [consecutive_failures, cumulative_rewards] at each switch point
# Hidden states: latent strategies (e.g. inference-based vs stimulus-bound)
# ═══════════════════════════════════════════════════════════════════════════════

print("STEP 4 — LM-HMM: Behavioral Strategy Identification")


# HMM operates on the bout-level (one observation per bout = conditions at switch)
bout_summary = (
    df.groupby(['participant', 'bout_number'])
    .agg(
        failures_at_switch   = ('consecutive_failures', 'last'),
        rewards_at_switch    = ('cumulative_rewards',   'last'),
        bout_length          = ('trial',                 'count'),
        n_rewards_in_bout    = ('rewarded',              'sum'),
        level                = ('level',                 'first'),
    )
    .reset_index()
)

print(f"  Bout-level summary ({len(bout_summary)} bouts):")
print(bout_summary[['bout_number', 'failures_at_switch', 'rewards_at_switch',
                     'bout_length', 'n_rewards_in_bout']].to_string(index=False))

# Prepare observation sequence
obs_cols = ['failures_at_switch', 'rewards_at_switch']
X_hmm = bout_summary[obs_cols].values.astype(float)
X_hmm_scaled = scaler.fit_transform(X_hmm)

# Fit Gaussian HMM
# Note: with pilot data (5 bouts) this is illustrative.
# With 20-25 participants you'll pass lengths= for each participant's sequence.
lengths = bout_summary.groupby('participant').size().values.tolist()

model_hmm = hmm.GaussianHMM(
    n_components=N_HMM_STATES,
    covariance_type='full',
    n_iter=HMM_N_ITER,
    random_state=RANDOM_STATE,
    verbose=False
)
model_hmm.fit(X_hmm_scaled, lengths=lengths)
hidden_states = model_hmm.predict(X_hmm_scaled, lengths=lengths)
log_likelihood = model_hmm.score(X_hmm_scaled, lengths=lengths)

bout_summary['hmm_state'] = hidden_states

# Label states by their mean consecutive_failures (high = inference-based)
state_means = bout_summary.groupby('hmm_state')['failures_at_switch'].mean()
inference_state = state_means.idxmax()
state_labels = {
    s: ('inference-based' if s == inference_state else 'stimulus-bound')
    for s in range(N_HMM_STATES)
}
bout_summary['strategy'] = bout_summary['hmm_state'].map(state_labels)

print(f"\n  HMM log-likelihood: {log_likelihood:.2f}")
print("\n  State assignments:")
print(bout_summary[['bout_number', 'failures_at_switch', 'rewards_at_switch',
                     'hmm_state', 'strategy']].to_string(index=False))

print("\n  State means (what each strategy looks like on average):")
print(bout_summary.groupby('strategy')[obs_cols].mean().round(2))

# Merge state labels back to trial-level df
df = df.merge(
    bout_summary[['participant', 'bout_number', 'hmm_state', 'strategy']],
    on=['participant', 'bout_number'], how='left'
)

bout_summary.to_csv(os.path.join(OUT_DIR, "results_hmm_states.csv"), index=False)

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

colors = ['#4C72B0', '#DD8452']
for state in range(N_HMM_STATES):
    mask = bout_summary['hmm_state'] == state
    axes[0].scatter(
        bout_summary.loc[mask, 'failures_at_switch'],
        bout_summary.loc[mask, 'rewards_at_switch'],
        label=state_labels[state], color=colors[state], s=100, zorder=3
    )
axes[0].set_xlabel("Consecutive Failures at Switch")
axes[0].set_ylabel("Cumulative Rewards at Switch")
axes[0].set_title("HMM States in Decision-Variable Space")
axes[0].legend()

# State sequence over bouts
axes[1].step(bout_summary['bout_number'], bout_summary['hmm_state'],
             where='post', linewidth=2, color='#4C72B0')
axes[1].scatter(bout_summary['bout_number'], bout_summary['hmm_state'],
                c=[colors[s] for s in bout_summary['hmm_state']], s=100, zorder=3)
axes[1].set_yticks([0, 1])
axes[1].set_yticklabels([state_labels[0], state_labels[1]])
axes[1].set_xlabel("Bout Number")
axes[1].set_title("Strategy Sequence Across Session")

plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "step4_hmm_strategies.png"), dpi=150)
plt.close()
print(f"\n  Plot saved → plots/step4_hmm_strategies.png\n")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — GLMs: Decode Decision Variables from Eye-Tracking
# Can we predict consecutive_failures / cumulative_rewards from gaze alone?
# Crucial control: orthogonalise decision vars against reward outcome first
# ═══════════════════════════════════════════════════════════════════════════════

print("STEP 5 — GLM Decoding of Decision Variables from Eye-Tracking")

# Drop rows with missing gaze features
df_glm = df.dropna(subset=GAZE_FEATURES + DECISION_VARS).copy()
print(f"  Trials with complete gaze data: {len(df_glm)}")

# ── 5a. Orthogonalise decision variables against reward outcome ───────────────
# This removes the variance in consecutive_failures / cumulative_rewards that
# is simply explained by whether the last trial was rewarded or not.
# What remains is the "hidden" cognitive computation.

from sklearn.linear_model import LinearRegression

def orthogonalise(y, confound):
    """Regress confound out of y, return residuals."""
    X_conf = confound.reshape(-1, 1)
    resid = y - LinearRegression().fit(X_conf, y).predict(X_conf)
    return resid

reward_binary = df_glm['rewarded'].astype(int).values

df_glm['consec_fail_orth']  = orthogonalise(df_glm['consecutive_failures'].values,  reward_binary)
df_glm['cum_rewards_orth']  = orthogonalise(df_glm['cumulative_rewards'].values,     reward_binary)

print("  Decision variables orthogonalised against reward outcome.")

# ── 5b. GLM: predict each decision variable from gaze ────────────────────────
X_gaze = df_glm[GAZE_FEATURES].values
X_gaze_scaled = scaler.fit_transform(X_gaze)

targets = {
    'consecutive_failures (raw)':           df_glm['consecutive_failures'].values,
    'cumulative_rewards (raw)':             df_glm['cumulative_rewards'].values,
    'consecutive_failures (orthogonalised)': df_glm['consec_fail_orth'].values,
    'cumulative_rewards (orthogonalised)':   df_glm['cum_rewards_orth'].values,
}

glm_results = []

fig, axes = plt.subplots(2, 2, figsize=(12, 9))
axes = axes.flatten()

for ax, (target_name, y_target) in zip(axes, targets.items()):
    # Ridge regression (regularised GLM) with leave-one-bout-out CV
    pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('ridge',  Ridge(alpha=1.0))
    ])
    cv_groups = df_glm['bout_number'].values
    cv_splitter = LeaveOneGroupOut()

    y_pred_cv = cross_val_predict(
        pipe, X_gaze_scaled, y_target,
        cv=cv_splitter, groups=cv_groups
    )

    # R² from cross-validated predictions
    ss_res = np.sum((y_target - y_pred_cv) ** 2)
    ss_tot = np.sum((y_target - y_target.mean()) ** 2)
    r2_cv  = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

    # Pearson r
    corr = np.corrcoef(y_target, y_pred_cv)[0, 1]

    glm_results.append({
        'target':    target_name,
        'r2_cv':     round(r2_cv, 3),
        'pearson_r': round(corr, 3),
        'n_trials':  len(y_target)
    })

    print(f"  {target_name}")
    print(f"    CV R² = {r2_cv:.3f}   Pearson r = {corr:.3f}")

    # Scatter: actual vs predicted
    ax.scatter(y_target, y_pred_cv, alpha=0.6, color='#4C72B0', edgecolors='white', linewidth=0.5)
    mn, mx = min(y_target.min(), y_pred_cv.min()), max(y_target.max(), y_pred_cv.max())
    ax.plot([mn, mx], [mn, mx], 'r--', linewidth=1, label='Perfect prediction')
    ax.set_xlabel("Actual")
    ax.set_ylabel("Predicted (CV)")
    ax.set_title(f"{target_name}\nCV R²={r2_cv:.3f}  r={corr:.3f}")

plt.suptitle("GLM: Decoding Decision Variables from Eye-Tracking", fontsize=13, y=1.01)
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "step5_glm_decoding.png"), dpi=150, bbox_inches='tight')
plt.close()

glm_df = pd.DataFrame(glm_results)
glm_df.to_csv(os.path.join(OUT_DIR, "results_glm_decoding.csv"), index=False)

print(f"\n  Plot saved → plots/step5_glm_decoding.png")

# ── Final enriched trial dataframe ───────────────────────────────────────────
df.to_csv(os.path.join(OUT_DIR, "trials_enriched_full.csv"), index=False)
print()