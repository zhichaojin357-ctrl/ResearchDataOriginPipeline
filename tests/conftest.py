from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def pytest_configure() -> None:
    os.environ.setdefault("RESEARCHDATAORIGINPIPELINE_DISABLE_ORIGIN", "1")
    os.environ.setdefault("GROUPMEETINGAUTOPPT_DISABLE_ORIGIN", "1")


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def tmp_path(tmp_path: Path) -> Path:
    # Production outputs are siblings of the project. Keep that sibling inside
    # this test's directory instead of sharing the pytest session's output root.
    project = tmp_path / "work"
    project.mkdir()
    return project


@pytest.fixture(autouse=True)
def isolate_external_output_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    temporary_root = tmp_path.parent / "temp"
    temporary_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporary_root))
    for name in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(name, str(temporary_root))
