import warnings
import numpy as np
import pandas as pd

def select_features_shap(X_train, y_train, X_test, n_features=15):
    """
    Train an XGBoost classifier, calculate mean absolute SHAP values on X_train,
    and select the top n_features.
    """
    import shap
    from xgboost import XGBClassifier

    print(f"[FEATURE][INFO] Training XGBoost model for SHAP calculations...")
    # Train XGBoost for SHAP calculation
    clf = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        random_state=42,
        eval_metric="logloss",
    )
    clf.fit(X_train, y_train)

    print(f"[FEATURE][INFO] Calculating SHAP values using TreeExplainer...")
    # Calculate SHAP values
    explainer = shap.TreeExplainer(clf)
    shap_values = explainer.shap_values(X_train)

    # Handle different output structures of shap_values
    if isinstance(shap_values, list):
        # shap_values[1] is the SHAP values for the positive class in binary classification
        shap_vals_arr = np.asarray(shap_values[1])
    elif hasattr(shap_values, "values"):
        # For Explanation object
        shap_vals_arr = np.asarray(shap_values.values)
    else:
        shap_vals_arr = np.asarray(shap_values)

    # If shape is (N, D, 2) in binary classification, take the second slice (positive class)
    if len(shap_vals_arr.shape) == 3 and shap_vals_arr.shape[2] == 2:
        shap_vals_arr = shap_vals_arr[:, :, 1]

    # Calculate mean absolute SHAP values
    mean_abs_shap = np.mean(np.abs(shap_vals_arr), axis=0)

    # Sort and select top n_features
    indices = np.argsort(mean_abs_shap)[::-1][:n_features]
    selected_features = X_train.columns[indices].tolist()

    X_train_selected = X_train[selected_features]
    X_test_selected = X_test[selected_features]

    # Store the SHAP scores in a dictionary (using key 'coefficients' to avoid breaking downstream table/plot logic)
    importance = {feature: float(score) for feature, score in zip(X_train.columns.tolist(), mean_abs_shap)}

    meta = {
        "coefficients": importance,
        "selected_features": selected_features,
        "n_features": n_features,
    }

    return X_train_selected, X_test_selected, selected_features, meta
