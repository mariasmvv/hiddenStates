"""
=============================================================================
Linear Mixed-Effects Model: Strategy Identification in a Hidden-State Foraging Task
Replicating the core analysis from Vertechi et al. (2020)
=============================================================================

SCIENTIFIC BACKGROUND
---------------------
In hidden-state foraging tasks, two fundamentally different strategies can
explain when a subject leaves an exhausted resource site:

  1. INFERENCE-BASED (Reward-Independent) Strategy — matches an ideal
     Bayesian observer. The agent maintains an internal belief about
     whether the site is still "active" (high-reward state) or "depleted"
     (low-reward state) and leaves when that belief crosses a threshold.
     Because this decision is driven by accumulated *evidence*, not raw
     reward counts, the number of consecutive failures at departure
     should be INDEPENDENT of how many rewards were collected earlier
     in the bout.
     → Model prediction: slope (RewardNumber) ≈ 0, p > 0.05

  2. STIMULUS-BOUND (Reward-Dependent) Strategy — the agent leaves after
     a fixed number of failures that scales with the rewards received.
     More early rewards → higher "expectation" → more failures tolerated.
     The two variables therefore co-vary positively.
     → Model prediction: slope (RewardNumber) >> 0, p < 0.05

The Linear Mixed-Effects Model below tests these competing hypotheses while
properly accounting for the repeated-measures structure of the data (multiple
bouts per participant).
"""

# ── Standard library ──────────────────────────────────────────────────────────
import sys

# ── Third-party ───────────────────────────────────────────────────────────────
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


# =============================================================================
# 1. CONFIGURATION — edit these to match your setup
# =============================================================================

CSV_PATH = "hidden_states_export2.csv"   # ← path to your CSV file

# Column names as they appear in your CSV
COL_USER    = "recording_id"
COL_CFAIL   = "consecutive_failures_norm"   # dependent variable (DV)
COL_REWARD  = "total_rewards_norm"          # independent variable (IV)


# =============================================================================
# 2. DATA LOADING
# =============================================================================

print("=" * 70)
print("STEP 1 — Loading data")
print("=" * 70)

try:
    df_raw = pd.read_csv(CSV_PATH)
except FileNotFoundError:
    sys.exit(
        f"\n[ERROR] Could not find '{CSV_PATH}'.\n"
        "Please update CSV_PATH at the top of this script.\n"
    )

print(f"  Rows loaded   : {len(df_raw):,}")
print(f"  Columns found : {list(df_raw.columns)}\n")

# Validate that required columns exist
required_cols = {COL_USER, COL_CFAIL, COL_REWARD}
missing = required_cols - set(df_raw.columns)
if missing:
    sys.exit(
        f"[ERROR] The following required columns are missing from the CSV: {missing}\n"
        "Please check the column name constants at the top of the script.\n"
    )


# =============================================================================
# 3. DATA CLEANING & BOUT-LEVEL REDUCTION
# =============================================================================

print("=" * 70)
print("STEP 2 — Cleaning and preparing data")
print("=" * 70)

df = df_raw.copy()

# ── 3a. Keep only the final row of each bout ──────────────────────────────────
# Each bout ends at the moment the player leaves a site. If your CSV already
# stores one row per bout (i.e. the final-moment snapshot), this step is a
# no-op. If it stores every time-step, we keep the row with the *highest*
# ConsecutiveFailures value within each (UserID × bout) group, which
# corresponds to the departure moment.
#
# Assumption: a "bout" restarts whenever ConsecutiveFailures resets to 0
# after having been > 0, or whenever the site changes. We implement a
# simple heuristic: within each UserID, assign a bout ID each time
# ConsecutiveFailures goes from a positive value back to 0 (or at the
# very first row). Then take the last row of each bout.

def assign_bout_ids(group):
    """Assign a monotonically increasing bout ID within a participant's data."""
    bout_id = 0
    ids = []
    prev = None
    for val in group[COL_CFAIL]:
        # A new bout starts when the counter resets (drops relative to prev)
        if prev is not None and val < prev:
            bout_id += 1
        ids.append(bout_id)
        prev = val
    return ids

df["_bout_id"] = np.nan

for uid, grp in df.groupby(COL_USER, sort=False):
    df.loc[grp.index, "_bout_id"] = assign_bout_ids(grp)

# Now keep the final (maximum ConsecutiveFailures) row per bout
df_bouts = (
    df
    .sort_values(COL_CFAIL)                          # sort so last = highest
    .groupby([COL_USER, "_bout_id"], sort=False)
    .last()                                           # final row = departure moment
    .reset_index()
)

print(f"  Bouts identified : {len(df_bouts):,}")
print(f"  Participants     : {df_bouts[COL_USER].nunique():,}\n")

# ── 3b. Drop rows with missing values in the model columns ────────────────────
before = len(df_bouts)
df_bouts = df_bouts.dropna(subset=[COL_USER, COL_CFAIL, COL_REWARD])
dropped = before - len(df_bouts)
if dropped:
    print(f"  [WARN] Dropped {dropped} rows with NaN in key columns.\n")

# ── 3c. Enforce correct dtypes ────────────────────────────────────────────────
df_bouts[COL_CFAIL]  = df_bouts[COL_CFAIL].astype(float)
df_bouts[COL_REWARD] = df_bouts[COL_REWARD].astype(float)

# ── 3d. Descriptive summary ───────────────────────────────────────────────────
print("  Descriptive statistics (bout-level):")
print(
    df_bouts[[COL_CFAIL, COL_REWARD]]
    .describe()
    .round(2)
    .to_string(index=True)
)
print()


# =============================================================================
# 4. MODEL FITTING
# =============================================================================
#
# Formula (Wilkinson notation):
#
#   ConsecutiveFailures ~ 1 + RewardNumber + (1 | UserID)
#
# In statsmodels, random effects are specified via the `groups` argument
# rather than inside the formula string.
#
# Fixed effects
# ─────────────
#   Intercept   — expected ConsecutiveFailures when RewardNumber = 0
#   RewardNumber — *this is the key coefficient*: how many extra consecutive
#                  failures at departure per additional reward collected
#
# Random effect
# ─────────────
#   Random intercept for UserID — captures between-subject baseline
#   differences in departure threshold (some players are simply more
#   patient than others), preventing that variance from inflating the
#   residuals and biasing the fixed-effect estimates.

print("=" * 70)
print("STEP 3 — Fitting Linear Mixed-Effects Model")
print("=" * 70)
print(
    f"  Formula : {COL_CFAIL} ~ 1 + {COL_REWARD}\n"
    f"  Groups  : {COL_USER}  (random intercept)\n"
)

formula = f"{COL_CFAIL} ~ 1 + {COL_REWARD}"

model = smf.mixedlm(
    formula  = formula,
    data     = df_bouts,
    groups   = df_bouts[COL_USER],   # random intercept per participant
    # re_formula=None means random intercept only (default)
)

result = model.fit(method="lbfgs", reml=True)
# REML=True (Restricted Maximum Likelihood) is the standard choice for
# LMMs when the primary interest is in the variance components; it gives
# less-biased estimates of the random-effect variance than full ML.

print(result.summary())
print()


# =============================================================================
# 5. STRATEGY INTERPRETATION
# =============================================================================

print("=" * 70)
print("STEP 4 — Interpreting the RewardNumber coefficient")
print("=" * 70)

# Extract the slope for RewardNumber
slope = result.params[COL_REWARD]
pval  = result.pvalues[COL_REWARD]
ci_lo, ci_hi = result.conf_int().loc[COL_REWARD]

print(f"\n  RewardNumber coefficient (slope) : {slope:+.4f}")
print(f"  95% Confidence interval          : [{ci_lo:.4f}, {ci_hi:.4f}]")
print(f"  p-value                          : {pval:.4f}\n")

ALPHA = 0.05   # significance threshold

if pval >= ALPHA:
    print(
        "  ✅  INFERENCE-BASED (Reward-Independent) Strategy\n"
        "  ──────────────────────────────────────────────────\n"
        f"  The slope ({slope:+.4f}) is near zero and statistically\n"
        f"  NON-SIGNIFICANT (p = {pval:.4f} ≥ {ALPHA}).\n\n"
        "  Interpretation: The number of consecutive failures at which\n"
        "  participants leave a site does NOT depend on how many rewards\n"
        "  they collected during that bout. This is consistent with an\n"
        "  ideal Bayesian / inference-based strategy: subjects appear to\n"
        "  maintain an internal belief about the site's state and leave\n"
        "  when accumulated negative evidence (failures) crosses a\n"
        "  threshold — exactly as reported for mice in Vertechi et al.\n"
        "  (2020).\n"
    )
else:
    print(
        "  ⚠️   STIMULUS-BOUND (Reward-Dependent) Strategy\n"
        "  ──────────────────────────────────────────────────\n"
        f"  The slope ({slope:+.4f}) is SIGNIFICANTLY POSITIVE\n"
        f"  (p = {pval:.4f} < {ALPHA}).\n\n"
        "  Interpretation: Participants who collected more rewards in a\n"
        "  bout also tolerated more consecutive failures before leaving.\n"
        "  This suggests a reward-dependent, stimulus-bound strategy:\n"
        "  the decision threshold co-varies with prior reward history\n"
        "  rather than being driven purely by a hidden-state belief.\n"
        "  This pattern is inconsistent with ideal Bayesian inference.\n"
    )

print("=" * 70)
print("Analysis complete.")
print("=" * 70)
