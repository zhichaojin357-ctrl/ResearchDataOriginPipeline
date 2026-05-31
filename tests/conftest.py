from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_configure() -> None:
    os.environ.setdefault("RESEARCHDATAORIGINPIPELINE_DISABLE_ORIGIN", "1")
    os.environ.setdefault("GROUPMEETINGAUTOPPT_DISABLE_ORIGIN", "1")


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]
