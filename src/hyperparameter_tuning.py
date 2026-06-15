from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from src.data_loader import load_and_flatten_data, load_flat_csv
from src.evaluate import _extract_positive_class_probability
from src.models import get_models
from src.artifacts import load_preprocessor_bundle


TUNING_ARTIFACT_NAME = "tuning_results.json"
_FAILED_TRIAL_AUC = 0.5

_REQUIRED_ARTIFACT_KEYS = {
    "schema_version",
    "created_at",
    "random_state",
    "cv",
    "metric",
    "budget",
    "selected_features",
    "models",
    "ranking",
}

_BUDGETS = {
    "quick": {
        "XGBoost": 3,
        "LightGBM": 2,
        "SVM": 2,
        "Logistic Regression": 2,
        "AdaBoost": 2,
        "GNB": 1,
        "CNB": 1,
        "MLP": 2,
        "TabPFN-3-Plus": 0,
    },
    "deep": {
        "XGBoost": 200,
        "LightGBM": 20,
        "SVM": 5,
        "Logistic Regression": 5,
        "AdaBoost": 5,
        "GNB": 2,
        "CNB": 2,
        "MLP": 5,
        "TabPFN-3-Plus": 0,
    },
}


def build_budget(name: str) -> dict[str, int]:
    budget_name = name.strip().lower()
    if budget_name not in _BUDGETS:
        available = ", ".join(sorted(_BUDGETS))
        raise ValueError(f"Unknown tuning budget '{name}'. Available budgets: {available}")
    return dict(_BUDGETS[budget_name])


def save_tuning_results(path: Path, payload: dict[str, Any]) -> None:
    validate_tuning_results(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_tuning_results(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_tuning_results(payload)
    return payload


def validate_tuning_results(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Tuning artifact must be a JSON object")
    missing = sorted(_REQUIRED_ARTIFACT_KEYS - set(payload.keys()))
    if missing:
        raise ValueError(f"Tuning artifact is missing required keys: {missing}")
    if payload["schema_version"] != "1":
        raise ValueError(f"Unsupported tuning artifact schema_version: {payload['schema_version']}")
    if payload["metric"] != "roc_auc":
        raise ValueError(f"Unsupported tuning metric: {payload['metric']}")
    if not isinstance(payload["models"], dict):
        raise ValueError("Tuning artifact field 'models' must be an object")
    for model_name, model_payload in payload["models"].items():
        if not isinstance(model_payload, dict):
            raise ValueError(f"Tuning payload for {model_name} must be an object")
        for key in ("best_score", "n_trials", "best_params"):
            if key not in model_payload:
                raise ValueError(f"Tuning payload for {model_name} missing key: {key}")
        if not isinstance(model_payload["best_params"], dict):
            raise ValueError(f"Tuning payload for {model_name} has non-object best_params")


def extract_best_params(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validate_tuning_results(payload)
    return {model_name: dict(model_payload["best_params"]) for model_name, model_payload in payload["models"].items()}


def load_tuned_params_from_models_dir(models_dir: Path) -> dict[str, dict[str, Any]] | None:
    tuning_path = models_dir / TUNING_ARTIFACT_NAME
    if not tuning_path.exists():
        return None
    return extract_best_params(load_tuning_results(tuning_path))


def _import_optuna():
    try:
        import optuna
    except ImportError as exc:
        raise ImportError(
            "Optuna is required for hyperparameter tuning. "
            "Install project dependencies with `uv sync` or `uv pip install -e .`."
        ) from exc
    return optuna


def suggest_xgboost_params(trial, scale_pos_weight_center: float) -> dict[str, Any]:
    low_spw = max(0.1, scale_pos_weight_center * 0.5)
    high_spw = max(low_spw, scale_pos_weight_center * 2.0)
    return {
        "n_estimators": trial.suggest_int("n_estimators", 100, 1200),
        "max_depth": trial.suggest_int("max_depth", 2, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", low_spw, high_spw),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "gamma": trial.suggest_float("gamma", 1e-8, 1.0, log=True),
        "tree_method": "hist",
    }


def suggest_logistic_regression_params(trial) -> dict[str, Any]:
    return {
        "C": trial.suggest_float("C", 1e-3, 100.0, log=True),
        "class_weight": trial.suggest_categorical("class_weight", [None, "balanced"]),
    }


def suggest_svm_params(trial) -> dict[str, Any]:
    kernel = trial.suggest_categorical("kernel", ["linear", "rbf", "poly", "sigmoid"])
    params: dict[str, Any] = {
        "C": trial.suggest_float("C", 1e-3, 100.0, log=True),
        "kernel": kernel,
        "class_weight": trial.suggest_categorical("class_weight", [None, "balanced"]),
    }
    if kernel != "linear":
        params["gamma"] = trial.suggest_float("gamma", 1e-4, 10.0, log=True)
    return params


def suggest_adaboost_params(trial) -> dict[str, Any]:
    return {
        "n_estimators": trial.suggest_int("n_estimators", 50, 800),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 2.0, log=True),
        "estimator_max_depth": trial.suggest_int("estimator_max_depth", 1, 5),
    }


def suggest_lightgbm_params(trial) -> dict[str, Any]:
    return {
        "n_estimators": trial.suggest_int("n_estimators", 100, 1200),
        "num_leaves": trial.suggest_int("num_leaves", 7, 127),
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
    }


def suggest_gnb_params(trial) -> dict[str, Any]:
    return {
        "var_smoothing": trial.suggest_float("var_smoothing", 1e-12, 1e-6, log=True),
    }


def suggest_cnb_params(trial) -> dict[str, Any]:
    return {
        "alpha": trial.suggest_float("alpha", 1e-4, 10.0, log=True),
    }


def suggest_mlp_params(trial) -> dict[str, Any]:
    hidden_layer_size_options = {
        "16": (16,),
        "32": (32,),
        "64": (64,),
        "32_16": (32, 16),
        "64_32": (64, 32),
    }
    hidden_layer_size_key = trial.suggest_categorical(
        "hidden_layer_size",
        list(hidden_layer_size_options),
    )
    return {
        "hidden_layer_sizes": hidden_layer_size_options[hidden_layer_size_key],
        "alpha": trial.suggest_float("alpha", 1e-6, 1e-1, log=True),
        "learning_rate_init": trial.suggest_float("learning_rate_init", 1e-5, 1e-1, log=True),
    }


def _positive_negative_ratio(y_train) -> float:
    y_arr = np.asarray(y_train)
    positives = int(np.sum(y_arr == 1))
    negatives = int(np.sum(y_arr == 0))
    return float(negatives / positives) if positives else 1.0


def _suggest_params(model_name: str, trial, y_train) -> dict[str, Any]:
    if model_name == "XGBoost":
        return suggest_xgboost_params(trial, _positive_negative_ratio(y_train))
    if model_name == "Logistic Regression":
        return suggest_logistic_regression_params(trial)
    if model_name == "SVM":
        return suggest_svm_params(trial)
    if model_name == "AdaBoost":
        return suggest_adaboost_params(trial)
    if model_name == "LightGBM":
        return suggest_lightgbm_params(trial)
    if model_name == "GNB":
        return suggest_gnb_params(trial)
    if model_name == "CNB":
        return suggest_cnb_params(trial)
    if model_name == "MLP":
        return suggest_mlp_params(trial)
    if model_name == "TabPFN-3-Plus":
        raise ValueError(f"Tuning is not supported for {model_name}")
    raise ValueError(f"Tuning is not supported for model: {model_name}")


def _slice_rows(X, idx):
    if hasattr(X, "iloc"):
        return X.iloc[idx]
    return np.asarray(X)[idx]


def _mean_cv_auc(model, X_train, y_train, cv_strategy) -> float:
    fold_scores = []
    y_arr = np.asarray(y_train)
    for train_idx, val_idx in cv_strategy.split(X_train, y_arr):
        X_fold_train = _slice_rows(X_train, train_idx)
        X_fold_val = _slice_rows(X_train, val_idx)
        y_fold_train = y_arr[train_idx]
        y_fold_val = y_arr[val_idx]

        estimator = clone(model)
        estimator.fit(X_fold_train, y_fold_train)
        y_pred = estimator.predict(X_fold_val)
        y_prob = _extract_positive_class_probability(estimator, X_fold_val, y_pred)
        fold_scores.append(float(roc_auc_score(y_fold_val, y_prob)))
    return float(np.mean(fold_scores))


def tune_models(
    X_train,
    y_train,
    budget: dict[str, int],
    cv_splits: int = 10,
    random_state: int = 42,
) -> dict[str, dict[str, Any]]:
    positive_budget = {model_name: n_trials for model_name, n_trials in budget.items() if n_trials > 0}
    if not positive_budget:
        return {}

    optuna = _import_optuna()
    results: dict[str, dict[str, Any]] = {}
    cv_strategy = StratifiedKFold(n_splits=cv_splits, shuffle=True, random_state=random_state)

    for model_name, n_trials in positive_budget.items():

        def objective(trial):
            params = _suggest_params(model_name, trial, y_train)
            trial.set_user_attr("model_params", params)
            model = get_models(tuned_params={model_name: params})[model_name]
            try:
                return _mean_cv_auc(model, X_train, y_train, cv_strategy)
            except ValueError:
                return _FAILED_TRIAL_AUC

        sampler = optuna.samplers.TPESampler(seed=random_state)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
        best_params = dict(study.best_trial.user_attrs.get("model_params", study.best_params))
        results[model_name] = {
            "best_score": float(study.best_value),
            "n_trials": int(len(study.trials)),
            "best_params": best_params,
        }

        fixed_params = _fixed_params_for_model(model_name, y_train, study.best_params)
        results[model_name]["best_params"].update(fixed_params)

    return results


def run_tuning(
    train_path: Path,
    test_path: Path,
    models_dir: Path,
    budget_name: str = "deep",
    model_budget: dict[str, int] | None = None,
    cv_splits: int = 10,
    random_state: int = 42,
) -> dict[str, str]:
    models_dir.mkdir(parents=True, exist_ok=True)

    if str(train_path).endswith(".csv"):
        X_train_raw, y_train, _ = load_flat_csv(str(train_path), require_target=True)
    else:
        X_train_raw, y_train, _ = load_and_flatten_data(str(train_path), require_target=True)

    if str(test_path).endswith(".csv"):
        X_test_raw, _, _ = load_flat_csv(str(test_path), require_target=False)
    else:
        X_test_raw, _, _ = load_and_flatten_data(str(test_path), require_target=False)

    y_train = y_train.astype(int)

    preprocessor_path = models_dir / "preprocessor.joblib"
    preprocessor_payload = load_preprocessor_bundle(preprocessor_path)
    selected_features = preprocessor_payload.get("sel_features", [])
    if not selected_features:
        raise ValueError(
            "No selected features found in preprocessor.joblib. Please run 'main.py select-features' first."
        )

    # If the input data has already been filtered down to selected features,
    # we just use the columns as is. Otherwise, we filter X_train_raw down to selected_features.
    if all(col in X_train_raw.columns for col in selected_features):
        X_train_sel = X_train_raw[selected_features]
    else:
        kept_cols = preprocessor_payload["kept_cols"]
        X_train_prep = X_train_raw[kept_cols]
        X_train_sel = X_train_prep[selected_features]

    budget = dict(model_budget) if model_budget is not None else build_budget(budget_name)
    print(f"[TUNE][INFO] Starting hyperparameter tuning with budget='{budget_name}': {budget}")
    studies = tune_models(
        X_train_sel,
        y_train,
        budget=budget,
        cv_splits=cv_splits,
        random_state=random_state,
    )
    payload = build_tuning_payload(
        budget_name=budget_name,
        selected_features=selected_features,
        studies=studies,
        random_state=random_state,
        cv_splits=cv_splits,
    )
    artifact_path = models_dir / TUNING_ARTIFACT_NAME
    save_tuning_results(artifact_path, payload)
    print(f"[TUNE][INFO] Saved tuning results to {artifact_path}")
    return {"tuning_results_path": str(artifact_path)}


def _fixed_params_for_model(model_name: str, y_train, best_params: dict[str, Any]) -> dict[str, Any]:
    if model_name == "XGBoost":
        return {"tree_method": "hist"}
    return {}


def build_tuning_payload(
    budget_name: str,
    selected_features: list[str],
    studies: dict[str, dict[str, Any]],
    random_state: int = 42,
    cv_splits: int = 10,
) -> dict[str, Any]:
    ranking = [
        {"model": model_name, "best_score": float(model_payload["best_score"])}
        for model_name, model_payload in studies.items()
    ]
    ranking.sort(key=lambda row: row["best_score"], reverse=True)
    payload = {
        "schema_version": "1",
        "created_at": datetime.now(UTC).isoformat(),
        "random_state": random_state,
        "cv": {
            "type": "StratifiedKFold",
            "n_splits": cv_splits,
            "shuffle": True,
        },
        "metric": "roc_auc",
        "budget": budget_name,
        "selected_features": list(selected_features),
        "models": studies,
        "ranking": ranking,
    }
    validate_tuning_results(payload)
    return payload
