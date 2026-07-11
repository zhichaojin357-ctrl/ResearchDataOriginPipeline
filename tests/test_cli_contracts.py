from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from src.cli import main
from src.core.project import default_output_root, load_project_config


ROOT = Path(__file__).resolve().parents[1]


def test_origin_style_replay_resolves_relative_output_under_configured_root(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    plan = project / "plan.json"
    plan.write_text('{"items": []}', encoding="utf-8")
    configured_output_root = tmp_path / "configured-output"
    captured: dict[str, Path] = {}

    def fake_replay(_project: Path, _plan: Path, output_dir: Path, *, with_origin: bool = False) -> dict:
        captured["output_dir"] = output_dir
        return {
            "output_dir": str(output_dir),
            "planned_count": 1,
            "compared_count": 1,
            "failure_count": 0,
        }

    monkeypatch.chdir(project)
    monkeypatch.setenv("RESEARCH_PIPELINE_OUTPUT_ROOT", str(configured_output_root))
    monkeypatch.setattr("src.cli.run_origin_style_asset_replay", fake_replay)

    code = main(
        [
            "origin-style-asset-replay",
            "--template-plan",
            str(plan),
            "--output-dir",
            "style-replay",
        ]
    )

    assert code == 0
    assert captured["output_dir"] == configured_output_root / "style-replay"
    assert not (project / "style-replay").exists()


def test_origin_style_replay_rejects_output_outside_configured_root(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    raw_data = project / "input" / "raw_data"
    raw_data.mkdir(parents=True)
    plan = project / "plan.json"
    plan.write_text('{"items": []}', encoding="utf-8")
    configured_output_root = tmp_path / "configured-output"
    monkeypatch.chdir(project)
    monkeypatch.setenv("RESEARCH_PIPELINE_OUTPUT_ROOT", str(configured_output_root))

    with pytest.raises(ValueError, match="configured output root"):
        main(
            [
                "origin-style-asset-replay",
                "--template-plan",
                str(plan),
                "--output-dir",
                str(raw_data),
            ]
        )


def test_jeol_cli_returns_nonzero_when_no_workbooks_are_exported(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    source_root = tmp_path / "raw"
    output_root = tmp_path / "decoded"
    project.mkdir()
    source_root.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setattr("src.cli.export_jeol_cwesr_to_xlsx", lambda *_args, **_kwargs: {"exported_xlsx": 0})

    code = main(["jeol-epr-decode", "--out", str(output_root), str(source_root)])

    assert code == 1


def test_jeol_cli_rejects_output_that_overlaps_an_input_root(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    source_root = tmp_path / "raw"
    project.mkdir()
    source_root.mkdir()
    monkeypatch.chdir(project)

    with pytest.raises(ValueError, match="overlaps protected input"):
        main(["jeol-epr-decode", "--out", str(source_root), str(source_root)])


def test_jeol_cli_allows_an_independent_external_output_root(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    source_root = tmp_path / "raw"
    output_root = tmp_path / "decoded"
    project.mkdir()
    source_root.mkdir()
    captured: dict[str, Path] = {}

    def fake_export(_roots, out: Path, **_kwargs) -> dict:
        captured["output_root"] = out
        return {"exported_xlsx": 1}

    monkeypatch.chdir(project)
    monkeypatch.setattr("src.cli.export_jeol_cwesr_to_xlsx", fake_export)

    code = main(["jeol-epr-decode", "--out", str(output_root), str(source_root)])

    assert code == 0
    assert captured["output_root"] == output_root


@pytest.mark.parametrize(
    ("command", "extra_args"),
    [
        ("scan", []),
        ("triage", ["--dry-run"]),
        ("process", ["--no-origin"]),
    ],
)
def test_explicit_missing_config_path_is_a_cli_error(
    tmp_path: Path,
    command: str,
    extra_args: list[str],
) -> None:
    project = tmp_path / "project"
    raw_data = project / "input" / "raw_data"
    raw_data.mkdir(parents=True)
    missing_config = project / "config" / "missing.yaml"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "run.py"),
            command,
            "--input",
            str(raw_data),
            "--config",
            str(missing_config),
            *extra_args,
        ],
        cwd=project,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "explicit config file does not exist" in result.stderr
    assert "Traceback" not in result.stderr
    assert not default_output_root(project).exists()


def test_internal_optional_config_loading_still_allows_a_missing_file(tmp_path: Path) -> None:
    assert load_project_config(tmp_path, Path("config/optional-missing.yaml")) == {}
