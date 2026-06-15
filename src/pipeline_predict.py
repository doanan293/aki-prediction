from __future__ import annotations

import json
from numbers import Real
from pathlib import Path

import joblib
import numpy as np

from src.artifacts import load_model_registry, load_preprocessor_bundle
from src.data_loader import load_and_flatten_data
from src.pipeline_evaluate import transform_with_bundle


def _normalize_binary_prediction(value: object, idx: int) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, Real) and value in (0, 1):
        return bool(value)
    raise ValueError(f"Invalid prediction at index {idx}: {value!r}")


def _validate_prediction_payload(payload: object) -> list[dict]:
    if not isinstance(payload, list):
        raise ValueError("Input payload must be a list of objects")
    for idx, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(
                f"Input payload must be a list of objects; item at index {idx} is {type(row).__name__}"
            )
    return payload


def run_predict(
    input_path: Path,
    models_dir: Path,
    model_name: str | None,
    output_path: Path,
) -> Path:
    if input_path.suffix.lower() != ".json":
        raise ValueError("predict input must be a .json file")
    if output_path.suffix.lower() != ".csv":
        raise ValueError("predict output must be a .csv file")

    registry = load_model_registry(models_dir / "model_registry.json")
    chosen_name = model_name or registry["best_model_name"]

    if chosen_name not in registry["model_files"]:
        raise KeyError(f"Requested model not found in registry: {chosen_name}")

    bundle = load_preprocessor_bundle(models_dir / "preprocessor.joblib")
    model_path = models_dir / registry["model_files"][chosen_name]
    if not model_path.exists():
        raise FileNotFoundError(
            f"Missing model artifact: {model_path}. "
            "Run 'main.py train' to regenerate model files."
        )
    model = joblib.load(model_path)

    # If the model is TabPFN, refit it on the combined train and test sets to use 100% data
    # (since TabPFN does in-context learning, more samples in context helps).
    if type(model).__name__ == "TabPFNWrapper":
        print("[PREDICT][INFO] Refitting TabPFN model on 100% of the training data (train + test splits)...")
        from src.config import TRAIN_DATA_PATH, TEST_DATA_PATH
        from src.data_loader import load_flat_csv
        import pandas as pd
        
        X_train_raw, y_train, _ = load_flat_csv(str(TRAIN_DATA_PATH), require_target=True)
        X_test_raw, y_test, _ = load_flat_csv(str(TEST_DATA_PATH), require_target=True)
        
        X_full_raw = pd.concat([X_train_raw, X_test_raw], axis=0, ignore_index=True)
        y_full = pd.concat([y_train, y_test], axis=0, ignore_index=True).astype(int)
        
        sel_features = bundle.get("sel_features", [])
        if not sel_features:
            raise ValueError("No selected features found in preprocessor bundle.")
            
        X_full_sel = X_full_raw[sel_features]
        model.fit(X_full_sel, y_full)

    payload = _validate_prediction_payload(
        json.loads(input_path.read_text(encoding="utf-8"))
    )
    subject_ids = []
    for idx, row in enumerate(payload):
        subject_id = row.get("subjectId")
        if subject_id is None:
            raise ValueError(f"Patient at index {idx} is missing subjectId")
        subject_ids.append(subject_id)

    X_raw, _, _ = load_and_flatten_data(str(input_path), require_target=False)

    X_pred = transform_with_bundle(X_raw, bundle)

    raw_predictions = model.predict(X_pred)
    predictions_bool = [
        _normalize_binary_prediction(value, idx)
        for idx, value in enumerate(raw_predictions)
    ]

    if len(subject_ids) != len(predictions_bool):
        raise ValueError(
            f"Length mismatch: input has {len(subject_ids)} rows but predictions have {len(predictions_bool)}"
        )

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(X_pred)[:, 1]
    else:
        if hasattr(model, "decision_function"):
            scores = model.decision_function(X_pred)
            probabilities = 1 / (1 + np.exp(-scores))
        else:
            probabilities = [1.0 if pred else 0.0 for pred in predictions_bool]

    import pandas as pd
    out_df = pd.DataFrame({
        "id": subject_ids,
        "probability": [round(float(p), 2) for p in probabilities],
        "prediction": [1 if pred else 0 for pred in predictions_bool]
    })
    out_df = out_df.drop_duplicates(subset=["id"], keep="first")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)
    return output_path
