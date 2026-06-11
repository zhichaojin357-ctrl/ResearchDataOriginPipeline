from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest


def pytest_configure() -> None:
    os.environ.setdefault("RESEARCHDATAORIGINPIPELINE_DISABLE_ORIGIN", "1")
    os.environ.setdefault("GROUPMEETINGAUTOPPT_DISABLE_ORIGIN", "1")


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolate_external_output_roots(tmp_path_factory: pytest.TempPathFactory):
    roots = {
        Path(tempfile.gettempdir()) / "\u8f93\u51fa",
        tmp_path_factory.getbasetemp() / "\u8f93\u51fa",
    }
    for root in roots:
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
    yield
    for root in roots:
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
