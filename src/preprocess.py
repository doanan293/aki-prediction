import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer


def preprocess_data(X_train, X_test, missing_threshold=0.2):
    """
    Drop columns by train-only missing ratio, then fit train-only KNN imputer
    and transform both train/test with those fitted artifacts.
    """
    # Drop severity scores to avoid information leakage
    # exclude_cols = ["sofa", "saps2", "oasis"]
    exclude_cols = []
    X_train = X_train.drop(columns=[col for col in exclude_cols if col in X_train.columns], errors="ignore")
    X_test = X_test.drop(columns=[col for col in exclude_cols if col in X_test.columns], errors="ignore")

    # 1. Drop columns using train missing ratio only
    missing_ratio = X_train.isnull().mean()
    cols_to_keep = missing_ratio[missing_ratio <= missing_threshold].index.tolist()

    if not cols_to_keep:
        raise ValueError("No columns remain after missing-threshold filtering")

    X_train_filtered = X_train[cols_to_keep].copy()
    X_test_filtered = X_test[cols_to_keep].copy()

    # Identify categorical columns to encode
    cat_cols = ["race", "dka_type", "liver_disease", "ckd_stage"]
    active_cat_cols = [col for col in cat_cols if col in X_train_filtered.columns]

    if active_cat_cols:
        X_train_encoded = pd.get_dummies(X_train_filtered, columns=active_cat_cols, drop_first=True, dtype=float)
        X_test_encoded = pd.get_dummies(X_test_filtered, columns=active_cat_cols, drop_first=True, dtype=float)

        encoded_cols = X_train_encoded.columns.tolist()
        X_test_encoded = X_test_encoded.reindex(columns=encoded_cols, fill_value=0.0)

        # Reset NaNs for the dummy columns on originally missing rows so that KNNImputer can impute them
        for col in active_cat_cols:
            orig_nan_train = X_train_filtered[col].isna()
            if orig_nan_train.any():
                dummy_cols = [c for c in X_train_encoded.columns if c.startswith(f"{col}_")]
                X_train_encoded.loc[orig_nan_train, dummy_cols] = np.nan

            orig_nan_test = X_test_filtered[col].isna()
            if orig_nan_test.any():
                dummy_cols = [c for c in X_test_encoded.columns if c.startswith(f"{col}_")]
                X_test_encoded.loc[orig_nan_test, dummy_cols] = np.nan
    else:
        X_train_encoded = X_train_filtered
        X_test_encoded = X_test_filtered
        encoded_cols = cols_to_keep

    # 2. Fit imputer on train (now containing only numeric columns), then transform train/test
    imputer = KNNImputer(n_neighbors=5)
    X_train_imputed = pd.DataFrame(imputer.fit_transform(X_train_encoded), columns=encoded_cols, index=X_train.index)
    X_test_imputed = pd.DataFrame(imputer.transform(X_test_encoded), columns=encoded_cols, index=X_test.index)

    artifacts = {
        "missing_ratio": missing_ratio,
        "imputer": imputer,
        "active_cat_cols": active_cat_cols,
    }

    return X_train_imputed, X_test_imputed, encoded_cols, artifacts
