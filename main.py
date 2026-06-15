import argparse
import importlib
import sys
from pathlib import Path

from src.config import (
    IMAGES_DIR,
    TABLES_DIR,
    MODELS_DIR,
    PREDICTIONS_OUTPUT_PATH,
    TEST_DATA_PATH,
    TRAIN_DATA_PATH,
    RAW_TRAIN_DATA_PATH,
    RAW_TEST_DATA_PATH,
)


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be a non-negative integer")
    return parsed


def run_prepare_command(args):
    run_prepare = importlib.import_module("src.pipeline_prepare").run_prepare

    return run_prepare(
        raw_train_path=Path(args.raw_train_path),
        raw_test_path=Path(args.raw_test_path),
        output_dir=Path(args.output_dir),
    )


def run_train_command(args):
    run_train = importlib.import_module("src.pipeline_train").run_train

    return run_train(
        train_path=Path(args.train_path),
        test_path=Path(args.test_path),
        models_dir=Path(args.models_dir),
        select_best_by=args.select_best_by,
        tables_dir=Path(args.tables_dir) if args.tables_dir else None,
    )


def run_tune_command(args):
    run_tuning = importlib.import_module("src.hyperparameter_tuning").run_tuning

    model_budget = None
    overrides = {
        "XGBoost": args.trials_xgboost,
        "LightGBM": args.trials_lightgbm,
        "SVM": args.trials_svm,
        "Logistic Regression": args.trials_logistic,
        "AdaBoost": args.trials_adaboost,
        "GNB": args.trials_gnb,
        "CNB": args.trials_cnb,
        "MLP": args.trials_mlp,
    }
    if any(value is not None for value in overrides.values()):
        from src.hyperparameter_tuning import build_budget

        model_budget = build_budget(args.budget)
        for model_name, value in overrides.items():
            if value is not None:
                model_budget[model_name] = value

    return run_tuning(
        train_path=Path(args.train_path),
        test_path=Path(args.test_path),
        models_dir=Path(args.models_dir),
        budget_name=args.budget,
        model_budget=model_budget,
    )


def run_select_features_command(args):
    run_select_features = importlib.import_module("src.pipeline_select_features").run_select_features

    return run_select_features(
        train_path=Path(args.train_path),
        test_path=Path(args.test_path),
        models_dir=Path(args.models_dir),
        tables_dir=Path(args.tables_dir) if args.tables_dir else None,
        images_dir=Path(args.images_dir) if args.images_dir else None,
    )


def run_evaluate_command(args):
    run_evaluate = importlib.import_module("src.pipeline_evaluate").run_evaluate

    return run_evaluate(
        input_path=Path(args.input_path),
        models_dir=Path(args.models_dir),
        model_name=args.model_name,
        images_dir=Path(args.images_dir),
        tables_dir=Path(args.tables_dir) if args.tables_dir else None,
    )


def run_predict_command(args):
    run_predict = importlib.import_module("src.pipeline_predict").run_predict

    return run_predict(
        input_path=Path(args.input_path),
        models_dir=Path(args.models_dir),
        model_name=args.model_name,
        output_path=Path(args.output_path),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py")
    sub = parser.add_subparsers(dest="command")

    p_train = sub.add_parser("train")
    p_train.add_argument("--train-path", default=str(TRAIN_DATA_PATH))
    p_train.add_argument("--test-path", default=str(TEST_DATA_PATH))
    p_train.add_argument("--models-dir", default=str(MODELS_DIR))
    p_train.add_argument("--select-best-by", default="auc")
    p_train.add_argument("--tables-dir", default=str(TABLES_DIR))

    p_select = sub.add_parser("select-features")
    p_select.add_argument("--train-path", default=str(TRAIN_DATA_PATH))
    p_select.add_argument("--test-path", default=str(TEST_DATA_PATH))
    p_select.add_argument("--models-dir", default=str(MODELS_DIR))
    p_select.add_argument("--tables-dir", default=str(TABLES_DIR))
    p_select.add_argument("--images-dir", default=str(IMAGES_DIR))

    p_tune = sub.add_parser("tune")
    p_tune.add_argument("--train-path", default=str(TRAIN_DATA_PATH))
    p_tune.add_argument("--test-path", default=str(TEST_DATA_PATH))
    p_tune.add_argument("--models-dir", default=str(MODELS_DIR))
    p_tune.add_argument("--budget", default="deep", choices=["quick", "deep"])
    p_tune.add_argument("--trials-xgboost", type=_non_negative_int, default=None)
    p_tune.add_argument("--trials-lightgbm", type=_non_negative_int, default=None)
    p_tune.add_argument("--trials-svm", type=_non_negative_int, default=None)
    p_tune.add_argument("--trials-logistic", type=_non_negative_int, default=None)
    p_tune.add_argument("--trials-adaboost", type=_non_negative_int, default=None)
    p_tune.add_argument("--trials-gnb", type=_non_negative_int, default=None)
    p_tune.add_argument("--trials-cnb", type=_non_negative_int, default=None)
    p_tune.add_argument("--trials-mlp", type=_non_negative_int, default=None)

    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--input-path", default=str(TEST_DATA_PATH))
    p_eval.add_argument("--models-dir", default=str(MODELS_DIR))
    p_eval.add_argument("--model-name", default=None)
    p_eval.add_argument("--images-dir", default=str(IMAGES_DIR))
    p_eval.add_argument("--tables-dir", default=str(TABLES_DIR))

    p_predict = sub.add_parser("predict")
    p_predict.add_argument("--input-path", default=str(RAW_TEST_DATA_PATH))
    p_predict.add_argument("--models-dir", default=str(MODELS_DIR))
    p_predict.add_argument("--model-name", default=None)
    p_predict.add_argument("--output-path", default=str(PREDICTIONS_OUTPUT_PATH))

    p_prep = sub.add_parser("prepare-data")
    p_prep.add_argument("--raw-train-path", default=str(RAW_TRAIN_DATA_PATH))
    p_prep.add_argument("--raw-test-path", default=str(RAW_TEST_DATA_PATH))
    p_prep.add_argument("--output-dir", default=str(Path(TRAIN_DATA_PATH).parent))

    return parser


def cli(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare-data":
        run_prepare_command(args)
        return 0
    if args.command == "select-features":
        run_select_features_command(args)
        return 0
    if args.command == "tune":
        run_tune_command(args)
        return 0
    if args.command == "train":
        run_train_command(args)
        return 0
    if args.command == "evaluate":
        run_evaluate_command(args)
        return 0
    if args.command == "predict":
        run_predict_command(args)
        return 0

    parser.print_help()
    print(
        "Migration note: run one of these commands: "
        "main.py prepare-data | main.py select-features | main.py tune | main.py train | main.py evaluate | main.py predict",
        file=sys.stderr,
    )
    return 2


def main(argv=None) -> int:
    return cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())

