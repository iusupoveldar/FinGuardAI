"""Logistic risk model and deterministic benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    FEATURE_VERSION,
    NUMERIC_FEATURES,
    validate_feature_schema,
)


MODEL_VERSION = "logistic_regression_v2"


def aggregate_customer_priority(
    probabilities: np.ndarray | pd.Series,
    rule_scores: np.ndarray | pd.Series,
) -> float:
    """Volume-resistant operational priority aggregation."""

    probability_values = np.sort(np.asarray(probabilities, dtype=float))[::-1]
    rule_values = np.asarray(rule_scores, dtype=float)
    if not probability_values.size:
        return 0.0
    return float(
        0.55 * probability_values[0]
        + 0.35 * probability_values[:3].mean()
        + 0.10 * (rule_values.max() if rule_values.size else 0.0)
    )


def rule_benchmark(features: pd.DataFrame) -> np.ndarray:
    """Transparent non-ML benchmark in the [0, 1] range."""

    velocity = np.clip(features["sender_count_1_vs_30_baseline"] / 10.0, 0, 1)
    amount = np.clip(features["amount_vs_sender_median_30"] / 10.0, 0, 1)
    cross_border = features["cross_border_account"].clip(0, 1)
    new_counterparty = features["is_new_counterparty"].clip(0, 1)
    return np.asarray(
        0.30 * velocity
        + 0.25 * amount
        + 0.20 * cross_border
        + 0.25 * new_counterparty,
        dtype=float,
    )


def build_pipeline(random_state: int = 42) -> Pipeline:
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categories = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return Pipeline(
        [
            (
                "prepare",
                ColumnTransformer(
                    [
                        ("numeric", numeric, NUMERIC_FEATURES),
                        ("category", categories, CATEGORICAL_FEATURES),
                    ]
                ),
            ),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1_000,
                    random_state=random_state,
                    solver="liblinear",
                ),
            ),
        ]
    )


def build_boosted_tree_pipeline(random_state: int = 42) -> Pipeline:
    """One deliberately shallow Phase 4 challenger for offline comparison."""

    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categories = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            (
                "encode",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )
    return Pipeline(
        [
            (
                "prepare",
                ColumnTransformer(
                    [
                        ("numeric", numeric, NUMERIC_FEATURES),
                        ("category", categories, CATEGORICAL_FEATURES),
                    ]
                ),
            ),
            (
                "model",
                HistGradientBoostingClassifier(
                    learning_rate=0.05,
                    max_iter=100,
                    max_leaf_nodes=15,
                    l2_regularization=1.0,
                    random_state=random_state,
                ),
            ),
        ]
    )


@dataclass
class RiskModelArtifact:
    pipeline: Pipeline
    medium_threshold: float
    high_threshold: float
    model_version: str = MODEL_VERSION
    feature_version: str = FEATURE_VERSION
    feature_columns: tuple[str, ...] = tuple(FEATURE_COLUMNS)
    sklearn_version: str = sklearn.__version__

    def predict_probability(self, features: pd.DataFrame) -> np.ndarray:
        validate_feature_schema(features)
        if tuple(FEATURE_COLUMNS) != self.feature_columns:
            raise ValueError("model artifact feature schema does not match runtime schema")
        return self.pipeline.predict_proba(features[FEATURE_COLUMNS])[:, 1]

    def band(self, probability: float) -> str:
        if probability >= self.high_threshold:
            return "high"
        if probability >= self.medium_threshold:
            return "medium"
        return "low"

    def save(self, path: str) -> None:
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "RiskModelArtifact":
        # Loading across sklearn releases is unsupported and can silently alter
        # predictions. Suppress pickle warnings only because we validate below.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            artifact: Any = joblib.load(path)
        if not isinstance(artifact, cls):
            raise ValueError("unsupported risk model artifact")
        if artifact.feature_version != FEATURE_VERSION:
            raise ValueError("model artifact uses an incompatible feature version")
        trained_version = artifact.__dict__.get("sklearn_version")
        if trained_version is None:
            raise ValueError(
                "model artifact predates dependency version tracking; retrain it"
            )
        if trained_version != sklearn.__version__:
            raise ValueError(
                "model artifact was trained with scikit-learn "
                f"{trained_version}, but runtime uses {sklearn.__version__}; "
                "retrain it with the active environment"
            )
        return artifact
