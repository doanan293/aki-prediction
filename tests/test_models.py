from pathlib import Path

import pytest

from src.models import _resolve_tabpfn_model_path, _validate_tabpfn_checkpoint


def test_validate_tabpfn_checkpoint_rejects_git_lfs_pointer(tmp_path: Path):
    checkpoint = tmp_path / "model.ckpt"
    checkpoint.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:abc123\n"
        "size 212860000\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Git LFS pointer"):
        _validate_tabpfn_checkpoint(checkpoint)


def test_validate_tabpfn_checkpoint_accepts_binary_file(tmp_path: Path):
    checkpoint = tmp_path / "model.ckpt"
    checkpoint.write_bytes(b"PK\x03\x04\x00\x00\x08\x08")

    _validate_tabpfn_checkpoint(checkpoint)


def test_resolve_tabpfn_model_path_prefers_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_checkpoint = tmp_path / "env-model.ckpt"
    env_checkpoint.write_bytes(b"PK\x03\x04\x00\x00\x08\x08")
    default_checkpoint = tmp_path / "default-model.ckpt"
    default_checkpoint.write_bytes(b"PK\x03\x04\x00\x00\x08\x08")

    monkeypatch.setenv("TABPFN_MODEL_PATH", str(env_checkpoint))

    assert _resolve_tabpfn_model_path(default_checkpoint) == env_checkpoint
