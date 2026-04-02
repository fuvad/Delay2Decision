"""
mlflow_config.py — Shared MLflow setup for all Delay2Decision services.
========================================================================
Call `init_mlflow(experiment_name)` at the top of any service to
configure tracking URI and select the experiment.
"""

import mlflow
from src.utils.config import MLFLOW_TRACKING_URI


def init_mlflow(experiment_name: str) -> str:
    """Set the tracking URI and experiment; return the experiment name."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment_name)
    return experiment_name
