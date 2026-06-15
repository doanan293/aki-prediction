from __future__ import annotations

import math
from pathlib import Path

import joblib

from src.artifacts import (
    build_registry_payload,
    save_model_registry,
    save_preprocessor_bundle,
    load_preprocessor_bundle,
)
from src.config import IMAGES_DIR, TABLES_DIR
from src.data_loader import load_and_flatten_data, load_flat_csv
from src.evaluate import compute_auc_ci, compute_roc_from_scores, evaluate_model_cv_with_oof
from src.hyperparameter_tuning import TUNING_ARTIFACT_NAME, load_tuned_params_from_models_dir
from src.models import get_models
from src.visualization import plot_roc_split, plot_xgb_feature_importance, plot_tabpfn_feature_importance


def _resolve_selection_metric_key(metrics: dict, select_best_by: str) -> str:
    metric_key = (select_best_by or "auc").strip().lower()
    for key in metrics.keys():
        if key.lower() == metric_key:
            return key

    available = sorted(metrics.keys())
    raise ValueError(f"Invalid select_best_by='{select_best_by}'. Available metrics: {available}")


def _get_metric_score(metrics: dict, metric_key: str) -> float:
    val = metrics[metric_key]
    if isinstance(val, tuple):
        score = float(val[0])
    else:
        score = float(val)
    if math.isnan(score):
        return float("-inf")
    return score


def _extract_training_summary(model_name: str, model) -> dict[str, int] | None:
    if model_name != "MLP" or not hasattr(model, "n_iter_"):
        return None
    try:
        return {"n_iter": int(getattr(model, "n_iter_"))}
    except (TypeError, ValueError):
        return None


def _load_tuned_params_if_available(models_dir: Path) -> dict | None:
    tuned_params = load_tuned_params_from_models_dir(models_dir)
    if tuned_params is None:
        print("[TRAIN][INFO] No tuning_results.json found; using default model parameters.")
        return None
    print(f"[TRAIN][INFO] Loaded tuned model parameters from {models_dir / TUNING_ARTIFACT_NAME}")
    return tuned_params


def run_train(
    train_path: Path,
    test_path: Path,
    models_dir: Path,
    select_best_by: str = "auc",
    tables_dir: Path | None = None,
) -> dict[str, str]:
    models_dir.mkdir(parents=True, exist_ok=True)
    tuned_params = _load_tuned_params_if_available(models_dir)
    if tables_dir is None:
        tables_dir = TABLES_DIR
    else:
        tables_dir = Path(tables_dir)

    if str(train_path).endswith(".csv"):
        X_train_raw, y_train, _ = load_flat_csv(str(train_path), require_target=True)
    else:
        X_train_raw, y_train, _ = load_and_flatten_data(str(train_path), require_target=True)

    if str(test_path).endswith(".csv"):
        X_test_raw, y_test, _ = load_flat_csv(str(test_path), require_target=False)
    else:
        X_test_raw, y_test, _ = load_and_flatten_data(str(test_path), require_target=False)

    if y_test.isna().any() and not y_test.isna().all():
        raise ValueError("Test labels must be all missing or all present (all-or-none requirement)")

    y_train = y_train.astype(int)

    preprocessor_path = models_dir / "preprocessor.joblib"
    preprocessor_payload = load_preprocessor_bundle(preprocessor_path)
    prep_artifacts = preprocessor_payload["prep_artifacts"]
    kept_cols = preprocessor_payload["kept_cols"]

    sel_features = preprocessor_payload.get("sel_features", [])
    if not sel_features:
        raise ValueError(
            "No selected features found in preprocessor.joblib. Please run 'main.py select-features' first."
        )

    if all(col in X_train_raw.columns for col in sel_features):
        X_train_sel = X_train_raw[sel_features]
    else:
        X_train_prep = X_train_raw[kept_cols]
        X_train_sel = X_train_prep[sel_features]

    save_preprocessor_bundle(
        out_path=preprocessor_path,
        prep_artifacts=prep_artifacts,
        kept_cols=kept_cols,
        sel_features=sel_features,
        target_name="akdPositive",
    )

    best_model_name = ""
    best_model_score = float("-inf")
    model_files: dict[str, str] = {}
    metric_snapshot: dict[str, float] = {}
    selected_metric_key: str | None = None

    cv_table_rows = []
    roc_data = {}
    fitted_models = {}
    training_summary: dict[str, dict[str, int]] = {}

    for model_name, model in get_models(tuned_params=tuned_params).items():
        # Evaluate model using 10-Fold Stratified Cross-Validation on the training set
        cv_results, oof_scores = evaluate_model_cv_with_oof(model, X_train_sel, y_train, cv=10)

        if selected_metric_key is None:
            selected_metric_key = _resolve_selection_metric_key(cv_results, select_best_by)

        score = _get_metric_score(cv_results, selected_metric_key)

        mean_val, std_val = cv_results[selected_metric_key]
        print(
            f"[TRAIN][INFO] Model: {model_name:<20} - 10-Fold CV {selected_metric_key}: {mean_val:.4f} ± {std_val:.4f}"
        )

        # Tính toán ROC cho mô hình trên tập OOF
        fpr, tpr, auc_val = compute_roc_from_scores(y_train, oof_scores)
        ci_val = compute_auc_ci(y_train, oof_scores)
        roc_data[model_name] = (fpr, tpr, auc_val, ci_val)

        # Fit on the full training set for deployment persistence
        try:
            model.fit(X_train_sel, y_train)
            fitted_models[model_name] = model
            fit_summary = _extract_training_summary(model_name, model)
            if fit_summary is not None:
                training_summary[model_name] = fit_summary
        except Exception as e:
            print(f"[TRAIN][WARNING] Lỗi khi huấn luyện mô hình {model_name} trên tập Train đầy đủ: {e}")

        model_file = f"{model_name.lower().replace(' ', '_')}.joblib"
        model_path = models_dir / model_file
        try:
            joblib.dump(model, model_path)
        except Exception as e:
            print(f"[TRAIN][WARNING] Lỗi khi lưu mô hình {model_name} vào {model_file}: {e}")

        model_files[model_name] = model_file
        metric_snapshot[model_name] = score

        # Lưu metrics của mô hình để lập bảng
        row = {"Mô hình": model_name}
        for metric, val in cv_results.items():
            if metric == "roc":
                continue
            if isinstance(val, tuple):
                m, s = val
                row[metric] = f"{m:.3f} ± {s:.3f}"
            else:
                row[metric] = f"{val:.3f}"
        cv_table_rows.append(row)

        if not best_model_name or score > best_model_score:
            best_model_score = score
            best_model_name = model_name

    if not best_model_name:
        raise ValueError("No models available for training")

    # 1. Vẽ biểu đồ so sánh ROC 10-Fold CV
    images_path = Path(IMAGES_DIR)
    images_path.mkdir(parents=True, exist_ok=True)
    plot_roc_split(roc_data, "Train ROC Curve", output_path=str(images_path / "train-roc-curve.jpg"))

    # 2. Vẽ biểu đồ độ quan trọng đặc trưng XGBoost
    if "XGBoost" in fitted_models:
        xgb_model = fitted_models["XGBoost"]
        plot_xgb_feature_importance(xgb_model, sel_features, output_path=str(images_path / "xgb-feature-importance.png"))

    # 3. Vẽ biểu đồ độ quan trọng đặc trưng TabPFN (Permutation Importance)
    if "TabPFN-3-Plus" in fitted_models:
        print("[TRAIN][INFO] Calculating permutation feature importance for TabPFN-3-Plus...")
        from sklearn.inspection import permutation_importance
        tabpfn_model = fitted_models["TabPFN-3-Plus"]
        result = permutation_importance(
            tabpfn_model, X_train_sel, y_train, scoring="roc_auc", n_repeats=5, random_state=42
        )
        importance_map = {feat: float(imp) for feat, imp in zip(sel_features, result.importances_mean)}
        plot_tabpfn_feature_importance(
            importance_map, output_path=str(images_path / "tabpfn-feature-importance.png")
        )
        print("[TRAIN][INFO] Saved TabPFN feature importance plot to tabpfn-feature-importance.png")

    # 4. Lưu bảng kết quả 10-Fold CV (Disabled cv_results_table output to restrict output to 3 core tables)

    registry_payload = build_registry_payload(
        best_model_name=best_model_name,
        model_files=model_files,
        selection_metric=select_best_by,
        metric_snapshot=metric_snapshot,
        training_summary=training_summary or None,
    )

    registry_path = models_dir / "model_registry.json"
    save_model_registry(registry_path, registry_payload)

    # 5. Tạo Bảng 1 & Bảng 2 của bài báo
    from src.config import RAW_TRAIN_DATA_PATH
    from src.extract_tables import run_table_1_generation, run_table_2_generation

    tables_output_dir = tables_dir
    try:
        run_table_1_generation(RAW_TRAIN_DATA_PATH, tables_output_dir)
        run_table_2_generation(
            X_train_sel,
            y_train,
            tables_output_dir,
            models_dir=models_dir,
            training_summary=training_summary or None,
        )
    except Exception as e:
        print(f"[TRAIN][WARNING] Lỗi khi tạo Bảng 1 hoặc Bảng 2: {e}")

    return {
        "best_model_name": best_model_name,
        "preprocessor_path": str(preprocessor_path),
        "registry_path": str(registry_path),
    }
