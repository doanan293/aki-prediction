from __future__ import annotations

from pathlib import Path
from typing import Any
import pandas as pd

from src.artifacts import load_preprocessor_bundle, save_preprocessor_bundle
from src.config import TABLES_DIR, IMAGES_DIR
from src.data_loader import load_flat_csv
from src.feature_selection import select_features_shap
from src.visualization import plot_shap_importance


def _shap_importance_value(row: dict[str, Any]) -> float:
    value = row.get("SHAP Importance")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")


def _sort_feature_selection_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_shap_importance_value, reverse=True)


def run_select_features(
    train_path: Path,
    test_path: Path,
    models_dir: Path,
    tables_dir: Path | None = None,
    images_dir: Path | None = None,
) -> dict[str, Any]:
    models_dir.mkdir(parents=True, exist_ok=True)

    if tables_dir is None:
        tables_dir = TABLES_DIR
    else:
        tables_dir = Path(tables_dir)

    if images_dir is None:
        images_dir = IMAGES_DIR
    else:
        images_dir = Path(images_dir)

    # 1. Load data
    if str(train_path).endswith(".csv"):
        X_train_raw, y_train, _ = load_flat_csv(str(train_path), require_target=True)
    else:
        from src.data_loader import load_and_flatten_data

        X_train_raw, y_train, _ = load_and_flatten_data(str(train_path), require_target=True)

    if str(test_path).endswith(".csv"):
        X_test_raw, _, _ = load_flat_csv(str(test_path), require_target=False)
    else:
        from src.data_loader import load_and_flatten_data

        X_test_raw, _, _ = load_and_flatten_data(str(test_path), require_target=False)

    y_train = y_train.astype(int)

    # 2. Load preprocessor bundle
    preprocessor_path = models_dir / "preprocessor.joblib"
    preprocessor_payload = load_preprocessor_bundle(preprocessor_path)
    prep_artifacts = preprocessor_payload["prep_artifacts"]
    kept_cols = preprocessor_payload["kept_cols"]

    # 3. Filter train/test to kept_cols
    X_train_prep = X_train_raw[kept_cols]
    X_test_prep = X_test_raw[kept_cols]

    # 4. Perform SHAP feature selection
    print(f"[FEATURE][INFO] Running SHAP feature selection on {len(kept_cols)} features...")
    X_train_sel, X_test_sel, sel_features, meta = select_features_shap(
        X_train_prep,
        y_train,
        X_test_prep,
        n_features=20,
    )
    print(f"[FEATURE][INFO] Selected {len(sel_features)} features: {sel_features}")

    # 5. Overwrite the preprocessor bundle with the selected features
    save_preprocessor_bundle(
        out_path=preprocessor_path,
        prep_artifacts=prep_artifacts,
        kept_cols=kept_cols,
        sel_features=sel_features,
        target_name="akdPositive",
    )
    print(f"[FEATURE][INFO] Updated preprocessor bundle at {preprocessor_path}")

    # 6. Overwrite the CSV files with only the selected features (preserving ID and target columns)
    drop_cols = ["subjectId", "hadmId", "stayId", "akdPositive"]

    # Overwrite train.csv
    if train_path.exists():
        df_train = pd.read_csv(train_path)
        existing_drop_cols_train = [col for col in drop_cols if col in df_train.columns]
        df_train_sel = pd.concat([df_train[existing_drop_cols_train], X_train_sel], axis=1)
        df_train_sel.to_csv(train_path, index=False)
        print(f"[FEATURE][INFO] Overwrote train CSV at {train_path}")

    # Overwrite test.csv
    if test_path.exists():
        df_test = pd.read_csv(test_path)
        existing_drop_cols_test = [col for col in drop_cols if col in df_test.columns]
        df_test_sel = pd.concat([df_test[existing_drop_cols_test], X_test_sel], axis=1)
        df_test_sel.to_csv(test_path, index=False)
        print(f"[FEATURE][INFO] Overwrote test CSV at {test_path}")

    # Overwrite unlabeled_test.csv if it exists
    unlabeled_path = test_path.parent / "unlabeled_test.csv"
    if unlabeled_path.exists():
        df_unlabeled = pd.read_csv(unlabeled_path)
        existing_drop_cols_unlabeled = [col for col in drop_cols if col in df_unlabeled.columns]
        X_unlabeled_sel = df_unlabeled[sel_features]
        df_unlabeled_sel = pd.concat([df_unlabeled[existing_drop_cols_unlabeled], X_unlabeled_sel], axis=1)
        df_unlabeled_sel.to_csv(unlabeled_path, index=False)
        print(f"[FEATURE][INFO] Overwrote unlabeled test CSV at {unlabeled_path}")

    # 7. Save SHAP feature importance plot
    images_dir.mkdir(parents=True, exist_ok=True)
    active_coefs = {k: v for k, v in meta["coefficients"].items() if k in sel_features}
    feature_importance_plot_path = images_dir / "shap-feature-importance.png"
    plot_shap_importance(active_coefs, output_path=str(feature_importance_plot_path))
    print(f"[FEATURE][INFO] Saved SHAP feature importance plot to {feature_importance_plot_path}")

    # 8. Save feature selection results table
    tables_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for col in kept_cols:
        coef = meta["coefficients"].get(col, 0.0)
        status = "Kept" if col in sel_features else "Discarded"
        rows.append({"Feature": col, "SHAP Importance": coef, "Status": status})
    rows = _sort_feature_selection_rows(rows)
    df_results = pd.DataFrame(rows)
    results_csv_path = tables_dir / "feature_selection_results.csv"
    df_results.to_csv(results_csv_path, index=False)
    print(f"[FEATURE][INFO] Saved feature selection results table to {results_csv_path}")

    # Save Markdown format
    results_md_path = tables_dir / "feature_selection_results.md"
    md_lines = ["# Feature Selection Results", "", "| Feature | SHAP Importance | Status |", "| --- | --- | --- |"]
    for r in rows:
        md_lines.append(f"| {r['Feature']} | {r['SHAP Importance']} | {r['Status']} |")
    results_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"[FEATURE][INFO] Saved feature selection results markdown table to {results_md_path}")

    return {
        "selected_features": sel_features,
        "results_table_path": str(results_csv_path),
        "preprocessor_path": str(preprocessor_path),
    }
