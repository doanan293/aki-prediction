import numpy as np
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold


def _extract_positive_class_probability(model, X_test, y_pred):
    """
    Lấy xác suất lớp dương một cách ổn định.
    Ưu tiên cột ứng với lớp 1 nếu model.classes_ có chứa 1.
    """
    if not hasattr(model, "predict_proba"):
        return y_pred

    proba = model.predict_proba(X_test)
    proba = np.asarray(proba)
    if np.ndim(proba) == 1:
        return proba

    if proba.shape[1] == 1:
        return proba[:, 0]

    positive_index = 1
    classes = getattr(model, "classes_", None)
    if classes is not None:
        classes = np.asarray(classes)
        matches = np.where(classes == 1)[0]
        if len(matches) > 0:
            positive_index = int(matches[0])
        else:
            positive_index = 1

    return proba[:, positive_index]


def _safe_divide(numerator, denominator):
    return float(numerator) / float(denominator) if denominator else 0.0


def _specificity_score(y_true, y_pred):
    tn, fp, _, _ = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return _safe_divide(tn, tn + fp)


def _ppv_score(y_true, y_pred):
    return float(precision_score(y_true, y_pred, zero_division=0))


def _npv_score(y_true, y_pred):
    tn, _, fn, _ = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return _safe_divide(tn, tn + fn)


def compute_roc_from_scores(y_true, y_score):
    """
    Tính ROC từ nhãn thật và điểm dự đoán.
    Trả về fallback an toàn khi y_true chỉ có một lớp.
    """
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)

    if len(np.unique(y_true)) < 2:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0]), np.nan

    fpr, tpr, _ = roc_curve(y_true, y_score)
    auc = float(roc_auc_score(y_true, y_score))
    return fpr, tpr, auc


def compute_auc_ci(y_true, y_score, n_bootstraps=1000, rng_seed=42):
    """
    Tính khoảng tin cậy 95% (95% CI) cho AUC sử dụng phương pháp Bootstrap phân tầng.
    """
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    
    mask = np.isfinite(y_true) & np.isfinite(y_score)
    y_true = y_true[mask]
    y_score = y_score[mask]
    
    unique_classes = np.unique(y_true)
    if len(unique_classes) < 2:
        return np.nan, np.nan
        
    pos_idx = np.where(y_true == 1)[0]
    neg_idx = np.where(y_true == 0)[0]
    
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        return np.nan, np.nan
        
    rng = np.random.default_rng(rng_seed)
    bootstrapped_aucs = []
    
    for _ in range(n_bootstraps):
        pos_sample = rng.choice(pos_idx, size=len(pos_idx), replace=True)
        neg_sample = rng.choice(neg_idx, size=len(neg_idx), replace=True)
        indices = np.concatenate([pos_sample, neg_sample])
        
        try:
            auc = roc_auc_score(y_true[indices], y_score[indices])
            bootstrapped_aucs.append(auc)
        except ValueError:
            continue
            
    if len(bootstrapped_aucs) == 0:
        return np.nan, np.nan
        
    sorted_aucs = np.sort(bootstrapped_aucs)
    ci_lower = float(np.percentile(sorted_aucs, 2.5))
    ci_upper = float(np.percentile(sorted_aucs, 97.5))
    
    return ci_lower, ci_upper


def evaluate_model_cv_with_oof(model, X_train, y_train, cv=10, positive_label=1):
    """
    Chạy Stratified CV một lần để lấy cả summary metrics và OOF positive scores.
    """
    y_train = np.asarray(y_train)
    cv_strategy = (
        StratifiedKFold(n_splits=cv, shuffle=True, random_state=42)
        if isinstance(cv, int)
        else cv
    )

    metric_values = {
        "AUC": [],
        "Accuracy": [],
        "Sensitivity": [],
        "Specificity": [],
        "PPV": [],
        "NPV": [],
        "F1-Score": [],
    }
    oof_scores = np.zeros(y_train.shape[0], dtype=float)

    for train_idx, val_idx in cv_strategy.split(X_train, y_train):
        if hasattr(X_train, "iloc"):
            X_fold_train = X_train.iloc[train_idx]
            X_fold_val = X_train.iloc[val_idx]
        else:
            X_fold_train = X_train[train_idx]
            X_fold_val = X_train[val_idx]

        y_fold_train = y_train[train_idx]
        y_fold_val = y_train[val_idx]

        try:
            estimator = clone(model)
            estimator.fit(X_fold_train, y_fold_train)

            y_pred = estimator.predict(X_fold_val)
            y_prob = _extract_positive_class_probability(estimator, X_fold_val, y_pred)
            y_prob = np.asarray(y_prob, dtype=float)

            if y_prob.ndim == 2:
                if y_prob.shape[1] == 1:
                    y_prob = y_prob[:, 0]
                else:
                    classes = getattr(estimator, "classes_", np.unique(y_train))
                    classes = np.asarray(classes)
                    positive_index = min(len(classes) - 1, y_prob.shape[1] - 1)
                    matches = np.where(classes == positive_label)[0]
                    if len(matches) > 0:
                        positive_index = int(matches[0])
                    y_prob = y_prob[:, positive_index]

            oof_scores[val_idx] = y_prob

            if len(np.unique(y_fold_val)) < 2:
                auc = np.nan
            else:
                auc = float(roc_auc_score(y_fold_val, y_prob))

            metric_values["AUC"].append(auc)
            metric_values["Accuracy"].append(float(accuracy_score(y_fold_val, y_pred)))
            metric_values["Sensitivity"].append(
                float(recall_score(y_fold_val, y_pred, zero_division=0))
            )
            metric_values["Specificity"].append(_specificity_score(y_fold_val, y_pred))
            metric_values["PPV"].append(_ppv_score(y_fold_val, y_pred))
            metric_values["NPV"].append(_npv_score(y_fold_val, y_pred))
            metric_values["F1-Score"].append(
                float(f1_score(y_fold_val, y_pred, zero_division=0))
            )
        except Exception as e:
            model_class_name = type(model).__name__
            print(f"[EVALUATE][WARNING] Lỗi khi chạy fold CV cho {model_class_name}: {e}")
            for k in metric_values.keys():
                metric_values[k].append(np.nan)
            oof_scores[val_idx] = 0.5

    def _mean_std(values):
        arr = np.asarray(values, dtype=float)
        if np.isnan(arr).all():
            return np.nan, np.nan
        return float(np.nanmean(arr)), float(np.nanstd(arr))

    cv_results = {metric: _mean_std(values) for metric, values in metric_values.items()}
    return cv_results, oof_scores


def evaluate_on_test(model, X_test, y_test):
    """
    Dự đoán thử nghiệm trên tập test độc lập. Trả về Metrics và tọa độ ROC (FPR, TPR).
    """
    y_pred = model.predict(X_test)
    y_prob = _extract_positive_class_probability(model, X_test, y_pred)

    unique_classes = np.unique(y_test)
    if len(unique_classes) < 2:
        auc = np.nan
        fpr = np.array([0.0, 1.0])
        tpr = np.array([0.0, 1.0])
        ci = (np.nan, np.nan)
    else:
        auc = roc_auc_score(y_test, y_prob)
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        ci = compute_auc_ci(y_test, y_prob)

    acc = accuracy_score(y_test, y_pred)
    sens = recall_score(y_test, y_pred, zero_division=0)

    tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
    spec = _safe_divide(tn, tn + fp)
    ppv = _safe_divide(tp, tp + fp)
    npv = _safe_divide(tn, tn + fn)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    return {
        "AUC": auc,
        "Accuracy": acc,
        "Sensitivity": sens,
        "Specificity": spec,
        "PPV": ppv,
        "NPV": npv,
        "F1-Score": f1,
        "roc": (fpr, tpr),
        "AUC_CI": ci,
    }
