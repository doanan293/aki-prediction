import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import brier_score_loss

# Ánh xạ tên biến sang định dạng nhãn đẹp trong bài báo
FEATURE_LABEL_MAP = {
    "bun": "BUN",
    "urine_output": "Urine output",
    "weight": "Weight admit",
    "age": "Age",
    "plt": "PLT",
    "infusion_volume": "Infusion volume",
    "bg": "BG",
}


def _map_feature_name(name):
    name_lower = str(name).lower().strip()
    return FEATURE_LABEL_MAP.get(name_lower, name)


def _map_model_name(name):
    if str(name).strip().lower() == "logistic regression":
        return "Logistic"
    return name


def plot_roc_split(roc_data, title, output_path="images/roc_comparison.png"):
    """
    Vẽ đường biểu diễn ROC đa đường cho các model trên tập kiểm thử,
    với định dạng và nhãn trục chuẩn xác theo bài báo.
    """
    plt.figure(figsize=(10, 8))

    # Sắp xếp các mô hình theo AUC giảm dần để hiển thị chú thích (legend) ngăn nắp
    sorted_roc_data = sorted(roc_data.items(), key=lambda x: x[1][2], reverse=True)

    for model_name, val in sorted_roc_data:
        mapped_name = _map_model_name(model_name)
        if len(val) == 4:
            fpr, tpr, auc, ci = val
        else:
            fpr, tpr, auc = val
            ci = None

        if ci is not None and not np.isnan(ci[0]) and not np.isnan(ci[1]):
            label = f"{mapped_name} (AUC = {auc:.3f} 95%CI ({ci[0]:.3f}-{ci[1]:.3f}))"
        else:
            label = f"{mapped_name} (AUC = {auc:.3f})"
        plt.plot(fpr, tpr, label=label, linewidth=2)

    # Đường chéo nét đứt màu đỏ đất mờ theo bài báo
    plt.plot([0, 1], [0, 1], color="#C0392B", linestyle="--", alpha=0.7, linewidth=1.5)

    plt.xlabel("Specificity", fontsize=14, fontweight="bold")
    plt.ylabel("Sensitivity", fontsize=14, fontweight="bold")
    plt.title(title, fontsize=16, fontweight="bold", pad=15)
    plt.legend(loc="lower right", fontsize=11, frameon=True, facecolor="white", edgecolor="lightgray")

    # Kích hoạt lưới tọa độ nét đứt mờ nhạt
    plt.grid(color="lightgray", linestyle="-.", alpha=0.6)

    # Định dạng viền
    ax = plt.gca()
    ax.tick_params(labelsize=12)
    for spine in ax.spines.values():
        spine.set_linewidth(1.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_xgb_feature_importance(model, feature_names, output_path="images/feature_importance.png"):
    """
    Vẽ biểu đồ Feature Importance của XGBoost không có tiêu đề,
    có nhãn variables và màu sắc giống 100% bài báo.
    """
    if not hasattr(model, "feature_importances_"):
        raise ValueError("Model does not expose feature_importances_.")

    importances = model.feature_importances_
    indices = np.argsort(importances)

    mapped_features = [_map_feature_name(feature_names[i]) for i in indices]

    plt.figure(figsize=(10, 6))

    # Sử dụng màu đỏ cam/san hô giống hệt feature_importance.png
    plt.barh(range(len(indices)), importances[indices], align="center", color="#E54B3B", height=0.7)

    plt.yticks(range(len(indices)), mapped_features, fontsize=12)
    plt.xlabel("Feature importance", fontsize=14, fontweight="bold")
    plt.ylabel("Variables", fontsize=14, fontweight="bold")

    # Loại bỏ viền bên trên và bên phải
    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.tick_params(labelsize=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_shap_importance(shap_map, output_path="images/shap_importance.png"):
    """
    Vẽ biểu đồ tầm quan trọng đặc trưng dựa trên giá trị SHAP trung bình tuyệt đối.
    """
    items = list(shap_map.items())
    if not items:
        raise ValueError("shap_map must not be empty.")

    features = [item[0] for item in items]
    importance = np.array([item[1] for item in items], dtype=float)
    indices = np.argsort(importance)

    mapped_features = [_map_feature_name(features[i]) for i in indices]

    plt.figure(figsize=(10, 6))

    # Sử dụng màu đỏ gạch đất đồng nhất
    plt.barh(range(len(indices)), importance[indices], align="center", color="#B83A26", height=0.5)

    plt.yticks(range(len(indices)), mapped_features, fontsize=12)
    plt.xlabel("Mean Absolute SHAP Value (Average Impact on Model Output)", fontsize=12, fontweight="bold")
    plt.title("Feature Importance based on Mean SHAP Values", fontsize=16, fontweight="bold", pad=15)

    # Loại bỏ viền bên trên và bên phải
    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.tick_params(labelsize=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_xgb_feature_importance_scores(importance_map, output_path="images/xgb-feature-importance-coef.png"):
    """
    Vẽ biểu đồ Feature Importance của XGBoost từ mapping feature -> importance.
    """
    items = list(importance_map.items())
    if not items:
        raise ValueError("importance_map must not be empty.")

    features = [item[0] for item in items]
    importances = np.array([item[1] for item in items], dtype=float)
    indices = np.argsort(importances)

    mapped_features = [_map_feature_name(features[i]) for i in indices]

    plt.figure(figsize=(10, 6))
    plt.barh(range(len(indices)), importances[indices], align="center", color="#E54B3B", height=0.7)

    plt.yticks(range(len(indices)), mapped_features, fontsize=12)
    plt.xlabel("Feature importance", fontsize=14, fontweight="bold")
    plt.ylabel("Variables", fontsize=14, fontweight="bold")

    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.tick_params(labelsize=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def _validate_y_true_y_prob(y_true, y_prob):
    y_true_arr = np.asarray(y_true).ravel()
    y_prob_arr = np.asarray(y_prob).ravel().astype(float)

    if y_true_arr.size == 0 or y_prob_arr.size == 0:
        raise ValueError("y_true and y_prob must not be empty.")
    if y_true_arr.shape[0] != y_prob_arr.shape[0]:
        raise ValueError("y_true and y_prob must have the same length.")

    try:
        y_true_numeric = y_true_arr.astype(float)
    except (TypeError, ValueError) as exc:
        raise ValueError("y_true and y_prob must contain finite numeric values.") from exc

    if not np.all(np.isfinite(y_true_numeric)) or not np.all(np.isfinite(y_prob_arr)):
        raise ValueError("y_true and y_prob must contain finite numeric values.")
    if not np.all((y_true_numeric == 0.0) | (y_true_numeric == 1.0)):
        raise ValueError("y_true must be binary (0/1).")
    if not np.all((y_prob_arr >= 0.0) & (y_prob_arr <= 1.0)):
        raise ValueError("y_prob values must be between 0 and 1.")

    return y_true_numeric.astype(int), y_prob_arr


def _hide_nonbeneficial_tail(net_benefit):
    display_values = np.asarray(net_benefit, dtype=float).copy()
    nonbeneficial = np.where(display_values <= 0.0)[0]
    if nonbeneficial.size > 0:
        display_values[int(nonbeneficial[0]) :] = np.nan
    return display_values


def plot_xgb_decision_curve(y_true, y_prob, output_path, model_label="XGBoost"):
    """
    Vẽ biểu đồ Decision Curve (Đường cong quyết định) đơn lẻ chuẩn xác theo bài báo.
    """
    y_true_arr, y_prob_arr = _validate_y_true_y_prob(y_true, y_prob)

    thresholds = np.linspace(0.01, 0.99, 99)
    n_samples = y_true_arr.shape[0]

    y_true_positive = y_true_arr[:, None] == 1
    predicted_positive = y_prob_arr[:, None] >= thresholds[None, :]

    tp = np.sum(predicted_positive & y_true_positive, axis=0)
    fp = np.sum(predicted_positive & ~y_true_positive, axis=0)

    net_benefit_model = (tp / n_samples) - (fp / n_samples) * (thresholds / (1.0 - thresholds))
    net_benefit_model_display = _hide_nonbeneficial_tail(net_benefit_model)
    prevalence = np.mean(y_true_arr)
    net_benefit_all = prevalence - (1.0 - prevalence) * (thresholds / (1.0 - thresholds))
    net_benefit_none = np.zeros_like(thresholds)

    plt.figure(figsize=(8, 8))

    # Chuyển đổi sang tỷ lệ phần trăm (0 - 100%) giống hệt bài báo
    plt.plot(thresholds * 100, net_benefit_model_display, label=f"{model_label}", color="#B03A2E", linewidth=2)
    plt.plot(thresholds * 100, net_benefit_all, label="Treat All", color="black", linestyle="--", linewidth=1.5)
    plt.plot(thresholds * 100, net_benefit_none, label="Treat None", color="#C53030", linestyle=":", linewidth=2)

    plt.title("Test Decision Curve", fontsize=14, fontweight="bold", pad=10)
    plt.xlabel("Threshold Probability(%)", fontsize=12, fontweight="bold")
    plt.ylabel("Mean Net Benefit", fontsize=12, fontweight="bold")
    plt.xlim(0, 100)
    plt.ylim(-0.05, 0.45)
    plt.legend(loc="upper right", fontsize=11, frameon=True)

    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.tick_params(labelsize=11)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_xgb_calibration_curve(y_true, y_prob, output_path, model_label="XGBoost"):
    """
    Vẽ biểu đồ Calibration Curve (Biểu đồ hiệu chuẩn) đơn lẻ chuẩn xác theo bài báo.
    """
    y_true_arr, y_prob_arr = _validate_y_true_y_prob(y_true, y_prob)

    bin_edges = np.linspace(0.0, 1.0, 11)
    bin_ids = np.digitize(y_prob_arr, bin_edges[1:-1], right=True)

    mean_predicted = []
    observed_frequency = []
    for idx in range(10):
        in_bin = bin_ids == idx
        if np.any(in_bin):
            mean_predicted.append(float(np.mean(y_prob_arr[in_bin])))
            observed_frequency.append(float(np.mean(y_true_arr[in_bin])))

    plt.figure(figsize=(8, 8))
    brier = brier_score_loss(y_true_arr, y_prob_arr)

    plt.plot([0, 1], [0, 1], color="black", linestyle=":", label="Perfect Calibration", linewidth=1.5)
    plt.plot(
        mean_predicted,
        observed_frequency,
        marker="o",
        color="#B03A2E",
        label=f"{model_label} ({brier:.3f})",
        linewidth=2,
        clip_on=False,
    )

    plt.title("Calibration plots  (reliability curve)", fontsize=14, fontweight="bold", pad=10)
    plt.xlabel("Mean predicted value", fontsize=12, fontweight="bold")
    plt.ylabel("Fraction of positives", fontsize=12, fontweight="bold")
    plt.xlim(0.0, 1.0)
    plt.ylim(0.0, 1.0)
    plt.legend(loc="lower right", fontsize=11, frameon=True)

    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.tick_params(labelsize=11)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_tabpfn_feature_importance(importance_map, output_path="images/tabpfn-feature-importance.png"):
    """
    Vẽ biểu đồ Permutation Feature Importance của TabPFN.
    """
    items = list(importance_map.items())
    if not items:
        raise ValueError("importance_map must not be empty.")

    features = [item[0] for item in items]
    importances = np.array([item[1] for item in items], dtype=float)
    indices = np.argsort(importances)

    mapped_features = [_map_feature_name(features[i]) for i in indices]

    plt.figure(figsize=(10, 6))
    # Sử dụng màu xanh dương/navy thanh lịch cho TabPFN
    plt.barh(range(len(indices)), importances[indices], align="center", color="#1F77B4", height=0.7)

    plt.yticks(range(len(indices)), mapped_features, fontsize=12)
    plt.xlabel("Permutation Importance (Mean AUC Drop)", fontsize=14, fontweight="bold")
    plt.ylabel("Variables", fontsize=14, fontweight="bold")

    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.tick_params(labelsize=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
