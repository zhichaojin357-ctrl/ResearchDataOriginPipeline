from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from src.core import output_sanitizer
from src.core.output_sanitizer import (
    contains_local_absolute_path,
    render_output_path,
    sanitize_report_payload,
    scrub_output_text,
)


@pytest.mark.parametrize(
    "source",
    ["/home/researcher/data/sample.csv", "/home/researcher name/data/sample.csv", r"C:\Users\researcher\data\sample.csv", r"\\lab\data\sample.csv"],
)
def test_external_paths_are_sanitized_for_each_path_flavour(source: str, tmp_path: Path) -> None:
    assert render_output_path(source, project_root=tmp_path) == "external/sample.csv"
    assert scrub_output_text(f"failed to read {source}") == "failed to read external/sample.csv"
    assert contains_local_absolute_path(f"failed to read {source}")


@pytest.mark.parametrize("path_type", [PurePosixPath, PureWindowsPath])
@pytest.mark.parametrize("source", ["/home/researcher/data/sample.csv", "C:/Data/sample.csv", "//lab/data/sample.csv"])
def test_foreign_absolute_paths_do_not_depend_on_host_path_flavour(path_type, source: str, monkeypatch) -> None:
    monkeypatch.setattr(output_sanitizer, "Path", path_type)
    assert render_output_path(source) == "external/sample.csv"


def test_posix_report_paths_keep_known_roots_relative(tmp_path: Path) -> None:
    project = tmp_path / "project"
    output = tmp_path / "output"
    payload = {
        "source": str(project / "input" / "sample.csv"),
        "files": [str(output / "result.csv"), {"error": "failed to read /home/researcher/sample.csv"}],
    }
    cleaned = sanitize_report_payload(project, payload, output)
    assert cleaned == {
        "source": "input/sample.csv",
        "files": ["result.csv", {"error": "failed to read external/sample.csv"}],
    }
    assert render_output_path(output / "result.csv", project_root=project, output_root=output) == "output/result.csv"


@pytest.mark.parametrize("value", ["mA/cm^2", "1/cm", "input/raw_data/sample.csv", "https://example.com/data/sample.csv"])
def test_relative_paths_units_and_web_links_remain_unchanged(value: str) -> None:
    assert scrub_output_text(value) == value
    assert not contains_local_absolute_path(value)
