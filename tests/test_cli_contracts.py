from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.cli import build_parser, main
from src.core.project import default_output_root, load_project_config


ROOT = Path(__file__).resolve().parents[1]


def test_root_help_works_without_site_packages() -> None:
    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "run.py"), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 0
    assert "deps-audit" in result.stdout
    assert "Traceback" not in result.stderr


def test_build_parser_does_not_import_scientific_runtime() -> None:
    script = (
        "import sys; "
        "from src.cli import build_parser; "
        "build_parser(); "
        "forbidden = {'numpy', 'pandas', 'scipy', 'openpyxl', 'yaml'}; "
        "loaded = sorted(forbidden.intersection(sys.modules)); "
        "assert not loaded, loaded"
    )
    result = subprocess.run(
        [sys.executable, "-S", "-c", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_xps_and_xrd_force_flags_are_explicit_opt_in() -> None:
    parser = build_parser()
    xps_default = parser.parse_args(["xps-heterojunction-stacked", "--dry-run"])
    xps_force = parser.parse_args(
        ["xps-heterojunction-stacked", "--dry-run", "--force"]
    )
    xrd_required = [
        "xrd-overlay",
        "--bicu-source",
        "bicu.txt",
        "--bobc-source",
        "bobc.txt",
        "--cwo-source",
        "cwo.txt",
        "--cwo-card",
        "card.txt",
        "--dry-run",
    ]
    xrd_default = parser.parse_args(xrd_required)
    xrd_force = parser.parse_args([*xrd_required, "--force"])

    assert xps_default.force is False
    assert xps_force.force is True
    assert xrd_default.force is False
    assert xrd_force.force is True


def test_epr_overlay_accepts_explicit_output_root() -> None:
    args = build_parser().parse_args(
        [
            "epr-overlay",
            "--reference-dir",
            "refs",
            "--output-root",
            "external-output",
            "--group",
            "OH",
        ]
    )

    assert args.output_root == Path("external-output")
    assert args.config is None


def test_deps_audit_reports_missing_packages_without_import_crash(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "run.py"), "deps-audit"],
        cwd=project,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    audit_path = default_output_root(project) / "reports" / "dependency_audit.json"
    assert audit_path.is_file()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["summary"]["status"] == "fail"
    assert {"numpy", "pandas", "scipy", "openpyxl", "yaml"} <= set(audit["summary"]["missing_core"])


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
    monkeypatch.setattr("src.core.origin_style_assets.run_origin_style_asset_replay", fake_replay)

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
    monkeypatch.setattr(
        "src.core.epr_jeol.export_jeol_cwesr_to_xlsx",
        lambda *_args, **_kwargs: {"exported_xlsx": 0},
    )

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
    captured: dict[str, object] = {}

    def fake_export(_roots, out: Path, **kwargs) -> dict:
        captured["output_root"] = out
        captured["force"] = kwargs.get("force")
        return {"exported_xlsx": 1}

    monkeypatch.chdir(project)
    monkeypatch.setattr("src.core.epr_jeol.export_jeol_cwesr_to_xlsx", fake_export)

    code = main(["jeol-epr-decode", "--out", str(output_root), "--force", str(source_root)])

    assert code == 0
    assert captured["output_root"] == output_root
    assert captured["force"] is True


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
