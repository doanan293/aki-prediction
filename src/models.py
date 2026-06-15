import inspect
import os
from pathlib import Path

from sklearn.ensemble import AdaBoostClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB, GaussianNB
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier
from sklearn.base import BaseEstimator, ClassifierMixin

_TABPFN_MODEL_PATH_ENV = "TABPFN_MODEL_PATH"


def _project_root():
    return Path(__file__).resolve().parent.parent


def _resolve_tabpfn_model_path(model_path):
    configured_path = os.environ.get(_TABPFN_MODEL_PATH_ENV)
    path = Path(configured_path or model_path)
    if configured_path and not path.is_absolute():
        path = _project_root() / path

    if path.exists():
        return path

    basename = path.name
    candidates = [
        Path("resource") / "tabpfn-pretrain" / basename,
        _project_root() / "resource" / "tabpfn-pretrain" / basename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return path


def _validate_tabpfn_checkpoint(model_path):
    path = Path(model_path)
    if not path.exists() or not path.is_file():
        return

    with path.open("rb") as fh:
        header = fh.read(64)

    if header.startswith(b"version https://git-lfs.github.com/spec/"):
        raise ValueError(
            "TabPFN checkpoint is a Git LFS pointer, not the real model file: "
            f"{path}. Run "
            "`git lfs pull --include=resource/tabpfn-pretrain/tabpfn-v3-classifier-v3_20260417_binary.ckpt` "
            "before training."
        )

class TabPFNWrapper(ClassifierMixin, BaseEstimator):
    def __init__(
        self,
        random_state=42,
        model_path="/home/andv/personal/hm-kpdl/final/resource/tabpfn-pretrain/tabpfn-v3-classifier-v3_20260417_binary.ckpt",
        device="cpu",
    ):
        self.random_state = random_state
        self.model_path = model_path
        self.device = device

    def fit(self, X, y):
        import pandas as pd
        import numpy as np

        _validate_tabpfn_checkpoint(_resolve_tabpfn_model_path(self.model_path))

        self.classes_ = np.unique(y)
        if isinstance(X, pd.DataFrame):
            self.X_train_ = X.copy()
        else:
            self.X_train_ = np.array(X)
            
        if isinstance(y, pd.Series):
            self.y_train_ = y.copy()
        else:
            self.y_train_ = np.array(y)
            
        return self

    def _init_local_classifier(self):
        from tabpfn import TabPFNClassifier
        
        path = _resolve_tabpfn_model_path(self.model_path)
        _validate_tabpfn_checkpoint(path)

        return TabPFNClassifier(
            model_path=str(path),
            device=self.device,
        )

    def predict_proba(self, X):
        clf = self._init_local_classifier()
        clf.fit(self.X_train_, self.y_train_)
        return clf.predict_proba(X)

    def predict(self, X):
        clf = self._init_local_classifier()
        clf.fit(self.X_train_, self.y_train_)
        return clf.predict(X)




_ALLOWED_TUNED_PARAMS = {
    "XGBoost": frozenset(
        {
            "n_estimators",
            "max_depth",
            "learning_rate",
            "subsample",
            "colsample_bytree",
            "scale_pos_weight",
            "tree_method",
            "reg_alpha",
            "reg_lambda",
            "min_child_weight",
            "gamma",
        }
    ),
    "Logistic Regression": frozenset({"C", "class_weight"}),
    "LightGBM": frozenset(
        {
            "n_estimators",
            "num_leaves",
            "learning_rate",
            "subsample",
            "colsample_bytree",
        }
    ),
    "AdaBoost": frozenset(
        {
            "n_estimators",
            "learning_rate",
            "estimator_max_depth",
        }
    ),
    "GNB": frozenset({"var_smoothing"}),
    "CNB": frozenset({"alpha"}),
    "MLP": frozenset(
        {
            "hidden_layer_sizes",
            "alpha",
            "learning_rate_init",
        }
    ),
    "SVM": frozenset({"C", "gamma", "kernel", "class_weight"}),
    "TabPFN-3-Plus": frozenset(),
}


def get_models(tuned_params=None):
    """
    Return the fixed 9-model registry used by the pipeline.
    """
    tuned_params = _validate_tuned_params(tuned_params)
    models = {
        "XGBoost": XGBClassifier(
            eval_metric="logloss",
            random_state=42,
            **tuned_params.get("XGBoost", {}),
        ),
        "Logistic Regression": LogisticRegression(
            max_iter=1000,
            random_state=42,
            **tuned_params.get("Logistic Regression", {}),
        ),
        "LightGBM": _build_lightgbm_model(tuned_params.get("LightGBM", {})),
        "AdaBoost": _build_adaboost_model(tuned_params.get("AdaBoost", {})),
        "GNB": GaussianNB(**tuned_params.get("GNB", {})),
        "CNB": ComplementNB(**tuned_params.get("CNB", {})),
        "MLP": MLPClassifier(
            max_iter=1000,
            random_state=42,
            **tuned_params.get("MLP", {}),
        ),
        "SVM": SVC(
            probability=True,
            random_state=42,
            max_iter=10000,
            **tuned_params.get("SVM", {}),
        ),
        "TabPFN-3-Plus": TabPFNWrapper(random_state=42, **tuned_params.get("TabPFN-3-Plus", {})),
    }
    return models



def _validate_tuned_params(tuned_params):
    if tuned_params is None:
        return {}
    if not isinstance(tuned_params, dict):
        raise ValueError("tuned_params must be a dictionary")
    validated = {}
    for model_name, params in tuned_params.items():
        if model_name not in _ALLOWED_TUNED_PARAMS:
            raise ValueError(f"Unknown tuned model: {model_name}")
        if not isinstance(params, dict):
            raise ValueError(f"Tuned params for {model_name} must be a dictionary")
        allowed = _ALLOWED_TUNED_PARAMS[model_name]
        unknown = sorted(set(params) - allowed)
        if unknown:
            raise ValueError(
                f"Unsupported tuned parameter(s) for {model_name}: {unknown}"
            )
        validated[model_name] = dict(params)
    return validated


def _build_lightgbm_model(params=None):
    try:
        from lightgbm import LGBMClassifier
    except (ImportError, OSError) as exc:
        raise ImportError(
            "LightGBM is required for the strict model registry. "
            "Install lightgbm to use get_models()."
        ) from exc

    return LGBMClassifier(random_state=42, verbose=-1, **(params or {}))


def _build_adaboost_model(params=None):
    model_params = dict(params or {})
    estimator_params = _extract_adaboost_estimator_params(model_params)
    if estimator_params:
        tree = DecisionTreeClassifier(random_state=42, **estimator_params)
        if "estimator" in inspect.signature(AdaBoostClassifier).parameters:
            model_params["estimator"] = tree
        else:
            model_params["base_estimator"] = tree
    if "algorithm" in inspect.signature(AdaBoostClassifier).parameters:
        model_params.setdefault("algorithm", "SAMME")
    return AdaBoostClassifier(random_state=42, **model_params)


def _extract_adaboost_estimator_params(model_params):
    mapping = {
        "estimator_criterion": "criterion",
        "estimator_max_depth": "max_depth",
        "estimator_min_samples_split": "min_samples_split",
        "estimator_min_samples_leaf": "min_samples_leaf",
        "estimator_max_features": "max_features",
        "estimator_min_impurity_decrease": "min_impurity_decrease",
        "estimator_ccp_alpha": "ccp_alpha",
    }
    estimator_params = {}
    for public_key, estimator_key in mapping.items():
        if public_key in model_params:
            estimator_params[estimator_key] = model_params.pop(public_key)
    return estimator_params
