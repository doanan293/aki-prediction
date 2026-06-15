from __future__ import annotations

from numbers import Real
from pathlib import Path

import joblib
import pandas as pd

from src.artifacts import load_model_registry, load_preprocessor_bundle
from src.data_loader import load_and_flatten_data, load_flat_csv
from src.evaluate import evaluate_on_test
from src.visualization import plot_roc_split
from src.config import TABLES_DIR


def transform_with_bundle(X_raw: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    kept_cols = bundle["kept_cols"]
    sel_features = bundle["sel_features"]
    prep_artifacts = bundle["prep_artifacts"]
    active_cat_cols = prep_artifacts.get("active_cat_cols", [])

    # If X_raw already has exactly the selected features,
    # it is already preprocessed and selected.
    if set(X_raw.columns) == set(sel_features):
        return X_raw[sel_features]

    # Validate that required raw columns are present
    non_cat_kept = [col for col in kept_cols if not any(col.startswith(f"{cat}_") for cat in active_cat_cols)]
    missing_non_cat = [col for col in non_cat_kept if col not in X_raw.columns]
    missing_cat = [col for col in active_cat_cols if col not in X_raw.columns]
    if missing_non_cat or missing_cat:
        raise KeyError(f"Missing required columns: {missing_non_cat + missing_cat}")

    # One-hot encode and preserve NaNs for KNN Imputation
    if active_cat_cols:
        X_filtered = X_raw.copy()
        X_encoded = pd.get_dummies(X_filtered, columns=active_cat_cols, drop_first=True, dtype=float)
        
        # Align with kept_cols (dummy columns from train)
        X_encoded = X_encoded.reindex(columns=kept_cols, fill_value=0.0)
        
        # Reset NaNs for the dummy columns on originally missing rows
        import numpy as np
        for col in active_cat_cols:
            orig_nan = X_filtered[col].isna()
            if orig_nan.any():
                dummy_cols = [c for c in X_encoded.columns if c.startswith(f"{col}_")]
                X_encoded.loc[orig_nan, dummy_cols] = np.nan
    else:
        X_encoded = X_raw.reindex(columns=kept_cols, fill_value=0.0)

    X_imputed = pd.DataFrame(
        prep_artifacts["imputer"].transform(X_encoded),
        columns=kept_cols,
        index=X_raw.index,
    )

    return X_imputed[sel_features]


def run_evaluate(
    input_path: Path,
    models_dir: Path,
    model_name: str | None,
    images_dir: Path,
    tables_dir: Path | None = None,
) -> dict[str, float]:
    if tables_dir is None:
        tables_dir = TABLES_DIR
    else:
        tables_dir = Path(tables_dir)
    registry = load_model_registry(models_dir / "model_registry.json")
    chosen_name = model_name or registry["best_model_name"]

    bundle = load_preprocessor_bundle(models_dir / "preprocessor.joblib")

    if str(input_path).endswith(".csv"):
        X_raw, y_raw, _ = load_flat_csv(str(input_path), require_target=True)
    else:
        X_raw, y_raw, _ = load_and_flatten_data(str(input_path), require_target=True)
    if y_raw.isna().any():
        raise ValueError("evaluate requires fully labeled input; unlabeled or partially labeled rows are not supported")

    X_eval = transform_with_bundle(X_raw, bundle)
    y_eval = y_raw.astype(int)

    test_table_rows = []
    roc_data = {}
    decision_curve_prob = None
    decision_curve_model_name = chosen_name
    best_model_metrics = None

    from src.evaluate import _extract_positive_class_probability

    for name, file_name in registry["model_files"].items():
        model_path = models_dir / file_name
        if not model_path.exists():
            continue
        model = joblib.load(model_path)
        metrics = evaluate_on_test(model, X_eval, y_eval)

        if name == chosen_name:
            best_model_metrics = metrics

        if "roc" in metrics and "AUC" in metrics:
            fpr, tpr = metrics["roc"]
            auc_ci = metrics.get("AUC_CI", (float("nan"), float("nan")))
            roc_data[name] = (fpr, tpr, float(metrics["AUC"]), auc_ci)

        if name == decision_curve_model_name:
            y_pred = model.predict(X_eval)
            decision_curve_prob = _extract_positive_class_probability(model, X_eval, y_pred)

        row = {"Mô hình": name}
        for metric, val in metrics.items():
            if metric == "roc":
                continue
            if isinstance(val, (int, float, Real)):
                row[metric] = f"{float(val):.3f}"
            else:
                row[metric] = "NA"
        test_table_rows.append(row)

    if best_model_metrics is None:
        raise KeyError(f"Requested model not found in registry or model files missing: {chosen_name}")

    images_dir.mkdir(parents=True, exist_ok=True)

    # 1. Vẽ biểu đồ ROC so sánh tập test
    plot_roc_split(
        roc_data,
        "Validation ROC Curve",
        output_path=str(images_dir / "validation-roc-curve.jpg"),
    )

    # 2. Vẽ biểu đồ DCA & Calibration theo XGBoost như bài báo gốc.
    if decision_curve_prob is not None:
        from src.visualization import plot_xgb_decision_curve, plot_xgb_calibration_curve

        # Vẽ 2 biểu đồ đơn lẻ chuẩn xác theo bài báo
        plot_xgb_decision_curve(
            y_true=y_eval,
            y_prob=decision_curve_prob,
            output_path=str(images_dir / "test-decision-curve.jpg"),
            model_label=decision_curve_model_name,
        )
        plot_xgb_calibration_curve(
            y_true=y_eval,
            y_prob=decision_curve_prob,
            output_path=str(images_dir / "calibration-plots.jpg"),
            model_label=decision_curve_model_name,
        )

    # 3. Lưu bảng kết quả trên tập test (Disabled test_results_table output to restrict output to 3 core tables)

    # 4. Tạo Bảng 3 của bài báo (Bootstrap trên tập test/validation)
    from src.extract_tables import run_table_3_generation
    try:
        run_table_3_generation(X_eval, y_eval, tables_dir, models_dir=models_dir)
    except Exception as e:
        print(f"[EVALUATE][WARNING] Lỗi khi tạo Bảng 3: {e}")

    out: dict[str, float] = {}
    for key, value in best_model_metrics.items():
        if key in ("roc", "AUC_CI"):
            continue
        if not isinstance(value, Real):
            raise ValueError(f"Metric '{key}' is not numeric: {type(value).__name__}")
        out[key] = float(value)

    return out
