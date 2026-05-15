"""
fit_lm_hmm_simple.py
====================
Fits a Linear Model Hidden Markov Model (LM-HMM) replicating
Cazettes et al. (2023) "A reservoir of foraging decision variables
in the mouse brain." Nature Neuroscience 26, 840-849.

NO external HMM library needed — only standard scientific Python.

Install dependencies (all available on any Python 3.8+):
    pip install numpy pandas matplotlib scipy

Model equation per hidden state k:
    F_t = w(k) * R_t  +  b(k)  +  epsilon_t
where:
    F_t         = Consecutivefailures_norm  (observation)
    R_t         = totalRewards_norm         (input covariate)
    w(k)        = slope  for state k
    b(k)        = intercept for state k
    epsilon_t   ~ Normal(0, sigma_k^2)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# CONFIGURATION  — edit these
# ============================================================
DATA_FILE  = "hidden_states_export.csv"
USER_COL   = "recording_id"
OBS_COL    = "consecutive_failures_norm"
INPUT_COL  = "total_rewards_norm"

N_STATES   = 2      # K: number of hidden states
N_RESTARTS = 5      # random restarts to avoid local optima
N_ITERS    = 200    # max EM iterations per restart
TOL        = 1e-4   # stop early if log-likelihood improvement < TOL
SEED       = 42


# ============================================================
# CORE EM ALGORITHM
# ============================================================

class LMHMM:
    """
    Linear Model Hidden Markov Model fitted by Expectation-Maximization.

    Each state k has its own linear observation model:
        mean_k(t) = W[k,0]*R_t + W[k,1]*1   (slope + intercept)
        y_t | z_t=k  ~  Normal(mean_k(t), sigma_k^2)

    The transition matrix A[i,j] = P(z_{t+1}=j | z_t=i) is stationary
    (does not depend on inputs), matching the paper's specification.
    """

    def __init__(self, n_states, seed=None):
        self.K = n_states
        self.rng = np.random.default_rng(seed)

    # ----------------------------------------------------------
    # Initialisation
    # ----------------------------------------------------------
    def _init_params(self, observations_list, inputs_list):
        """Random initialisation of all parameters."""
        K = self.K

        # Transition matrix: rows sum to 1
        A = self.rng.dirichlet(np.ones(K), size=K)

        # Initial state distribution
        pi = self.rng.dirichlet(np.ones(K))

        # Linear weights W[k] = [slope, intercept], shape (K, 2)
        # Initialise near the global OLS solution with small noise
        all_y = np.concatenate(observations_list)           # (N,)
        all_u = np.concatenate(inputs_list)                 # (N, 2)
        ols_w, _, _, _ = np.linalg.lstsq(all_u, all_y, rcond=None)
        W = np.tile(ols_w, (K, 1)).astype(float)
        W += self.rng.normal(0, 0.1, W.shape)

        # Observation noise standard deviation per state
        sigma = np.ones(K) * np.std(all_y) + self.rng.uniform(0, 0.05, K)

        return pi, A, W, sigma

    # ----------------------------------------------------------
    # Gaussian log-likelihood  log p(y_t | z_t=k)
    # ----------------------------------------------------------
    @staticmethod
    def _log_obs(y, u, W, sigma):
        """
        Compute log p(y_t | z_t=k) for all t and k.

        Parameters
        ----------
        y     : (T,)   observations
        u     : (T, 2) inputs  [R_t, 1]
        W     : (K, 2) weights
        sigma : (K,)   noise std

        Returns
        -------
        log_p : (T, K)
        """
        means = u @ W.T                          # (T, K)  linear model
        diff  = y[:, None] - means               # (T, K)
        log_p = (
            -0.5 * (diff / sigma[None, :]) ** 2
            - np.log(sigma[None, :])
            - 0.5 * np.log(2 * np.pi)
        )
        return log_p                             # (T, K)

    # ----------------------------------------------------------
    # Forward-backward algorithm (E-step, single sequence)
    # ----------------------------------------------------------
    def _forward_backward(self, log_obs, A, pi):
        """
        Standard scaled forward-backward.

        Returns
        -------
        gamma  : (T, K)  P(z_t=k | y_{1:T})
        xi_sum : (K, K)  sum_t P(z_t=i, z_{t+1}=j | y)
        log_ll : float   log P(y_{1:T})
        """
        T, K = log_obs.shape
        log_A  = np.log(A + 1e-300)
        log_pi = np.log(pi + 1e-300)

        # --- Forward pass (log-scale for numerical stability) ---
        log_alpha = np.empty((T, K))
        log_alpha[0] = log_pi + log_obs[0]
        log_alpha[0] -= _logsumexp(log_alpha[0])   # normalise

        log_scales = np.empty(T)
        log_scales[0] = 0.0

        for t in range(1, T):
            # (K,) = logsumexp over previous states
            log_pred = _logsumexp_axis(log_alpha[t-1:t, :].T + log_A.T, axis=0)
            log_alpha[t] = log_pred + log_obs[t]
            scale = _logsumexp(log_alpha[t])
            log_alpha[t] -= scale
            log_scales[t] = scale

        log_ll = log_scales.sum()

        # --- Backward pass ---
        log_beta = np.zeros((T, K))
        for t in range(T-2, -1, -1):
            log_beta[t] = _logsumexp_axis(
                log_A + log_obs[t+1] + log_beta[t+1], axis=1
            )
            # normalise to prevent overflow
            log_beta[t] -= _logsumexp(log_beta[t])

        # --- Posterior state probabilities gamma ---
        log_gamma = log_alpha + log_beta
        log_gamma -= _logsumexp_axis(log_gamma, axis=1, keepdims=True)
        gamma = np.exp(log_gamma)                            # (T, K)

        # --- Two-slice marginals xi_sum (K, K) ---
        xi_sum = np.zeros((K, K))
        for t in range(T-1):
            log_xi = (
                log_alpha[t, :, None]   # (K,1)
                + log_A                  # (K,K)
                + log_obs[t+1, None, :] # (1,K)
                + log_beta[t+1, None, :]# (1,K)
            )
            xi_sum += np.exp(log_xi - _logsumexp(log_xi.ravel()))

        return gamma, xi_sum, log_ll

    # ----------------------------------------------------------
    # EM algorithm
    # ----------------------------------------------------------
    def fit(self, observations_list, inputs_list,
            n_iters=200, tol=1e-4, verbose=True):
        """
        Fit the LM-HMM to a list of sequences via EM.

        Parameters
        ----------
        observations_list : list of (T_i,) arrays
        inputs_list       : list of (T_i, 2) arrays
        """
        pi, A, W, sigma = self._init_params(observations_list, inputs_list)
        prev_ll = -np.inf
        ll_curve = []

        for it in range(n_iters):

            # ---- E-step ----------------------------------------
            # Accumulate sufficient statistics across all sequences
            gamma_list  = []
            xi_sum_tot  = np.zeros((self.K, self.K))
            total_ll    = 0.0

            for y_seq, u_seq in zip(observations_list, inputs_list):
                log_obs_seq = self._log_obs(y_seq, u_seq, W, sigma)
                gamma, xi_sum, seq_ll = self._forward_backward(
                    log_obs_seq, A, pi
                )
                gamma_list.append((gamma, y_seq, u_seq))
                xi_sum_tot += xi_sum
                total_ll   += seq_ll

            ll_curve.append(total_ll)

            if verbose:
                print(f"    iter {it+1:>3}: log-likelihood = {total_ll:.4f}")

            # Check convergence
            if abs(total_ll - prev_ll) < tol and it > 0:
                if verbose:
                    print(f"    Converged at iteration {it+1}.")
                break
            prev_ll = total_ll

            # ---- M-step ----------------------------------------

            # 1. Update initial state distribution
            pi = np.mean([g[0][0] for g in gamma_list], axis=0)
            pi = np.maximum(pi, 1e-10)
            pi /= pi.sum()

            # 2. Update transition matrix (row-normalise xi_sum)
            A = xi_sum_tot / xi_sum_tot.sum(axis=1, keepdims=True)
            A = np.maximum(A, 1e-10)
            A /= A.sum(axis=1, keepdims=True)

            # 3. Update linear weights W and noise sigma per state
            for k in range(self.K):
                # Collect weighted observations across all sequences
                y_all   = np.concatenate([g[1] for g in gamma_list])
                u_all   = np.concatenate([g[2] for g in gamma_list])
                w_resp  = np.concatenate([g[0][:, k] for g in gamma_list])

                # Weighted least squares:  W[k] = (U^T diag(w) U)^{-1} U^T diag(w) y
                # Add small ridge to avoid singular matrix
                sqrt_w = np.sqrt(w_resp + 1e-10)
                U_w = u_all * sqrt_w[:, None]
                y_w = y_all * sqrt_w
                reg = 1e-6 * np.eye(u_all.shape[1])
                W[k] = np.linalg.solve(U_w.T @ U_w + reg, U_w.T @ y_w)

                # Weighted residual variance
                residuals = y_all - u_all @ W[k]
                sigma[k]  = np.sqrt(
                    np.sum(w_resp * residuals**2) / (np.sum(w_resp) + 1e-10)
                )
                sigma[k]  = max(sigma[k], 1e-4)   # numerical floor

        # Store fitted parameters
        self.pi_    = pi
        self.A_     = A
        self.W_     = W
        self.sigma_ = sigma
        self.ll_curve_ = np.array(ll_curve)
        return self

    # ----------------------------------------------------------
    # Viterbi decoding
    # ----------------------------------------------------------
    def predict_states(self, y_seq, u_seq):
        """Return the most likely hidden state sequence (Viterbi)."""
        T = len(y_seq)
        K = self.K
        log_obs = self._log_obs(y_seq, u_seq, self.W_, self.sigma_)
        log_A   = np.log(self.A_ + 1e-300)
        log_pi  = np.log(self.pi_ + 1e-300)

        viterbi  = np.empty((T, K))
        backptr  = np.zeros((T, K), dtype=int)
        viterbi[0] = log_pi + log_obs[0]

        for t in range(1, T):
            trans = viterbi[t-1, :, None] + log_A   # (K, K)
            backptr[t] = np.argmax(trans, axis=0)
            viterbi[t] = np.max(trans, axis=0) + log_obs[t]

        # Backtrack
        states = np.empty(T, dtype=int)
        states[-1] = np.argmax(viterbi[-1])
        for t in range(T-2, -1, -1):
            states[t] = backptr[t+1, states[t+1]]
        return states


# ============================================================
# NUMERICS HELPERS
# ============================================================

def _logsumexp(x):
    """Numerically stable log-sum-exp of a 1-D array."""
    m = np.max(x)
    return m + np.log(np.sum(np.exp(x - m)) + 1e-300)

def _logsumexp_axis(x, axis, keepdims=False):
    """Numerically stable log-sum-exp along an axis."""
    m = np.max(x, axis=axis, keepdims=True)
    result = m + np.log(np.sum(np.exp(x - m), axis=axis, keepdims=True) + 1e-300)
    if not keepdims:
        result = np.squeeze(result, axis=axis)
    return result


# ============================================================
# DATA LOADING
# ============================================================

def load_data(filepath, user_col, obs_col, input_col):
    """
    Load CSV and split into per-user observation and input sequences.

    Returns
    -------
    observations_list : list of (T_i,) float arrays  — F_t values
    inputs_list       : list of (T_i, 2) float arrays — [R_t, 1]
    user_ids          : list of user identifiers
    """
    print(f"Loading '{filepath}' …")
    df = pd.read_csv(filepath)
    print(f"  {len(df):,} rows, {df[user_col].nunique()} users.\n")

    observations_list, inputs_list, user_ids = [], [], []
    for uid, grp in df.groupby(user_col, sort=False):
        grp = grp.reset_index(drop=True)
        y   = grp[obs_col].values.astype(float)          # (T_i,)
        u   = np.column_stack([
            grp[input_col].values.astype(float),          # slope input
            np.ones(len(grp))                             # intercept column
        ])                                                 # (T_i, 2)
        observations_list.append(y)
        inputs_list.append(u)
        user_ids.append(uid)

    return observations_list, inputs_list, user_ids


# ============================================================
# MULTIPLE RESTARTS
# ============================================================

def fit_with_restarts(observations_list, inputs_list,
                      n_states, n_restarts, n_iters, tol, seed):
    best_model = None
    best_ll    = -np.inf
    all_curves = []

    for r in range(n_restarts):
        print(f"Restart {r+1}/{n_restarts}")
        model = LMHMM(n_states, seed=seed + r)
        model.fit(observations_list, inputs_list,
                  n_iters=n_iters, tol=tol, verbose=True)
        final_ll = model.ll_curve_[-1]
        all_curves.append(model.ll_curve_)
        print(f"  → final log-likelihood: {final_ll:.4f}\n")

        if final_ll > best_ll:
            best_ll    = final_ll
            best_model = model

    return best_model, all_curves


# ============================================================
# RESULTS DISPLAY
# ============================================================

def print_results(model):
    K = model.K
    print("\n" + "=" * 55)
    print("  FITTED LM-HMM PARAMETERS")
    print("=" * 55)

    print("\nObservation model per state:  F_t = w(k)*R_t + b(k) + ε_t\n")
    print(f"  {'State':<8} {'w(k)  slope':>14}  {'b(k)  intercept':>18}  {'σ_k  noise std':>16}")
    print("  " + "-" * 60)
    for k in range(K):
        w, b = model.W_[k]
        print(f"  State {k+1:<3}  {w:>14.6f}  {b:>18.6f}  {model.sigma_[k]:>16.6f}")

    print("\n\nTransition matrix  A[i,j] = P(next=j | current=i)\n")
    header = "         " + "  ".join(f"→ State {j+1}" for j in range(K))
    print(header)
    print("  " + "-" * (12 * K + 5))
    for i in range(K):
        row = "  ".join(f"{model.A_[i,j]:.6f}" for j in range(K))
        print(f"  State {i+1} |  {row}")

    print(f"\nInitial state distribution: "
          + "  ".join(f"State {k+1}: {model.pi_[k]:.4f}" for k in range(K)))


def plot_convergence(all_curves, save_path="em_convergence.png"):
    best_final = max(c[-1] for c in all_curves)
    plt.figure(figsize=(8, 4))
    for i, curve in enumerate(all_curves):
        lw = 2.5 if curve[-1] == best_final else 1.0
        ls = "-"  if curve[-1] == best_final else "--"
        plt.plot(curve, lw=lw, ls=ls, label=f"Restart {i+1} ({curve[-1]:.2f})")
    plt.xlabel("EM iteration")
    plt.ylabel("Log-likelihood")
    plt.title("LM-HMM EM convergence")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"\nConvergence plot saved to '{save_path}'")
    plt.close()


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 55)
    print("  LM-HMM  —  Cazettes et al. (2023)")
    print("=" * 55 + "\n")

    observations_list, inputs_list, user_ids = load_data(
        DATA_FILE, USER_COL, OBS_COL, INPUT_COL
    )

    best_model, all_curves = fit_with_restarts(
        observations_list, inputs_list,
        n_states   = N_STATES,
        n_restarts = N_RESTARTS,
        n_iters    = N_ITERS,
        tol        = TOL,
        seed       = SEED,
    )

    print_results(best_model)
    plot_convergence(all_curves)

    # Per-user state usage
    print("\n\nViterbi state assignments per user:\n")
    for uid, y, u in zip(user_ids, observations_list, inputs_list):
        states = best_model.predict_states(y, u)
        counts = np.bincount(states, minlength=N_STATES)
        pct    = counts / counts.sum() * 100
        usage  = "  ".join(f"State {k+1}: {pct[k]:5.1f}%" for k in range(N_STATES))
        print(f"  User {uid}: {usage}")

    print("\nDone.")


if __name__ == "__main__":
    main()
