import json

import numpy as np
import pandas as pd


def extract_first_value(ts_dict):
    """
    Extracts the value corresponding to the earliest timestamp/key in a dictionary.
    Assumes keys are ISO-8601 strings which sort chronologically.
    """
    if not ts_dict:
        return np.nan
    sorted_keys = sorted(ts_dict.keys())
    return ts_dict[sorted_keys[0]]


def _map_boolean(value):
    if isinstance(value, bool):
        return int(value)
    return value


def _normalize_target(value):
    if isinstance(value, (bool, np.bool_)):
        return int(value)

    if isinstance(value, (int, float, np.integer, np.floating)):
        if float(value) in (0.0, 1.0):
            return int(value)

    raise ValueError(
        "akdPositive must be a boolean or numeric 0/1; "
        f"got {value!r} ({type(value).__name__})"
    )


def _map_gender(value):
    mapping = {"M": 1, "F": 0}
    if value in mapping:
        return mapping[value]
    raise ValueError(f"Unknown gender value: {value}")


def _map_liver_disease(value):
    mapping = {"NONE": 0, "MILD": 1, "SEVERE": 2}
    if value in mapping:
        return mapping[value]
    raise ValueError(f"Unknown liver_disease value: {value}")


def _map_race(value):
    mapping = {
        "WHITE": 0,
        "BLACK/AFRICAN AMERICAN": 1,
        "UNKNOWN": 2,
        "OTHER": 3,
        "HISPANIC OR LATINO": 4,
        "ASIAN": 5,
        "ASIAN - CHINESE": 6,
        "ASIAN - SOUTH EAST ASIAN": 7,
        "BLACK/AFRICAN": 8,
        "BLACK/CARIBBEAN ISLAND": 9,
        "BLACK/CAPE VERDEAN": 10,
        "HISPANIC/LATINO - PUERTO RICAN": 11,
        "HISPANIC/LATINO - DOMINICAN": 12,
        "HISPANIC/LATINO - GUATEMALAN": 13,
        "HISPANIC/LATINO - MEXICAN": 14,
        "HISPANIC/LATINO - SALVADORAN": 15,
        "HISPANIC/LATINO - CUBAN": 16,
        "WHITE - OTHER EUROPEAN": 17,
        "WHITE - RUSSIAN": 18,
        "WHITE - BRAZILIAN": 19,
        "WHITE - EASTERN EUROPEAN": 20,
        "UNABLE TO OBTAIN": 21,
        "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER": 22,
        "MULTIPLE RACE/ETHNICITY": 23,
        "PORTUGUESE": 24,
        "AMERICAN INDIAN/ALASKA NATIVE": 25,
    }
    if value in mapping:
        return mapping[value]
    raise ValueError(f"Unknown race value: {value}")


def _normalize_value(key, value):
    if isinstance(value, dict):
        value = extract_first_value(value)

    value = _map_boolean(value)

    if key == "gender" and not pd.isna(value):
        return _map_gender(value)
    if key == "liver_disease" and not pd.isna(value):
        return _map_liver_disease(value)
    if key == "race" and not pd.isna(value):
        return _map_race(value)

    return value


def parse_and_flatten_raw(filepath: str, require_target: bool = True) -> pd.DataFrame:
    """
    Load JSON data and flatten per-patient rows with strict contracts.
    """
    with open(filepath) as f:
        data = json.load(f)

    rows = []
    for idx, patient in enumerate(data):
        row = {}
        # IDs and structural properties
        row["subjectId"] = patient.get("subjectId")
        row["hadmId"] = patient.get("hadmId")
        row["stayId"] = patient.get("stayId")

        # Target Label
        if require_target and "akdPositive" not in patient:
            raise ValueError(
                f"Missing required target akdPositive at index={idx}, "
                f"subjectId={patient.get('subjectId')}"
            )

        if "akdPositive" in patient:
            row["akdPositive"] = _normalize_target(patient.get("akdPositive"))
        else:
            row["akdPositive"] = np.nan

        # Nested features
        measures = patient.get("measures", {})
        for key, value in measures.items():
            row[key] = _normalize_value(key, value)

        rows.append(row)

    return pd.DataFrame(rows)


def load_and_flatten_data(filepath: str, require_target: bool = True):
    """
    Load JSON data and flatten per-patient rows, returning X, y, meta.
    """
    df = parse_and_flatten_raw(filepath, require_target=require_target)

    # Separate Target
    y = df["akdPositive"]

    # Remove Target and IDs from X
    drop_cols = ["subjectId", "hadmId", "stayId", "akdPositive"]
    X = df.drop(columns=[col for col in drop_cols if col in df.columns])

    meta = {
        "n_rows": X.shape[0],
        "n_features": X.shape[1],
        "n_missing_values": int(X.isna().sum().sum()),
    }

    return X, y, meta


def load_flat_csv(filepath: str, require_target: bool = True):
    """
    Load flat CSV data and separate into X, y, meta.
    """
    df = pd.read_csv(filepath)

    # Target Label
    if require_target and "akdPositive" not in df.columns:
        raise ValueError(
            f"Missing required target akdPositive in flat CSV {filepath}"
        )

    if "akdPositive" in df.columns:
        y = df["akdPositive"]
    else:
        y = pd.Series(np.nan, index=df.index, name="akdPositive")

    # Remove Target and IDs from X
    drop_cols = ["subjectId", "hadmId", "stayId", "akdPositive"]
    X = df.drop(columns=[col for col in drop_cols if col in df.columns])

    meta = {
        "n_rows": X.shape[0],
        "n_features": X.shape[1],
        "n_missing_values": int(X.isna().sum().sum()),
    }

    return X, y, meta


def analyze_raw_data(df: pd.DataFrame, target_col: str = "akdPositive") -> None:
    """
    Phân tích và hiển thị thông tin thống kê của dữ liệu thô (đã được làm phẳng).
    """
    # Loại bỏ các cột ID và Target để lấy các đặc trưng
    drop_cols = ["subjectId", "hadmId", "stayId", target_col]
    X = df.drop(columns=[col for col in drop_cols if col in df.columns], errors="ignore")
    
    n_rows = X.shape[0]
    n_features = X.shape[1]
    n_missing_values = int(X.isna().sum().sum())
    
    print("\n--- DỮ LIỆU THÔ (SAU KHI LÀM PHẲNG) ---")
    print(f"Số lượng bệnh nhân: {n_rows}")
    print(f"Số lượng đặc trưng ban đầu: {n_features}")
    print(f"Tổng số giá trị khuyết thiếu (NaN): {n_missing_values}")

    missing_pct = X.isna().mean()
    print("\nTỷ lệ khuyết thiếu của từng cột (%):")
    for col, pct in missing_pct.sort_values(ascending=False).items():
        print(f"- {col}: {pct * 100:.2f}%")
    print("----------------------------------------\n")
