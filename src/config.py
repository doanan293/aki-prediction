import os
from pathlib import Path

# Vô hiệu hóa telemetry của TabPFN để tránh tiến trình bị treo khi kết xuất/tắt (analytics-python queue hangs)
os.environ["TABPFN_DISABLE_TELEMETRY"] = "1"


def _find_project_root() -> Path:
    """Walk up from this file's location to find the project root directory.
    Uses pyproject.toml as the sentinel file.
    """
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent  # Fallback to parent directory of src


ROOT_DIR = _find_project_root()


def load_dotenv(dotenv_path: Path) -> None:
    """Loads a .env file into os.environ if it exists."""
    if dotenv_path.is_file():
        with open(dotenv_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Bỏ qua dòng trống hoặc comment
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    # setdefault không ghi đè lên biến môi trường đã tồn tại sẵn
                    os.environ.setdefault(key, val)


# Tải cấu hình từ tệp .env ở thư mục gốc nếu có
load_dotenv(ROOT_DIR / ".env")


def _resolve_path(env_key: str) -> Path:
    """Lấy đường dẫn từ biến môi trường.
    Nếu đường dẫn không tồn tại trong os.environ, ném ra ngoại lệ KeyError.
    Nếu đường dẫn nhận được là tương đối, tự động giải nghĩa tuyệt đối so với ROOT_DIR.
    """
    raw_path = os.environ.get(env_key)
    if not raw_path:
        raise KeyError(
            f"Biến môi trường bắt buộc '{env_key}' không được thiết lập trong .env hoặc môi trường chạy hệ thống."
        )

    path = Path(raw_path)
    # Giải nghĩa tuyệt đối nếu là đường dẫn tương đối
    if not path.is_absolute():
        path = (ROOT_DIR / path).resolve()
    return path


# Định nghĩa các hằng số cấu hình đường dẫn bắt buộc cho dự án
TRAIN_DATA_PATH = _resolve_path("TRAIN_DATA_PATH")
TEST_DATA_PATH = _resolve_path("TEST_DATA_PATH")
RAW_TRAIN_DATA_PATH = _resolve_path("RAW_TRAIN_DATA_PATH")
RAW_TEST_DATA_PATH = _resolve_path("RAW_TEST_DATA_PATH")
PREDICTIONS_OUTPUT_PATH = _resolve_path("PREDICTIONS_OUTPUT_PATH")
IMAGES_DIR = _resolve_path("IMAGES_DIR")
TABLES_DIR = _resolve_path("TABLES_DIR")
MODELS_DIR = _resolve_path("MODELS_DIR")
