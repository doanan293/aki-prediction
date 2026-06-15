from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib

ARTIFACT_SCHEMA_VERSION = "1"

REQUIRED_PREPROCESSOR_KEYS = {
    "schema_version",
    "target_name",
    "prep_artifacts",
    "kept_cols",
    "sel_features",
}

REQUIRED_REGISTRY_KEYS = {
    "schema_version",
    "best_model_name",
    "model_files",
    "selection_metric",
}


def save_preprocessor_bundle(
    out_path: Path,
    prep_artifacts: dict[str, Any],
    kept_cols: list[str],
    sel_features: list[str],
    target_name: str = "akdPositive",
) -> None:
    payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "target_name": target_name,
        "prep_artifacts": prep_artifacts,
        "kept_cols": kept_cols,
        "sel_features": sel_features,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, out_path)


def load_preprocessor_bundle(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing preprocessor artifact: {path}")

    payload = joblib.load(path)
    if not isinstance(payload, dict):
        raise ValueError("Invalid preprocessor artifact payload type")

    missing = sorted(REQUIRED_PREPROCESSOR_KEYS - set(payload.keys()))
    if missing:
        raise ValueError(f"Invalid preprocessor artifact, missing keys: {missing}")

    if payload["schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version={payload['schema_version']}; "
            f"expected {ARTIFACT_SCHEMA_VERSION}"
        )

    if (
        not isinstance(payload["target_name"], str)
        or not payload["target_name"].strip()
    ):
        raise ValueError("Invalid preprocessor artifact target_name type")
    if not isinstance(payload["prep_artifacts"], dict):
        raise ValueError("Invalid preprocessor artifact prep_artifacts type")
    if not isinstance(payload["kept_cols"], list) or any(
        not isinstance(col, str) for col in payload["kept_cols"]
    ):
        raise ValueError("Invalid preprocessor artifact kept_cols type")
    if not isinstance(payload["sel_features"], list) or any(
        not isinstance(col, str) for col in payload["sel_features"]
    ):
        raise ValueError("Invalid preprocessor artifact sel_features type")

    return payload


def build_registry_payload(
    best_model_name: str,
    model_files: dict[str, str],
    selection_metric: str,
    metric_snapshot: dict[str, float] | None = None,
    training_summary: dict[str, dict[str, int]] | None = None,
) -> dict[str, Any]:
    if not isinstance(model_files, dict) or not model_files:
        raise ValueError("Invalid model_files: expected a non-empty dict")
    if any(
        not isinstance(model_name, str)
        or not model_name.strip()
        or not isinstance(file_name, str)
        or not file_name.strip()
        for model_name, file_name in model_files.items()
    ):
        raise ValueError(
            "Invalid model_files entries: expected non-empty string keys and values"
        )
    if best_model_name not in model_files:
        raise ValueError("Invalid best_model_name: must be present in model_files")
    if not isinstance(selection_metric, str) or not selection_metric.strip():
        raise ValueError("Invalid selection_metric: expected a non-empty string")

    payload: dict[str, Any] = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "best_model_name": best_model_name,
        "model_files": model_files,
        "selection_metric": selection_metric,
    }
    if metric_snapshot is not None:
        payload["metric_snapshot"] = metric_snapshot
    if training_summary is not None:
        if not isinstance(training_summary, dict):
            raise ValueError("Invalid training_summary: expected a dict")
        for model_name, summary in training_summary.items():
            if not isinstance(model_name, str) or not model_name.strip():
                raise ValueError("Invalid training_summary model name")
            if not isinstance(summary, dict):
                raise ValueError(f"Invalid training_summary for {model_name}: expected a dict")
            if "n_iter" not in summary:
                raise ValueError(f"Invalid training_summary for {model_name}: missing n_iter")
            if not isinstance(summary["n_iter"], int) or summary["n_iter"] < 0:
                raise ValueError(f"Invalid training_summary for {model_name}: n_iter must be a non-negative integer")
        payload["training_summary"] = training_summary
    return payload


def save_model_registry(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_model_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing model registry: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid model registry JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid model registry payload type")

    missing = sorted(REQUIRED_REGISTRY_KEYS - set(payload.keys()))
    if missing:
        raise ValueError(f"Invalid model registry, missing keys: {missing}")

    if payload["schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported registry schema_version={payload['schema_version']}; "
            f"expected {ARTIFACT_SCHEMA_VERSION}"
        )

    if (
        not isinstance(payload["best_model_name"], str)
        or not payload["best_model_name"].strip()
    ):
        raise ValueError("Invalid model registry best_model_name type")
    if not isinstance(payload["model_files"], dict) or not payload["model_files"]:
        raise ValueError("Invalid model registry model_files type")
    if any(
        not isinstance(model_name, str)
        or not model_name.strip()
        or not isinstance(file_name, str)
        or not file_name.strip()
        for model_name, file_name in payload["model_files"].items()
    ):
        raise ValueError(
            "Invalid model registry model_files entries: expected non-empty string keys and values"
        )
    if payload["best_model_name"] not in payload["model_files"]:
        raise ValueError(
            "Invalid model registry: best_model_name must exist in model_files"
        )
    if (
        not isinstance(payload["selection_metric"], str)
        or not payload["selection_metric"].strip()
    ):
        raise ValueError("Invalid model registry selection_metric type")

    return payload
