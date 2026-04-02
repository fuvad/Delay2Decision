"""
personalization.py — User Profile Personalization Layer
=========================================================
Pure domain logic (NOT ML). Adjusts the ML-predicted buffer_minutes
based on the traveller's risk tolerance profile.

Pipeline:  ML models -> risk + buffer -> personalization -> final buffer
"""

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────
# USER PROFILES
# ─────────────────────────────────────────────────────────────────────────

PROFILES = {
    "conservative": {
        "description": "Hates missing flights - prefers extra safety margin",
        "buffer_multiplier": 1.20,   # +20% buffer
    },
    "balanced": {
        "description": "Average risk tolerance - trusts the model output",
        "buffer_multiplier": 1.00,   # no change
    },
    "aggressive": {
        "description": "Willing to take risk - minimizes waiting time",
        "buffer_multiplier": 0.80,   # -20% buffer
    },
}


def personalize_buffer(df: pd.DataFrame, profile: str = "balanced") -> pd.DataFrame:
    """
    Adjust buffer_minutes based on the chosen user profile.

    Parameters
    ----------
    df : DataFrame with a 'buffer_minutes' column (raw ML output).
    profile : one of 'conservative', 'balanced', 'aggressive'.

    Returns
    -------
    DataFrame with added columns:
        - profile           : the profile name used
        - buffer_multiplier : the multiplier applied
        - final_buffer      : personalized buffer (buffer_minutes × multiplier)
    """
    if profile not in PROFILES:
        raise ValueError(
            f"Unknown profile '{profile}'. Choose from: {list(PROFILES.keys())}"
        )

    multiplier = PROFILES[profile]["buffer_multiplier"]

    df = df.copy()
    df["profile"]           = profile
    df["buffer_multiplier"] = multiplier
    df["final_buffer"]      = (df["buffer_minutes"] * multiplier).round(1)

    return df


def personalize_all_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add personalized buffer columns for ALL profiles at once.

    Adds three columns:
        - buffer_conservative  (+20%)
        - buffer_balanced      (unchanged)
        - buffer_aggressive    (-20%)

    This lets downstream systems pick the right column based on user preference.
    """
    df = df.copy()
    for name, cfg in PROFILES.items():
        col = f"buffer_{name}"
        df[col] = (df["buffer_minutes"] * cfg["buffer_multiplier"]).round(1)

    return df
