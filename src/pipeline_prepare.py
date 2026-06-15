import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from src.data_loader import parse_and_flatten_raw
from src.preprocess import preprocess_data
from src.config import MODELS_DIR
from src.artifacts import save_preprocessor_bundle
from src.pipeline_evaluate import transform_with_bundle

def run_prepare(
    raw_train_path: Path,
    raw_test_path: Path,
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Parse and flatten raw train data (970 patients)
    df_train_full = parse_and_flatten_raw(str(raw_train_path), require_target=True)
    
    # In báo cáo phân tích dữ liệu thô
    from src.data_loader import analyze_raw_data
    analyze_raw_data(df_train_full)
    
    # 2. Perform stratified train/test split (85% train, 15% test/validation)
    df_train, df_test = train_test_split(
        df_train_full,
        test_size=0.15,
        stratify=df_train_full["akdPositive"],
        random_state=42
    )
    
    # Separate features and targets/IDs
    drop_cols = ["subjectId", "hadmId", "stayId", "akdPositive"]
    X_train = df_train.drop(columns=[col for col in drop_cols if col in df_train.columns], errors="ignore")
    X_test = df_test.drop(columns=[col for col in drop_cols if col in df_test.columns], errors="ignore")
    
    # Run dynamic preprocessing (dropping excluded cols, >20% missing, fitting KNN + Scaler)
    X_train_prep, X_test_prep, kept_cols, prep_artifacts = preprocess_data(
        X_train,
        X_test,
        missing_threshold=0.2,
    )
    
    # Save preprocessor bundle (sel_features will be filled during training)
    preprocessor_path = MODELS_DIR / "preprocessor.joblib"
    save_preprocessor_bundle(
        out_path=preprocessor_path,
        prep_artifacts=prep_artifacts,
        kept_cols=kept_cols,
        sel_features=[],
        target_name="akdPositive",
    )
    
    # Recombine features with targets and IDs
    df_train_prep = pd.concat([df_train[drop_cols], X_train_prep], axis=1)
    df_test_prep = pd.concat([df_test[drop_cols], X_test_prep], axis=1)
    
    train_out = output_dir / "train.csv"
    df_train_prep.to_csv(train_out, index=False)

    test_out = output_dir / "test.csv"
    df_test_prep.to_csv(test_out, index=False)

    # 3. Parse and flatten the original raw test data (unlabeled) for inference
    df_unlabeled = parse_and_flatten_raw(str(raw_test_path), require_target=False)
    
    drop_cols_unlabeled = ["subjectId", "hadmId", "stayId"]
    X_unlabeled = df_unlabeled.drop(columns=[col for col in drop_cols_unlabeled if col in df_unlabeled.columns], errors="ignore")
    
    bundle = {
        "kept_cols": kept_cols,
        "sel_features": kept_cols,
        "prep_artifacts": prep_artifacts,
    }
    X_unlabeled_prep = transform_with_bundle(X_unlabeled, bundle)
    
    df_unlabeled_prep = pd.concat([df_unlabeled[drop_cols_unlabeled], X_unlabeled_prep], axis=1)
    unlabeled_out = output_dir / "unlabeled_test.csv"
    df_unlabeled_prep.to_csv(unlabeled_out, index=False)

    return {
        "train_csv_path": str(train_out),
        "test_csv_path": str(test_out),
        "unlabeled_test_csv_path": str(unlabeled_out),
    }

