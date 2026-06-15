import csv
import json
from pathlib import Path
from typing import cast
import numpy as np
import pandas as pd
import joblib
from scipy.stats import mannwhitneyu, chi2_contingency
from sklearn.metrics import roc_auc_score, roc_curve, accuracy_score, recall_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold

from src.config import MODELS_DIR
from src.data_loader import parse_and_flatten_raw
from src.hyperparameter_tuning import load_tuned_params_from_models_dir
from src.models import get_models


def _metric_point_estimate(metric_value: str) -> float:
    try:
        return float(str(metric_value).split()[0])
    except (IndexError, TypeError, ValueError):
        return float("-inf")


def _sort_rows_by_metric_desc(rows: list[dict[str, str]], metric_key: str) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: _metric_point_estimate(row.get(metric_key, "")), reverse=True)


def run_table_1_generation(raw_train_path: Path, output_dir: Path) -> None:
    print("[TABLES] Generating Table 1: Baseline Characteristics...")
    df = parse_and_flatten_raw(str(raw_train_path), require_target=True)
    df_non_aki = df[df["akdPositive"] == 0]
    df_aki = df[df["akdPositive"] == 1]
    
    N_total = len(df)
    N_non_aki = len(df_non_aki)
    N_aki = len(df_aki)
    
    table_rows = []
    
    # 1. Continuous variables
    continuous_vars = [
        {"name": "Age, years", "col": "age", "decimals": 1},
        {"name": "Weight, Kg", "col": "weight", "decimals": 1},
        {"name": "HR, beats/min", "col": "hr", "decimals": 1},
        {"name": "RR, breaths/min", "col": "rr", "decimals": 1},
        {"name": "SBP, mmHg", "col": "sbp", "decimals": 1},
        {"name": "DBP, mmHg", "col": "dbp", "decimals": 1},
        {"name": "Bicarbonate, mEq/L", "col": "bicarbonate", "decimals": 1},
        {"name": "WBC, K/μL", "col": "wbc", "decimals": 1},
        {"name": "PLT, K/μL", "col": "plt", "decimals": 1},
        {"name": "Hb, g/dl", "col": "hb", "decimals": 1},
        {"name": "Phosphate, mEq/L", "col": "phosphate", "decimals": 1},
        {"name": "Calcium, mEq/L", "col": "calcium", "decimals": 1},
        {"name": "AG", "col": "ag", "decimals": 1},
        {"name": "BUN, mg/dl", "col": "bun", "decimals": 1},
        {"name": "Scr, mg/dl", "col": "scr", "decimals": 1},
        {"name": "Blood glucose, mg/dl", "col": "bg", "decimals": 1},
        {"name": "eGFR", "col": "egfr", "decimals": 1},
        {"name": "GCS", "col": "gcs", "decimals": 1},
        {"name": "OASIS", "col": "oasis", "decimals": 1},
        {"name": "SOFA", "col": "sofa", "decimals": 1},
        {"name": "SAPSII", "col": "saps2", "decimals": 1},
    ]
    
    for c_var in continuous_vars:
        col = cast(str, c_var["col"])
        dec = cast(int, c_var["decimals"])
        
        # Extracted clean values
        tot_vals = df[col].dropna().values
        non_vals = df_non_aki[col].dropna().values
        aki_vals = df_aki[col].dropna().values
        
        if len(non_vals) > 0 and len(aki_vals) > 0:
            _, p_val = mannwhitneyu(non_vals, aki_vals, alternative="two-sided")
            p_str = "<0.001" if p_val < 0.001 else f"{p_val:.3f}"
        else:
            p_str = "NA"
            
        # Capture dec in a local variable to avoid issues
        current_dec = dec
        def get_stat_str(vals) -> str:
            if len(vals) == 0:
                return "NA"
            med = np.median(vals)
            q25 = np.percentile(vals, 25)
            q75 = np.percentile(vals, 75)
            return f"{med:.{current_dec}f} [{q25:.{current_dec}f}, {q75:.{current_dec}f}]"
            
        table_rows.append({
            "Variable": cast(str, c_var["name"]),
            f"Total (n = {N_total:,})": get_stat_str(tot_vals),
            f"Non-AKI (n = {N_non_aki:,})": get_stat_str(non_vals),
            f"AKI (n = {N_aki:,})": get_stat_str(aki_vals),
            "p value": p_str
        })
        
    # 2. Binary variables
    binary_vars = [
        {"name": "Gender (Female)", "col": "gender", "val": [0]},
        {"name": "Microangiopathy (Yes)", "col": "microangiopathy", "val": [1]},
        {"name": "Macroangiopathy (Yes)", "col": "macroangiopathy", "val": [1]},
        {"name": "UTI (Yes)", "col": "uti", "val": [1, True]},
        {"name": "Chronic Pulmonary Disease (Yes)", "col": "chronic_pulmonary_disease", "val": [1, True]},
        {"name": "Liver disease (Yes)", "col": "liver_disease", "val": [1, 2]},
        {"name": "History of hypertension (Yes)", "col": "hypertension", "val": [1, True]},
        {"name": "History of CHF (Yes)", "col": "congestive_heart_failure", "val": [1, True]},
        {"name": "History of AMI (Yes)", "col": "history_ami", "val": [1, True]},
        {"name": "History of ACI (Yes)", "col": "history_aci", "val": [1, True]},
        {"name": "Malignant Cancer (Yes)", "col": "malignant_cancer", "val": [1, True]},
    ]
    
    for b_var in binary_vars:
        col = cast(str, b_var["col"])
        vals = cast(list, b_var["val"])
        
        # Count positive cases
        tot_pos = df[col].isin(vals).sum()
        non_pos = df_non_aki[col].isin(vals).sum()
        aki_pos = df_aki[col].isin(vals).sum()
        
        # Chi-square p-value
        c_table = [[non_pos, aki_pos], [N_non_aki - non_pos, N_aki - aki_pos]]
        try:
            _, p_val, _, _ = chi2_contingency(c_table, correction=True)
            p_str = "<0.001" if p_val < 0.001 else f"{p_val:.3f}"
        except Exception:
            p_str = "NA"
            
        table_rows.append({
            "Variable": cast(str, b_var["name"]),
            f"Total (n = {N_total:,})": f"{tot_pos:,} ({tot_pos / N_total * 100:.1f})",
            f"Non-AKI (n = {N_non_aki:,})": f"{non_pos:,} ({non_pos / N_non_aki * 100:.1f})",
            f"AKI (n = {N_aki:,})": f"{aki_pos:,} ({aki_pos / N_aki * 100:.1f})",
            "p value": p_str
        })
        
    # 3. Multi-categorical variables
    categorical_vars = [
        {
            "name": "Ethnicity",
            "col": "race",
            "categories": [
                {"name": "White", "codes": (0, 17, 18, 19, 20)},
                {"name": "African-American", "codes": (1, 8, 9, 10)},
                {"name": "Hispanic-American", "codes": (4, 11, 12, 13, 14, 15, 16, 24)},
                {"name": "Asian", "codes": (5, 6, 7)},
                {"name": "Other", "codes": None}  # fallback
            ]
        },
        {
            "name": "DM type",
            "col": "dka_type",
            "categories": [
                {"name": "T1DM", "codes": (1,)},
                {"name": "T2DM", "codes": (2,)},
                {"name": "Other", "codes": (0,)}
            ]
        },
        {
            "name": "Preexisting CKD",
            "col": "ckd_stage",
            "categories": [
                {"name": "Non-CKD", "codes": (0, None)},
                {"name": "Stage1-3", "codes": (1, 2, 3)},
                {"name": "Stage 4", "codes": (4,)}
            ]
        }
    ]
    
    for m_var in categorical_vars:
        col = cast(str, m_var["col"])
        cats = cast(list, m_var["categories"])
        
        # Build contingency table
        contingency = []
        cat_counts = []
        
        for cat in cats:
            codes = cat["codes"]
            if codes is None:
                # Other / fallback
                # Find all codes that were NOT handled by other categories
                handled_codes = []
                for other_cat in cats:
                    if other_cat["codes"] is not None:
                        handled_codes.extend([c for c in other_cat["codes"] if c is not None])
                
                tot_mask = ~df[col].isin(handled_codes)
                non_mask = ~df_non_aki[col].isin(handled_codes)
                aki_mask = ~df_aki[col].isin(handled_codes)
            else:
                has_none = None in codes
                non_null_codes = [c for c in codes if c is not None]
                
                if has_none:
                    tot_mask = df[col].isin(non_null_codes) | df[col].isna()
                    non_mask = df_non_aki[col].isin(non_null_codes) | df_non_aki[col].isna()
                    aki_mask = df_aki[col].isin(non_null_codes) | df_aki[col].isna()
                else:
                    tot_mask = df[col].isin(non_null_codes)
                    non_mask = df_non_aki[col].isin(non_null_codes)
                    aki_mask = df_aki[col].isin(non_null_codes)
            
            tot_count = tot_mask.sum()
            non_count = non_mask.sum()
            aki_count = aki_mask.sum()
            
            contingency.append([non_count, aki_count])
            cat_counts.append({
                "sub_name": cat["name"],
                "tot": tot_count,
                "non": non_count,
                "aki": aki_count
            })
            
        # Global p-value
        try:
            _, p_val, _, _ = chi2_contingency(contingency, correction=True)
            p_str = "<0.001" if p_val < 0.001 else f"{p_val:.3f}"
        except Exception:
            p_str = "NA"
            
        # Header row
        table_rows.append({
            "Variable": cast(str, m_var["name"]),
            f"Total (n = {N_total:,})": "",
            f"Non-AKI (n = {N_non_aki:,})": "",
            f"AKI (n = {N_aki:,})": "",
            "p value": p_str
        })
        
        # Sub-category rows
        for cc in cat_counts:
            sub_name = cc["sub_name"]
            t_cnt = cc["tot"]
            n_cnt = cc["non"]
            a_cnt = cc["aki"]
            table_rows.append({
                "Variable": f"  {sub_name}",
                f"Total (n = {N_total:,})": f"{t_cnt:,} ({t_cnt / N_total * 100:.1f})",
                f"Non-AKI (n = {N_non_aki:,})": f"{n_cnt:,} ({n_cnt / N_non_aki * 100:.1f})",
                f"AKI (n = {N_aki:,})": f"{a_cnt:,} ({a_cnt / N_aki * 100:.1f})",
                "p value": ""
            })
            
    # Save files
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = ["Variable", f"Total (n = {N_total:,})", f"Non-AKI (n = {N_non_aki:,})", f"AKI (n = {N_aki:,})", "p value"]
    
    # MD format
    md_lines = ["# TABLE 1: Characteristic at baseline between AKI and non-AKI group.", ""]
    md_lines.append(" | ".join(headers))
    md_lines.append(" | ".join(["---"] * len(headers)))
    for r in table_rows:
        md_lines.append(" | ".join([r[h] for h in headers]))
        
    (output_dir / "table_1_baseline_characteristics.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    
    # CSV format
    with (output_dir / "table_1_baseline_characteristics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in table_rows:
            writer.writerow(r)
            
    print("[TABLES] Table 1 generated successfully!")


def evaluate_youden_optimal(y_true, y_prob):
    """Calculate all metrics using the threshold that maximizes Youden's J statistic."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    
    if len(np.unique(y_true)) < 2:
        return {
            "AUC": np.nan, "Cutoff": np.nan, "Accuracy": np.nan, "Sensitivity": np.nan,
            "Specificity": np.nan, "PPV": np.nan, "NPV": np.nan, "F1-Score": np.nan
        }
        
    auc = float(roc_auc_score(y_true, y_prob))
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    youden = tpr - fpr
    opt_idx = np.argmax(youden)
    opt_cutoff = float(thresholds[opt_idx])
    
    # Clip optimal cutoff to [0.0, 1.0] if needed
    if opt_cutoff > 1.0:
        opt_cutoff = 1.0
    elif opt_cutoff < 0.0:
        opt_cutoff = 0.0
        
    y_pred = (y_prob >= opt_cutoff).astype(int)
    acc = float(accuracy_score(y_true, y_pred))
    sens = float(recall_score(y_true, y_pred, zero_division=0))
    
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    spec = float(tn / (tn + fp) if (tn + fp) > 0 else 0.0)
    ppv = float(tp / (tp + fp) if (tp + fp) > 0 else 0.0)
    npv = float(tn / (tn + fn) if (tn + fn) > 0 else 0.0)
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    
    return {
        "AUC": auc,
        "Cutoff": opt_cutoff,
        "Accuracy": acc,
        "Sensitivity": sens,
        "Specificity": spec,
        "PPV": ppv,
        "NPV": npv,
        "F1-Score": f1
    }


def evaluate_with_fixed_cutoff(y_true, y_prob, cutoff):
    """Calculate all metrics using a fixed threshold/cutoff."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    
    if len(np.unique(y_true)) < 2:
        return {
            "AUC": np.nan, "Cutoff": cutoff, "Accuracy": np.nan, "Sensitivity": np.nan,
            "Specificity": np.nan, "PPV": np.nan, "NPV": np.nan, "F1-Score": np.nan
        }
        
    auc = float(roc_auc_score(y_true, y_prob))
    y_pred = (y_prob >= cutoff).astype(int)
    acc = float(accuracy_score(y_true, y_pred))
    sens = float(recall_score(y_true, y_pred, zero_division=0))
    
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    spec = float(tn / (tn + fp) if (tn + fp) > 0 else 0.0)
    ppv = float(tp / (tp + fp) if (tp + fp) > 0 else 0.0)
    npv = float(tn / (tn + fn) if (tn + fn) > 0 else 0.0)
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    
    return {
        "AUC": auc,
        "Cutoff": cutoff,
        "Accuracy": acc,
        "Sensitivity": sens,
        "Specificity": spec,
        "PPV": ppv,
        "NPV": npv,
        "F1-Score": f1
    }


def run_table_2_generation(
    X_train_sel: pd.DataFrame,
    y_train: pd.Series,
    output_dir: Path,
    models_dir: Path | None = None,
    training_summary: dict[str, dict[str, int]] | None = None,
) -> None:
    print("[TABLES] Generating Table 2: Model parameters in training set (10-Fold CV)...")
    models_dir = MODELS_DIR if models_dir is None else Path(models_dir)
    training_summary = training_summary or {}
    
    models = get_models(tuned_params=load_tuned_params_from_models_dir(models_dir))
    cv = StratifiedKFold(n_splits=10, shuffle=True, random_state=42)
    
    table_rows = []
    fold_cutoffs = {}
    
    from src.evaluate import _extract_positive_class_probability
    
    for model_name, model in models.items():
        print(f"[TABLES] Training & Cross-Validating {model_name}...")
        
        fold_metrics = []
        model_cutoffs = []
        has_error = False
        
        for train_idx, val_idx in cv.split(X_train_sel, y_train):
            X_tr, y_tr = X_train_sel.iloc[train_idx], y_train.iloc[train_idx]
            X_va, y_va = X_train_sel.iloc[val_idx], y_train.iloc[val_idx]
            
            try:
                # Fit on training fold
                from sklearn.base import clone
                estimator = clone(model)
                estimator.fit(X_tr, y_tr)
                
                # Predict probabilities
                y_pred = estimator.predict(X_va)
                y_prob = _extract_positive_class_probability(estimator, X_va, y_pred)
                
                fold_res = evaluate_youden_optimal(y_va, y_prob)
                fold_metrics.append(fold_res)
                model_cutoffs.append(fold_res["Cutoff"])
            except Exception as e:
                print(f"[TABLES][WARNING] Lỗi khi chạy fold CV cho {model_name}: {e}")
                has_error = True
                break
            
        if has_error:
            fold_cutoffs[model_name] = [0.5] * 10
        else:
            fold_cutoffs[model_name] = model_cutoffs
        
        # Compute mean and SD for each metric
        keys = ["AUC", "Cutoff", "Accuracy", "Sensitivity", "Specificity", "PPV", "NPV", "F1-Score"]
        row = {"Model": model_name}
        row["Iterations"] = str(training_summary.get(model_name, {}).get("n_iter", "NA"))
        
        for k in keys:
            if has_error:
                row[k] = "NA (Limit)"
            else:
                vals = [fm[k] for fm in fold_metrics if not np.isnan(fm[k])]
                if len(vals) == 0:
                    row[k] = "NA"
                else:
                    m = np.mean(vals)
                    s = np.std(vals)
                    row[k] = f"{m:.3f} ({s:.3f})"
                
        table_rows.append(row)
        
    # Save fold cutoffs for Table 3
    cutoffs_file = models_dir / "fold_cutoffs.json"
    with open(cutoffs_file, "w", encoding="utf-8") as f:
        json.dump(fold_cutoffs, f, indent=2)
        
    table_rows = _sort_rows_by_metric_desc(table_rows, "AUC")

    # Save files
    headers = ["Model", "Iterations", "AUC", "Cutoff", "Accuracy", "Sensitivity", "Specificity", "PPV", "NPV", "F1-Score"]
    
    # MD format
    md_lines = ["# TABLE 2: Model parameters in training set.", ""]
    md_lines.append(" | ".join(headers))
    md_lines.append(" | ".join(["---"] * len(headers)))
    for r in table_rows:
        md_lines.append(" | ".join([r[h] for h in headers]))
        
    (output_dir / "table_2_model_parameters_training_set.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    
    # CSV format
    with (output_dir / "table_2_model_parameters_training_set.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in table_rows:
            writer.writerow(r)
            
    print("[TABLES] Table 2 generated successfully!")


def run_table_3_generation(
    X_test_sel: pd.DataFrame,
    y_test: pd.Series,
    output_dir: Path,
    models_dir: Path | None = None,
) -> None:
    print("[TABLES] Generating Table 3: Model parameters in validation set (Bootstrapping with Train Cutoffs)...")
    models_dir = MODELS_DIR if models_dir is None else Path(models_dir)
    
    # Load fold cutoffs from training
    cutoffs_file = models_dir / "fold_cutoffs.json"
    if cutoffs_file.exists():
        with open(cutoffs_file, encoding="utf-8") as f:
            fold_cutoffs = json.load(f)
    else:
        print("[TABLES][WARNING] Missing fold_cutoffs.json, will fallback to 0.5 as cutoff")
        fold_cutoffs = {}
        
    # Load Table 2 to copy exact Cutoff strings
    table_2_file = output_dir / "table_2_model_parameters_training_set.csv"
    table_2_cutoffs = {}
    if table_2_file.exists():
        with open(table_2_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                table_2_cutoffs[row["Model"]] = row["Cutoff"]
                
    models = get_models(tuned_params=load_tuned_params_from_models_dir(models_dir))
    table_rows = []
    
    from src.evaluate import _extract_positive_class_probability
    
    rng = np.random.default_rng(42)
    pos_idx = np.where(y_test == 1)[0]
    neg_idx = np.where(y_test == 0)[0]
    n_bootstraps = 100
    
    # Pre-generate bootstrap indices to ensure identical evaluation sets for all models (paired bootstrap)
    boot_indices = []
    for i in range(n_bootstraps):
        pos_boot = rng.choice(pos_idx, size=len(pos_idx), replace=True)
        neg_boot = rng.choice(neg_idx, size=len(neg_idx), replace=True)
        boot_indices.append(np.concatenate([pos_boot, neg_boot]))
    
    for model_name, model in models.items():
        print(f"[TABLES] Evaluating {model_name} with bootstrapping on test set...")
        model_path = models_dir / f"{model_name.lower().replace(' ', '_')}.joblib"
        if not model_path.exists():
            print(f"[TABLES][WARNING] Missing fitted model for {model_name}")
            continue
            
        fit_model = joblib.load(model_path)
        
        # Get raw predictions on the full test set
        y_pred_full = fit_model.predict(X_test_sel)
        y_prob_full = _extract_positive_class_probability(fit_model, X_test_sel, y_pred_full)
        
        # Retrieve training cutoffs for this model
        train_cutoffs = fold_cutoffs.get(model_name, [0.5] * 10)
        mean_cutoff = np.mean(train_cutoffs)
        
        # 1. Calculate point estimates on the full validation set
        auc_full = float(roc_auc_score(y_test, y_prob_full))
        y_pred_at_cutoff = (y_prob_full >= mean_cutoff).astype(int)
        acc_full = float(accuracy_score(y_test, y_pred_at_cutoff))
        sens_full = float(recall_score(y_test, y_pred_at_cutoff, zero_division=0))
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred_at_cutoff, labels=[0, 1]).ravel()
        spec_full = float(tn / (tn + fp) if (tn + fp) > 0 else 0.0)
        ppv_full = float(tp / (tp + fp) if (tp + fp) > 0 else 0.0)
        npv_full = float(tn / (tn + fn) if (tn + fn) > 0 else 0.0)
        f1_full = float(f1_score(y_test, y_pred_at_cutoff, zero_division=0))
        
        full_metrics = {
            "AUC": auc_full,
            "Accuracy": acc_full,
            "Sensitivity": sens_full,
            "Specificity": spec_full,
            "PPV": ppv_full,
            "NPV": npv_full,
            "F1-Score": f1_full
        }
        
        # 2. Bootstrapping to get standard deviations
        boot_metrics = []
        for i in range(n_bootstraps):
            boot_idx = boot_indices[i]
            y_true_boot = y_test.iloc[boot_idx].values
            y_prob_boot = y_prob_full[boot_idx]
            
            # Apply training Youden cutoff corresponding to the bootstrap sample index
            cutoff_val = float(train_cutoffs[i % len(train_cutoffs)])
            
            boot_res = evaluate_with_fixed_cutoff(y_true_boot, y_prob_boot, cutoff_val)
            boot_metrics.append(boot_res)
            
        # Compute mean and SD for each metric
        keys = ["AUC", "Accuracy", "Sensitivity", "Specificity", "PPV", "NPV", "F1-Score"]
        row = {"Model": model_name}
        
        # Copy exact Cutoff string from Table 2 to match the paper perfectly
        row["Cutoff"] = table_2_cutoffs.get(model_name, "0.500 (0.000)")
        
        for k in keys:
            vals = [bm[k] for bm in boot_metrics if not np.isnan(bm[k])]
            if len(vals) == 0:
                row[k] = "NA"
            else:
                std_val = np.std(vals)
                point_val = full_metrics[k]
                row[k] = f"{point_val:.3f} ({std_val:.3f})"
                
        table_rows.append(row)

    table_rows = _sort_rows_by_metric_desc(table_rows, "AUC")

    # Save files
    headers = ["Model", "AUC", "Cutoff", "Accuracy", "Sensitivity", "Specificity", "PPV", "NPV", "F1-Score"]
    
    # MD format
    md_lines = ["# TABLE 3: Model parameters in validation set.", ""]
    md_lines.append(" | ".join(headers))
    md_lines.append(" | ".join(["---"] * len(headers)))
    for r in table_rows:
        md_lines.append(" | ".join([r[h] for h in headers]))
        
    (output_dir / "table_3_model_parameters_validation_set.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    
    # CSV format
    with (output_dir / "table_3_model_parameters_validation_set.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in table_rows:
            writer.writerow(r)
            
    print("[TABLES] Table 3 generated successfully!")
