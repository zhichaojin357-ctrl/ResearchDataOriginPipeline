from __future__ import annotations

import csv
import gc
import math
import re
import subprocess
import time
from dataclasses import dataclass, field
from numbers import Integral
from pathlib import Path
from typing import Any, Iterable

from src.origin.plot_policy import GRAPH4_FIXED_STYLE, Graph4FixedStyle
from src.origin.text_format import origin_bold_text, origin_chemical_subscripts


PLOT_TYPES = {
    "line": 200,
    "scatter": 201,
    "line+symbol": 202,
    "column": 203,
    "bar": 204,
    "area": 205,
    "histogram": 206,
    "box": 207,
    "contour": 208,
    "3d_scatter": 209,
    "3d_surface": 210,
    "pie": 212,
    "bubble": 228,
}

EXPORT_FORMATS = {
    "png": "png",
    "jpg": "jpg",
    "jpeg": "jpg",
    "tif": "tif",
    "tiff": "tif",
    "bmp": "bmp",
    "emf": "emf",
    "eps": "eps",
    "pdf": "pdf",
    "svg": "svg",
}

RASTER_EXPORT_FORMATS = frozenset({"bmp", "jpg", "png", "tif"})
MIN_EXPORT_DPI = 72
MAX_EXPORT_DPI = 1200
ORIGIN_PROCESS_START_TIMEOUT_SECONDS = 3.0
ORIGIN_PROCESS_EXIT_TIMEOUT_SECONDS = 3.0
ORIGIN_PROCESS_POLL_SECONDS = 0.1

ORIGIN_XML_STYLE_CLIPBOARD_FORMAT = "Origin XML Style"
THEME_APPLY_PAGE = 2

COLOR_MAP = {
    "black": 1,
    "red": 2,
    "green": 3,
    "blue": 4,
    "cyan": 5,
    "magenta": 6,
    "yellow": 7,
    "orange": 19,
    "purple": 13,
    "gray": 8,
    "grey": 8,
}

SYMBOL_SHAPES = {
    1: 2,
    2: 3,
    3: 1,
    4: 4,
    5: 5,
    6: 6,
}


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


def _plotxy_data_reference(
    data_book: str,
    data_sheet: str,
    x_col: int,
    y_col: int,
    *,
    y_error_col: int = 0,
    row_from: int = 0,
    row_to: int = 0,
) -> str:
    columns = [int(x_col), int(y_col)]
    if y_error_col > 0:
        columns.append(int(y_error_col))
    if row_from >= 1 and row_to >= row_from:
        body = ",".join(f"{column}[{row_from}:{row_to}]" for column in columns)
    else:
        body = ",".join(str(column) for column in columns)
    return f"[{data_book}]{data_sheet}!({body})"


def connect_origin(entrypoint: str = "Origin.Application", *, visible: bool = False, isolated: bool = True) -> "OriginOperations":
    """Start a task-owned Origin COM session and wrap it in the stable adapter.

    The pipeline must never attach to an Origin instance that may belong to the
    user.  ``DispatchEx`` is still used for isolation, but the process preflight
    is the fail-closed ownership boundary for every caller of this shared helper.
    """
    pre_existing_pids = origin_process_ids()
    if pre_existing_pids:
        rendered = ", ".join(str(pid) for pid in sorted(pre_existing_pids))
        raise RuntimeError(
            "Origin is already running; refusing to attach to or close an "
            f"existing session (PIDs: {rendered})."
        )

    import win32com.client

    if isolated and hasattr(win32com.client, "DispatchEx"):
        app = win32com.client.DispatchEx(entrypoint)
    else:
        app = win32com.client.Dispatch(entrypoint)
    try:
        app.Visible = 1 if visible else 0
    except Exception:
        pass
    try:
        owned_pids = _wait_for_new_origin_process_ids(
            pre_existing_pids,
            timeout_seconds=ORIGIN_PROCESS_START_TIMEOUT_SECONDS,
        )
    except Exception:
        try:
            app.Exit()
        except Exception:
            pass
        raise
    return OriginOperations(app, owned_process_ids=owned_pids)


def origin_process_ids() -> set[int]:
    """Return running Origin-family PIDs, failing closed if inspection fails."""

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "$originProcesses = Get-Process -Name Origin* -ErrorAction SilentlyContinue; "
            "foreach ($originProcess in $originProcesses) { "
            "try { "
            "if (@($originProcess.Threads).Count -gt 0) { $originProcess.Id } "
            "} catch { $originProcess.Id } "
            "}",
        ],
        text=True,
        capture_output=True,
        timeout=10,
    )
    if completed.returncode:
        details = (completed.stderr or completed.stdout or "PowerShell query failed").strip()
        raise RuntimeError(
            "Could not inspect existing Origin processes safely: " + details
        )

    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        value = line.strip()
        if not value:
            continue
        try:
            pid = int(value)
        except ValueError as exc:
            raise RuntimeError(
                "Could not inspect existing Origin processes safely: "
                f"unexpected process identifier {value!r}"
            ) from exc
        if pid <= 0:
            raise RuntimeError(
                "Could not inspect existing Origin processes safely: "
                f"invalid process identifier {pid}"
            )
        pids.add(pid)
    return pids


def _wait_for_new_origin_process_ids(
    pre_existing_pids: set[int],
    *,
    timeout_seconds: float,
) -> set[int]:
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    while True:
        current = origin_process_ids()
        owned = current - set(pre_existing_pids)
        if owned or time.monotonic() >= deadline:
            return owned
        time.sleep(ORIGIN_PROCESS_POLL_SECONDS)


def _wait_for_owned_origin_exit(
    owned_pids: set[int],
    *,
    timeout_seconds: float,
) -> set[int]:
    if not owned_pids:
        return set()
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    while True:
        remaining = origin_process_ids() & owned_pids
        if not remaining or time.monotonic() >= deadline:
            return remaining
        time.sleep(ORIGIN_PROCESS_POLL_SECONDS)


def _terminate_owned_origin_processes(owned_pids: set[int]) -> dict[str, object]:
    """Force-close only PIDs captured from this isolated Origin session."""

    requested = sorted({int(pid) for pid in owned_pids if int(pid) > 0})
    terminated: list[int] = []
    failures: list[dict[str, object]] = []
    for process_id in requested:
        script = (
            f"$originPid = {process_id}; "
            "$originProcess = Get-Process -Id $originPid -ErrorAction SilentlyContinue; "
            "if ($null -eq $originProcess) { exit 0 }; "
            "if ($originProcess.ProcessName -notlike 'Origin*') { exit 3 }; "
            "Stop-Process -Id $originPid -Force -ErrorAction Stop"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                text=True,
                capture_output=True,
                timeout=10,
            )
        except Exception as exc:
            failures.append({"pid": process_id, "error": str(exc)})
            continue
        if completed.returncode == 0:
            terminated.append(process_id)
        else:
            failures.append(
                {
                    "pid": process_id,
                    "returncode": completed.returncode,
                    "error": (completed.stderr or completed.stdout or "termination failed").strip(),
                }
            )
    return {
        "ok": not failures,
        "requested_pids": requested,
        "terminated_pids": terminated,
        "failures": failures,
    }


def quote_labtalk(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def quote_origin_text(value: object) -> str:
    return quote_labtalk(origin_chemical_subscripts(value))


def quote_origin_markup(value: object) -> str:
    """Escape a LabTalk string without doubling Origin rich-text markup."""

    return str(value or "").replace('"', '\\"').replace("\r", " ").replace("\n", " ")


def to_origin_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def safe_origin_name(value: str, default: str = "Page") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not cleaned:
        cleaned = default
    if cleaned[0].isdigit():
        cleaned = f"{default}_{cleaned}"
    return cleaned[:24]


def visible_origin_label(value: str | Path, default: str = "Data") -> str:
    text = str(value).replace("\\", "/").strip()
    if "/" in text:
        text = text.rstrip("/").split("/")[-1]
    return text or default


def normalize_export_path(file_path: str | Path, export_format: str = "png") -> tuple[Path, str]:
    output = Path(file_path)
    requested_format = (export_format or "png").strip().lower().lstrip(".")
    suffix_format = output.suffix.lower().lstrip(".")
    resolved_format = EXPORT_FORMATS.get(suffix_format) or EXPORT_FORMATS.get(requested_format)
    if resolved_format is None:
        supported = ", ".join(sorted(EXPORT_FORMATS))
        raise ValueError(f"Unsupported export format {export_format!r}. Supported: {supported}")
    if not output.suffix or EXPORT_FORMATS.get(suffix_format) != resolved_format:
        output = output.with_suffix(f".{resolved_format}")
    return output, resolved_format


def _parse_csv(path: Path, delimiter: str = ",") -> tuple[list[str], list[list[float]]]:
    actual_delimiter = "\t" if delimiter in {"\\t", "\t"} else delimiter
    if len(actual_delimiter) != 1:
        raise ValueError(f"delimiter must be a single character, got {delimiter!r}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.reader(handle, delimiter=actual_delimiter) if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError(f"no data rows found in {path}")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("ragged CSV rows are not supported")
    header: list[str] = []
    data_rows = rows
    try:
        [[float(cell) if cell.strip() else math.nan for cell in row] for row in rows]
    except ValueError:
        header = [cell.strip() for cell in rows[0]]
        data_rows = rows[1:]
    if not data_rows:
        raise ValueError(f"no numeric data rows found in {path}")
    numeric_rows = [[float(cell) if cell.strip() else math.nan for cell in row] for row in data_rows]
    columns = [[row[index] for row in numeric_rows] for index in range(width)]
    return header, columns


def _wait_for_file(path: Path, timeout_seconds: float = 8.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(0.25)
    return path.exists() and path.stat().st_size > 0


def _read_origin_xml_style_clipboard(timeout_seconds: float = 8.0) -> bytes | None:
    try:
        import win32clipboard
    except ImportError:
        return None

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        opened = False
        try:
            win32clipboard.OpenClipboard()
            opened = True
            fmt = 0
            while True:
                fmt = win32clipboard.EnumClipboardFormats(fmt)
                if fmt == 0:
                    break
                try:
                    name = win32clipboard.GetClipboardFormatName(fmt)
                except Exception:
                    continue
                if name != ORIGIN_XML_STYLE_CLIPBOARD_FORMAT:
                    continue
                data = win32clipboard.GetClipboardData(fmt)
                if isinstance(data, bytes):
                    return data
                if isinstance(data, str):
                    return data.encode("utf-8")
                return bytes(data)
        except Exception:
            time.sleep(0.2)
        finally:
            if opened:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass
    return None


class OriginOperations:
    """Stable, named Origin operation functions backed by Origin COM."""

    def __init__(
        self,
        app: Any,
        *,
        owned_process_ids: Iterable[int] | None = None,
    ):
        self.app = app
        self._owned_process_ids = {
            int(process_id)
            for process_id in (owned_process_ids or ())
            if int(process_id) > 0
        }

    def close(self) -> OperationResult:
        app = self.app
        self.app = None
        owned_pids = set(self._owned_process_ids)
        self._owned_process_ids.clear()
        if app is None:
            return OperationResult(True, "Origin already closed")
        exit_error = ""
        try:
            app.Exit()
        except Exception as exc:
            exit_error = str(exc)
        finally:
            del app
            try:
                import pythoncom

                pythoncom.CoFreeUnusedLibraries()
            except Exception:
                pass
            gc.collect()
        try:
            remaining = _wait_for_owned_origin_exit(
                owned_pids,
                timeout_seconds=ORIGIN_PROCESS_EXIT_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            remaining = set(owned_pids)
            inspection_error = str(exc)
        else:
            inspection_error = ""
        termination = {
            "ok": True,
            "requested_pids": [],
            "terminated_pids": [],
            "failures": [],
        }
        if remaining:
            termination = _terminate_owned_origin_processes(remaining)
            try:
                remaining = _wait_for_owned_origin_exit(
                    remaining,
                    timeout_seconds=ORIGIN_PROCESS_EXIT_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                inspection_error = str(exc)
        ok = not remaining and not inspection_error
        forced = bool(termination.get("requested_pids"))
        message = (
            "Origin closed and COM proxy released"
            if ok and not forced and not exit_error
            else "Task-owned Origin process force-closed and COM proxy released"
            if ok
            else "Origin close left an active task-owned process"
        )
        return OperationResult(
            ok,
            message,
            {
                "owned_process_ids": sorted(owned_pids),
                "graceful_exit": not exit_error and not forced,
                "exit_error": exit_error,
                "forced_process_termination": forced,
                "termination": termination,
                "remaining_process_ids": sorted(remaining),
                "inspection_error": inspection_error,
            },
        )

    def run_labtalk(self, script: str) -> OperationResult:
        ok = bool(self.app.Execute(script))
        return OperationResult(ok, "LabTalk executed" if ok else "LabTalk returned failure", {"script": script})

    def get_labtalk_variable(self, name: str) -> OperationResult:
        if name.endswith("$"):
            value = self.app.LTStr(name)
        else:
            value = self.app.LTVar(name)
        return OperationResult(True, f"Read LabTalk variable {name}", {"name": name, "value": value})

    def new_project(self) -> OperationResult:
        self.app.NewProject()
        return OperationResult(True, "New Origin project created")

    def save_project(self, file_path: str | Path = "") -> OperationResult:
        target = str(file_path) if file_path else ""
        self.sanitize_project_metadata()
        self.app.Save(target)
        return OperationResult(True, "Project saved", {"file_path": target})

    def sanitize_project_metadata(self) -> OperationResult:
        script = (
            'doc -e W { page.comments$=""; page.comment$=""; wks.comments$=""; wks.comment$=""; }; '
            'doc -e P { page.comments$=""; page.comment$=""; };'
        )
        try:
            self.app.Execute(script)
        except Exception as exc:
            return OperationResult(False, f"Origin page metadata sanitization failed: {exc}", {"script": script})
        return OperationResult(True, "Origin page metadata sanitized", {"script": script})

    def reset_project_identity_for_export(self) -> OperationResult:
        """Detach the in-memory project identity before exporting path-bearing image metadata."""
        script = "doc -rn; doc -s;"
        try:
            executed = bool(self.app.Execute(script))
        except Exception:
            return OperationResult(False, "Origin project identity reset command failed before export.")
        if not executed:
            return OperationResult(False, "Origin project identity reset command failed before export.")
        try:
            project_path = self.app.LTStr("%X")
            project_name = self.app.LTStr("%G")
        except Exception:
            return OperationResult(False, "Origin project identity verification failed before export.")
        path_is_empty = str(project_path).strip() == ""
        name_is_untitled = str(project_name).strip().casefold() == "untitled"
        if not path_is_empty or not name_is_untitled:
            return OperationResult(
                False,
                "Origin project identity verification failed before export.",
                {
                    "project_path_empty": path_is_empty,
                    "project_name_untitled": name_is_untitled,
                },
            )
        return OperationResult(
            True,
            "Origin project identity reset and verified for export.",
            {
                "project_path_empty": True,
                "project_name_untitled": True,
            },
        )

    def load_project(self, file_path: str | Path) -> OperationResult:
        path = Path(file_path)
        if not path.exists():
            return OperationResult(False, f"Origin project file not found: {path}")
        self.app.Load(str(path))
        return OperationResult(True, "Project loaded", {"file_path": str(path)})

    def create_worksheet(self, book_name: str, sheet_name: str = "Sheet1") -> OperationResult:
        visible_book = visible_origin_label(book_name, "Book")
        visible_sheet = visible_origin_label(sheet_name, "Data")
        book = self.app.CreatePage(2, safe_origin_name(visible_book, "Book"), "origin")
        self.run_labtalk(
            f'win -a "{quote_labtalk(book)}"; '
            f'page.longname$="{quote_labtalk(visible_book)}"; page.comments$=""; page.comment$=""; '
            f'wks.name$="{quote_labtalk(safe_origin_name(visible_sheet, "Data"))}"; '
            f'wks.longname$="{quote_labtalk(visible_sheet)}"; wks.comments$=""; wks.comment$="";'
        )
        return OperationResult(True, "Worksheet created", {"book_name": book, "sheet_name": sheet_name})

    def add_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
        """Append one named worksheet to an existing workbook and activate it."""

        book = str(book_name).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", book):
            return OperationResult(False, "Worksheet book has an unsafe internal name")
        visible_sheet = visible_origin_label(sheet_name, "Data")
        internal_sheet = safe_origin_name(visible_sheet, "Data")
        created = self.run_labtalk(
            f'win -a "{quote_labtalk(book)}"; '
            f'newsheet name:="{quote_labtalk(internal_sheet)}" active:=1; '
            f'wks.name$="{quote_labtalk(internal_sheet)}"; '
            f'wks.longname$="{quote_labtalk(visible_sheet)}"; '
            'wks.comments$="";'
        )
        if not created.ok:
            return OperationResult(False, f"Could not add worksheet to workbook: {book}")
        return OperationResult(
            True,
            "Worksheet added",
            {"book_name": book, "sheet_name": internal_sheet},
        )

    def set_worksheet_data(
        self,
        book_name: str,
        sheet_name: str,
        columns: Iterable[Iterable[float]],
        column_names: Iterable[str] | None = None,
    ) -> OperationResult:
        target = f"[{book_name}]{sheet_name}"
        data_columns = [[float(value) for value in column] for column in columns]
        if not data_columns:
            return OperationResult(False, "No columns provided")
        for index, column in enumerate(data_columns):
            self.app.PutWorksheet(target, column, 0, index)
        names = list(column_names or [])
        if names:
            self.run_labtalk(f'win -a "{quote_labtalk(book_name)}";')
            for index, name in enumerate(names, start=1):
                self.run_labtalk(f'wks.col{index}.lname$ = "{quote_labtalk(name)}";')
        return OperationResult(
            True,
            "Worksheet data written",
            {"target": target, "columns": len(data_columns), "rows": len(data_columns[0])},
        )

    def set_worksheet_column_mask_rows(
        self,
        book_name: str,
        column_index: int,
        masked_rows: Iterable[int],
        *,
        sheet_index: int = 1,
    ) -> OperationResult:
        """Apply worksheet-cell masks in a task-owned fresh workbook.

        Origin stores masking as worksheet state rather than as a numeric data
        value.  Replaying only X/Y numbers would therefore expose points that
        were intentionally masked in the reviewed graph.  This operation uses
        Origin's native ``dataset<row>`` mask syntax after validating every
        book, sheet, column, and row identifier.
        """

        book = str(book_name).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", book):
            return OperationResult(False, "Worksheet book has an unsafe internal name")
        try:
            column = int(column_index)
            sheet = int(sheet_index)
        except (TypeError, ValueError):
            return OperationResult(False, "Worksheet mask column/sheet index is not numeric")
        if column < 1 or sheet < 1:
            return OperationResult(
                False,
                "Worksheet mask column/sheet indices must be one-based and positive",
            )
        normalized_rows: list[int] = []
        for raw_row in masked_rows:
            try:
                row = int(raw_row)
            except (TypeError, ValueError):
                return OperationResult(False, "Worksheet mask row is not numeric")
            if row < 1:
                return OperationResult(False, "Worksheet mask rows must be positive")
            normalized_rows.append(row)
        normalized_rows = sorted(set(normalized_rows))
        if not normalized_rows:
            return OperationResult(
                True,
                "No worksheet masks requested",
                {
                    "book_name": book,
                    "sheet_index": sheet,
                    "column_index": column,
                    "masked_rows": [],
                },
            )
        activated = self.run_labtalk(
            f'win -a "{quote_labtalk(book)}"; layer -s {sheet};'
        )
        if not activated.ok:
            return OperationResult(
                False,
                f"Could not activate worksheet book/sheet for masking: {book}/{sheet}",
            )
        commands = " ".join(
            f"wcol({column})<{row}>=1;" for row in normalized_rows
        )
        written = self.run_labtalk(commands)
        if not written.ok:
            return OperationResult(
                False,
                f"Could not apply worksheet masks: {book}/{sheet}/col{column}",
            )
        return OperationResult(
            True,
            "Worksheet masks applied",
            {
                "book_name": book,
                "sheet_index": sheet,
                "column_index": column,
                "masked_rows": normalized_rows,
            },
        )

    def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
        target = f"[{book_name}]{sheet_name}"
        data = self.app.GetWorksheet(target)
        if data is None:
            return OperationResult(False, f"Worksheet not found: {target}")
        try:
            rows = list(data)
        except TypeError:
            return OperationResult(False, f"Worksheet data is not iterable: {target}")
        if not rows:
            return OperationResult(True, "Worksheet data read", {"columns": []})
        try:
            column_count = len(rows[0])
        except TypeError:
            return OperationResult(False, f"Worksheet row data is not iterable: {target}")
        columns = [[row[index] for row in rows] for index in range(column_count)]
        return OperationResult(True, "Worksheet data read", {"target": target, "columns": columns})

    def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
        layer = self._graph_layer(graph_name, layer_index)
        if not layer:
            return OperationResult(False, f"Graph layer not found: [{graph_name}]{int(layer_index)}")
        data_plots = layer.DataPlots
        names = [str(data_plots.Item(index).Name) for index in range(data_plots.Count)]
        return OperationResult(
            True,
            "Graph plot dataset names read",
            {"graph_name": graph_name, "layer_index": int(layer_index), "plot_dataset_names": names},
        )

    def get_graph_plot_dataset_mappings(self, graph_name: str, layer_index: int = 1) -> OperationResult:
        """Read every plot's actual X/Y datasets from the active Origin layer.

        ``DataPlot.Name`` exposes only the plotted Y dataset.  That is not
        enough for templates containing independent X/Y pairs or datasets on
        later worksheet sheets.  ``range -wx/-wy`` resolves the actual plot
        datasets and ``nameof(range)$`` preserves an ``@sheet`` creation-index
        suffix where applicable.  This path is used because direct
        ``nameof(plotdata(...))$`` assignment is not evaluated reliably by the
        installed Origin COM/LabTalk bridge.
        """

        layer = self._graph_layer(graph_name, layer_index)
        if not layer:
            return OperationResult(False, f"Graph layer not found: [{graph_name}]{int(layer_index)}")
        graph_reference = str(graph_name).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", graph_reference):
            return OperationResult(False, "Graph page has an unsafe internal name for plot-range readback")
        data_plots = layer.DataPlots
        activated = self.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; layer -s {int(layer_index)};'
        )
        if not activated.ok:
            return OperationResult(
                False,
                f"Could not activate graph layer: [{graph_name}]{int(layer_index)}",
            )

        mappings: list[dict[str, object]] = []
        x_names: list[str] = []
        y_names: list[str] = []
        failure_count = 0
        for zero_based_index in range(int(data_plots.Count)):
            plot_index = zero_based_index + 1
            expected_y = str(data_plots.Item(zero_based_index).Name)
            script = (
                'string __rdop_plot_x$=""; string __rdop_plot_y$=""; '
                f'range -wx __rdop_plot_x_range=[{graph_reference}]{int(layer_index)}!{plot_index}; '
                f'range -wy __rdop_plot_y_range=[{graph_reference}]{int(layer_index)}!{plot_index}; '
                f'range __rdop_plot_range=[{graph_reference}]{int(layer_index)}!{plot_index}; '
                '__rdop_plot_x$=nameof(__rdop_plot_x_range)$; '
                '__rdop_plot_y$=nameof(__rdop_plot_y_range)$; '
                '__rdop_plot_begin=nan; __rdop_plot_end=nan; '
                'get __rdop_plot_range -b __rdop_plot_begin; '
                'get __rdop_plot_range -e __rdop_plot_end;'
            )
            executed = self.run_labtalk(script)
            if executed.ok:
                x_dataset = str(self.app.LTStr("__rdop_plot_x$") or "").strip()
                y_dataset = str(self.app.LTStr("__rdop_plot_y$") or "").strip()
                try:
                    row_from = int(round(float(self.app.LTVar("__rdop_plot_begin"))))
                    row_to = int(round(float(self.app.LTVar("__rdop_plot_end"))))
                except (TypeError, ValueError, OverflowError):
                    row_from = 0
                    row_to = -1
            else:
                x_dataset = ""
                y_dataset = ""
                row_from = 0
                row_to = -1
            dataplot_name_matches = bool(y_dataset and y_dataset == expected_y)
            ready = bool(
                x_dataset
                and y_dataset
                and dataplot_name_matches
                and row_from >= 1
                and row_to >= row_from
            )
            if not ready:
                failure_count += 1
            mappings.append(
                {
                    "plot_index": plot_index,
                    "x_dataset": x_dataset,
                    "y_dataset": y_dataset,
                    "dataplot_name": expected_y,
                    "dataplot_name_matches": dataplot_name_matches,
                    "row_from": row_from,
                    "row_to": row_to,
                    "row_count": row_to - row_from + 1 if ready else 0,
                    "status": "ready" if ready else "mapping_read_failed",
                }
            )
            x_names.append(x_dataset)
            y_names.append(y_dataset)

        return OperationResult(
            True,
            "Graph plot X/Y dataset mappings read",
            {
                "graph_name": graph_name,
                "layer_index": int(layer_index),
                "plot_count": int(data_plots.Count),
                "mapping_failure_count": failure_count,
                "plot_x_dataset_names": x_names,
                "plot_y_dataset_names": y_names,
                "plot_dataset_names": y_names,
                "plot_mappings": mappings,
                "mapping_source": "Origin range -wx/-wy plus nameof(range)$",
            },
        )

    def _graph_layer(self, graph_name: str, layer_index: int = 1) -> Any:
        graph = str(graph_name)
        index = int(layer_index)
        candidates = [f"[{graph}]{index}", f"[{graph}]Layer{index}"]
        if index == 1:
            candidates.extend([f"[{graph}]", graph])
        for reference in candidates:
            try:
                layer = self.app.FindGraphLayer(reference)
            except Exception:
                layer = None
            if layer:
                return layer
        return None

    def replace_template_workbook_columns(self, workbook_columns: dict[str, dict[int, Iterable[float]]]) -> OperationResult:
        return self.replace_template_worksheet_columns(
            {
                str(book_name): {"Sheet1": columns}
                for book_name, columns in workbook_columns.items()
            }
        )

    def replace_template_worksheet_columns(
        self,
        worksheet_columns: dict[str, dict[str | int, dict[int, Iterable[float]]]],
    ) -> OperationResult:
        """Replace explicitly addressed worksheet columns without guessing a sheet.

        Sheet references may be worksheet names or Origin creation indices.  A
        creation index is necessary for dataset names such as ``Book1_G@2``.
        """

        updated: list[dict[str, object]] = []
        for book_name, sheets in worksheet_columns.items():
            if not book_name or not sheets:
                continue
            for sheet_reference, columns in sheets.items():
                if not columns:
                    continue
                sheet = str(sheet_reference).strip()
                if not sheet:
                    continue
                target = f"[{book_name}]{sheet}"
                for column_index, values in sorted(columns.items()):
                    column_values = [_origin_numeric_or_missing(value) for value in values]
                    write_mode = self._put_template_workbook_column(target, column_values, int(column_index))
                    updated.append(
                        {
                            "book_name": str(book_name),
                            "sheet_reference": sheet,
                            "column_index": int(column_index),
                            "rows": len(column_values),
                            "write_mode": write_mode,
                        }
                    )
        if not updated:
            return OperationResult(False, "No template worksheet columns were provided")
        return OperationResult(True, "Template worksheet columns replaced", {"updated_columns": updated})

    def _put_template_workbook_column(
        self,
        target: str,
        column_values: list[float],
        column_index: int,
        *,
        row_start: int = 0,
    ) -> str:
        try:
            self.app.PutWorksheet(target, column_values, int(row_start), column_index)
            return "single"
        except Exception:
            if len(column_values) <= 1:
                raise
            chunk_size = 512
            for chunk_offset in range(0, len(column_values), chunk_size):
                self.app.PutWorksheet(
                    target,
                    column_values[chunk_offset : chunk_offset + chunk_size],
                    int(row_start) + chunk_offset,
                    column_index,
                )
            return f"chunked_{chunk_size}"

    def import_csv_to_worksheet(self, file_path: str | Path, book_name: str = "", delimiter: str = ",") -> OperationResult:
        path = Path(file_path)
        if not path.exists():
            return OperationResult(False, f"CSV file not found: {path}")
        header, columns = _parse_csv(path, delimiter)
        created = self.create_worksheet(book_name or path.stem)
        if not created.ok:
            return created
        actual_book = str(created.payload["book_name"])
        written = self.set_worksheet_data(actual_book, "Sheet1", columns, header or None)
        if not written.ok:
            return written
        return OperationResult(True, "CSV imported", {"book_name": actual_book, "columns": len(columns), "rows": len(columns[0])})

    def list_worksheets(self) -> OperationResult:
        self.run_labtalk(
            'string __rdop_pages$ = ""; '
            'doc -e W { __rdop_pages$ = __rdop_pages$ + page.name$ + "|workbook;"; }; '
            'doc -e P { __rdop_pages$ = __rdop_pages$ + page.name$ + "|graph;"; };'
        )
        raw = str(self.app.LTStr("__rdop_pages$"))
        pages = []
        for entry in raw.split(";"):
            if not entry:
                continue
            name, _, page_type = entry.partition("|")
            if name and page_type:
                pages.append({"name": name, "type": page_type})
        return OperationResult(True, "Pages listed", {"pages": pages})

    def create_graph(
        self,
        graph_name: str,
        data_book: str,
        data_sheet: str,
        x_col: int,
        y_col: int,
        plot_type: str = "line",
        y_error_col: int = 0,
        title: str = "",
        row_from: int = 0,
        row_to: int = 0,
    ) -> OperationResult:
        ptype = PLOT_TYPES.get(plot_type)
        if ptype is None:
            return OperationResult(False, f"Unsupported plot type: {plot_type}")
        graph = self.app.CreatePage(3, safe_origin_name(graph_name, "Graph"), "origin")
        data_ref = _plotxy_data_reference(
            data_book,
            data_sheet,
            x_col,
            y_col,
            y_error_col=y_error_col,
            row_from=row_from,
            row_to=row_to,
        )
        self.run_labtalk(f"plotxy iy:={data_ref} plot:={ptype} ogl:=[{graph}]Layer1;")
        if title:
            self.run_labtalk(f'label -n title -s "{quote_origin_text(title)}"; title.x = 50; title.y = 95;')
        return OperationResult(True, "Graph created", {"graph_name": graph, "plot_type": plot_type})

    def create_graph_from_template(self, graph_name: str, template_path: str | Path) -> OperationResult:
        path = Path(template_path)
        if not path.is_file():
            return OperationResult(False, f"Graph template file not found: {path}")
        template_arg = str(path)
        if path.is_absolute():
            self.run_labtalk(f'cd "{quote_labtalk(to_origin_path(path.parent))}";')
            template_arg = path.name
        graph = self.app.CreatePage(3, safe_origin_name(graph_name, "Graph"), template_arg)
        return OperationResult(True, "Graph created from template", {"graph_name": graph, "template_path": str(path)})

    def create_graph_from_xy_pairs_template(
        self,
        graph_name: str,
        template_path: str | Path,
        data_book: str,
        xy_ranges: Iterable[dict[str, object]],
        *,
        plot_type: str = "line+symbol",
        rescale: bool = False,
        legend: bool = False,
        group_plots: bool = False,
        group_layer_indices: Iterable[int] | None = None,
        individual_stack_offsets: Iterable[dict[str, object]] | None = None,
        plot_format_contracts: Iterable[dict[str, object]] | None = None,
    ) -> OperationResult:
        """Create a fresh graph from one OTP/OTPU and explicit worksheet X/Y ranges.

        Passing the absolute template path directly to ``plotxy`` loads the
        complete graph-template format tree.  This preserves formatting that a
        partial property replay cannot represent, including rich-text axis
        titles, font sizes, legend geometry, plot holders, axes, and layout.
        """

        path = Path(template_path)
        if not path.is_file() or path.suffix.casefold() not in {".otp", ".otpu"}:
            return OperationResult(False, f"Graph template file not found or unsupported: {path}")
        ptype = PLOT_TYPES.get(plot_type)
        if ptype is None:
            return OperationResult(False, f"Unsupported plot type: {plot_type}")
        safe_graph = safe_origin_name(graph_name, "Graph")
        safe_book = str(data_book).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", safe_book):
            return OperationResult(False, "Worksheet book has an unsafe internal name for template plotting")

        rendered_ranges: list[str] = []
        normalized_ranges: list[dict[str, object]] = []
        explicit_layer_indices: list[int | None] = []
        for raw in xy_ranges:
            if not isinstance(raw, dict):
                return OperationResult(False, "Every template XY range must be an object")
            try:
                x_col = int(raw.get("x_col"))
                y_col = int(raw.get("y_col"))
                row_from = int(raw.get("row_from"))
                row_to = int(raw.get("row_to"))
            except (TypeError, ValueError):
                return OperationResult(False, "Template XY range has nonnumeric column or row indices")
            if min(x_col, y_col, row_from) < 1 or row_to < row_from:
                return OperationResult(False, "Template XY range has invalid column or row bounds")
            range_book_value = raw.get("book_name")
            range_book: str | None = None
            if range_book_value is not None:
                range_book = str(range_book_value).strip()
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", range_book):
                    return OperationResult(False, "Template XY range has an unsafe workbook internal name")
            sheet_value = raw.get("sheet_index")
            normalized = {
                "x_col": x_col,
                "y_col": y_col,
                "row_from": row_from,
                "row_to": row_to,
            }
            if range_book is not None:
                normalized["book_name"] = range_book
            layer_value = raw.get("layer_index")
            layer_index: int | None = None
            if layer_value is not None:
                if isinstance(layer_value, bool):
                    return OperationResult(False, "Template XY range graph layer index must be a positive integer")
                try:
                    layer_index = int(layer_value)
                except (TypeError, ValueError):
                    return OperationResult(False, "Template XY range has a nonnumeric graph layer index")
                if isinstance(layer_value, float) and not layer_value.is_integer():
                    return OperationResult(False, "Template XY range graph layer index must be a positive integer")
                if layer_index < 1:
                    return OperationResult(False, "Template XY range graph layer index must be positive")
                normalized["layer_index"] = layer_index
            if sheet_value is None and range_book is None:
                rendered_ranges.append(f"({x_col},{y_col}[{row_from}:{row_to}])")
            else:
                if sheet_value is None:
                    sheet_index = 1
                else:
                    try:
                        sheet_index = int(sheet_value)
                    except (TypeError, ValueError):
                        return OperationResult(False, "Template XY range has a nonnumeric worksheet index")
                if sheet_index < 1:
                    return OperationResult(False, "Template XY range worksheet index must be positive")
                rendered_ranges.append(
                    f"[{range_book or safe_book}]{sheet_index}!"
                    f"({x_col}[{row_from}:{row_to}],{y_col}[{row_from}:{row_to}])"
                )
                normalized["sheet_index"] = sheet_index
            normalized_ranges.append(normalized)
            explicit_layer_indices.append(layer_index)
        if not rendered_ranges:
            return OperationResult(False, "No template XY ranges were provided")

        requested_group_layers: set[int] = set()
        if group_layer_indices is not None:
            for raw_layer_index in group_layer_indices:
                if isinstance(raw_layer_index, bool):
                    return OperationResult(
                        False,
                        "Template plot-group layer index must be a positive integer",
                    )
                try:
                    layer_index = int(raw_layer_index)
                except (TypeError, ValueError):
                    return OperationResult(
                        False,
                        "Template plot-group layer index is nonnumeric",
                    )
                if (
                    isinstance(raw_layer_index, float)
                    and not raw_layer_index.is_integer()
                ) or layer_index < 1:
                    return OperationResult(
                        False,
                        "Template plot-group layer index must be a positive integer",
                    )
                requested_group_layers.add(layer_index)

        normalized_stack_offsets: list[dict[str, float | int]] = []
        for raw_offset in individual_stack_offsets or ():
            if not isinstance(raw_offset, dict):
                return OperationResult(
                    False,
                    "Every individual stack-offset contract must be an object",
                )
            try:
                layer_index = int(raw_offset.get("layer_index"))
                plot_index = int(raw_offset.get("plot_index"))
                x_offset = float(raw_offset.get("x_offset", 0.0))
                y_offset = float(raw_offset.get("y_offset", 0.0))
                x_multiplier = float(raw_offset.get("x_multiplier", 1.0))
                y_multiplier = float(raw_offset.get("y_multiplier", 1.0))
            except (TypeError, ValueError, OverflowError):
                return OperationResult(
                    False,
                    "Individual stack-offset contract contains a nonnumeric value",
                )
            if layer_index < 1 or plot_index < 1:
                return OperationResult(
                    False,
                    "Individual stack-offset layer and plot indices must be positive",
                )
            if not all(
                math.isfinite(value)
                for value in (x_offset, y_offset, x_multiplier, y_multiplier)
            ):
                return OperationResult(
                    False,
                    "Individual stack-offset values must be finite",
                )
            normalized_stack_offsets.append(
                {
                    "layer_index": layer_index,
                    "plot_index": plot_index,
                    "x_offset": x_offset,
                    "y_offset": y_offset,
                    "x_multiplier": x_multiplier,
                    "y_multiplier": y_multiplier,
                }
            )

        plot_format_option_map = {
            "color": "c",
            "line_color": "cl",
            "line_width": "w",
            "line_style": "d",
            "connect": "l",
            "vertical_drop_lines": "lv",
            "vertical_drop_line_color": "lvc",
            "vertical_drop_line_style": "lvs",
            "vertical_drop_line_width": "lvw",
        }
        normalized_plot_formats: list[dict[str, object]] = []
        plot_format_targets: set[tuple[int, int]] = set()
        for raw_format in plot_format_contracts or ():
            if not isinstance(raw_format, dict):
                return OperationResult(
                    False,
                    "Every native plot-format contract must be an object",
                )
            try:
                layer_index = int(raw_format.get("layer_index"))
                plot_index = int(raw_format.get("plot_index"))
            except (TypeError, ValueError):
                return OperationResult(
                    False,
                    "Native plot-format layer and plot indices must be numeric",
                )
            if layer_index < 1 or plot_index < 1:
                return OperationResult(
                    False,
                    "Native plot-format layer and plot indices must be positive",
                )
            target = (layer_index, plot_index)
            if target in plot_format_targets:
                return OperationResult(
                    False,
                    "Native plot-format contract contains a duplicate layer/plot target",
                )
            values: dict[str, float] = {}
            for key in plot_format_option_map:
                if key not in raw_format:
                    continue
                try:
                    value = float(raw_format[key])
                except (TypeError, ValueError, OverflowError):
                    return OperationResult(
                        False,
                        f"Native plot-format value is nonnumeric: {key}",
                    )
                if not math.isfinite(value):
                    return OperationResult(
                        False,
                        f"Native plot-format value must be finite: {key}",
                    )
                values[key] = value
            if not values:
                return OperationResult(
                    False,
                    "Native plot-format contract contains no supported properties",
                )
            plot_format_targets.add(target)
            normalized_plot_formats.append(
                {
                    "layer_index": layer_index,
                    "plot_index": plot_index,
                    **values,
                }
            )

        activated = self.run_labtalk(f'win -a "{quote_labtalk(safe_book)}"; layer -s 1;')
        if not activated.ok:
            return OperationResult(False, f"Could not activate template data workbook: {safe_book}")
        uses_explicit_layers = any(index is not None for index in explicit_layer_indices)
        if uses_explicit_layers:
            for normalized, layer_index in zip(normalized_ranges, explicit_layer_indices):
                normalized.setdefault("layer_index", layer_index or 1)
            # Origin's template resolver prefers installed templates when it
            # receives only a basename.  Scientific product names such as
            # XRD can collide with Origin's own system templates, silently
            # producing a valid-looking but completely different graph.
            # CreatePage accepts an absolute path (including Unicode paths),
            # so keep the detached asset identity explicit.
            template_arg = str(path.resolve())
            if path.is_absolute():
                # Keep this best-effort for compatibility with
                # ``create_graph_from_template``: Origin can still resolve a
                # template filename after ``cd`` reports a nonzero status.
                self.run_labtalk(f'cd "{quote_labtalk(to_origin_path(path.parent))}";')
            try:
                created_graph = self.app.CreatePage(3, safe_graph, template_arg)
            except Exception as exc:
                return OperationResult(
                    False,
                    f"Origin could not create a blank graph from template: {path.name}: {exc}",
                    {"graph_name": safe_graph, "template_path": str(path)},
                )
            if not created_graph:
                return OperationResult(
                    False,
                    f"Origin could not create a blank graph from template: {path.name}",
                    {"graph_name": safe_graph, "template_path": str(path)},
                )
            template_axis_scales: dict[int, dict[str, float]] = {}
            for layer_index in sorted(
                {int(item["layer_index"]) for item in normalized_ranges}
            ):
                variables = {
                    # Keep LabTalk numeric identifiers short.  Older Origin
                    # engines truncate long identifiers, which can make the
                    # five values alias one another silently.
                    "x_from": f"rt{layer_index}xf",
                    "x_to": f"rt{layer_index}xt",
                    "y_from": f"rt{layer_index}yf",
                    "y_to": f"rt{layer_index}yt",
                    "link": f"rt{layer_index}lk",
                }
                captured = self.run_labtalk(
                    f'win -a "{quote_labtalk(safe_graph)}"; layer -s {layer_index}; '
                    f'{variables["x_from"]}=layer.x.from; '
                    f'{variables["x_to"]}=layer.x.to; '
                    f'{variables["y_from"]}=layer.y.from; '
                    f'{variables["y_to"]}=layer.y.to; '
                    f'{variables["link"]}=layer.link;'
                )
                if not captured.ok:
                    return OperationResult(
                        False,
                        "Origin template axis scales could not be captured before plotting",
                        {"graph_name": safe_graph, "layer_index": layer_index},
                    )
                scale: dict[str, float] = {}
                for key, variable in variables.items():
                    try:
                        value = float(
                            self.get_labtalk_variable(variable).payload.get("value")
                        )
                    except (TypeError, ValueError, OverflowError):
                        return OperationResult(
                            False,
                            "Origin template axis scale readback was nonnumeric",
                            {
                                "graph_name": safe_graph,
                                "layer_index": layer_index,
                                "property": key,
                            },
                        )
                    if not math.isfinite(value):
                        return OperationResult(
                            False,
                            "Origin template axis scale readback was not finite",
                            {
                                "graph_name": safe_graph,
                                "layer_index": layer_index,
                                "property": key,
                            },
                        )
                    scale[key] = value
                template_axis_scales[layer_index] = scale
            for rendered_range, normalized in zip(rendered_ranges, normalized_ranges):
                layer_index = int(normalized["layer_index"])
                command = (
                    f"plotxy iy:={rendered_range} plot:={ptype} size:=-1 "
                    f"rescale:={1 if rescale else 0} legend:={1 if legend else 0} "
                    # Target by one-based layer index.  Reviewed overlay
                    # templates commonly rename layers (for example RightY),
                    # so synthesizing ``Layer2`` can report success while
                    # adding no plot at all.
                    f"ogl:=[{safe_graph}]{layer_index};"
                )
                plotted = self.run_labtalk(command)
                if not plotted.ok:
                    return OperationResult(
                        False,
                        f"Origin plotxy failed for graph layer {layer_index} from template: {path.name}",
                        {
                            "graph_name": safe_graph,
                            "template_path": str(path),
                            "layer_index": layer_index,
                        },
                    )
        else:
            template_axis_scales = {}
            template = quote_labtalk(to_origin_path(path.resolve()))
            command = (
                f"plotxy iy:=({','.join(rendered_ranges)}) plot:={ptype} size:=-1 "
                f"rescale:={1 if rescale else 0} legend:={1 if legend else 0} "
                f'ogl:=[<new template:="{template}" name:="{quote_labtalk(safe_graph)}">];'
            )
            plotted = self.run_labtalk(command)
            if not plotted.ok:
                return OperationResult(
                    False,
                    f"Origin plotxy failed to create graph from template: {path.name}",
                    {"graph_name": safe_graph, "template_path": str(path)},
                )
        if uses_explicit_layers:
            expected_by_layer: dict[int, int] = {}
            for normalized in normalized_ranges:
                layer_index = int(normalized["layer_index"])
                expected_by_layer[layer_index] = expected_by_layer.get(layer_index, 0) + 1
            actual_plot_count = 0
            for layer_index, expected_count in expected_by_layer.items():
                layer = self._graph_layer(safe_graph, layer_index)
                if layer is None:
                    return OperationResult(
                        False,
                        f"Origin template graph layer {layer_index} was not created",
                        {
                            "graph_name": safe_graph,
                            "template_path": str(path),
                            "layer_index": layer_index,
                        },
                    )
                actual_count = int(layer.DataPlots.Count)
                if actual_count != expected_count:
                    return OperationResult(
                        False,
                        "Origin template graph layer plot count does not match the explicit XY ranges",
                        {
                            "graph_name": safe_graph,
                            "template_path": str(path),
                            "layer_index": layer_index,
                            "expected_plot_count": expected_count,
                            "actual_plot_count": actual_count,
                        },
                    )
                actual_plot_count += actual_count
        else:
            layer = self._graph_layer(safe_graph, 1)
            if layer is None:
                return OperationResult(
                    False,
                    "Origin plotxy returned success but the requested template graph was not created",
                    {"graph_name": safe_graph, "template_path": str(path)},
                )
            actual_plot_count = int(layer.DataPlots.Count)
            if actual_plot_count != len(normalized_ranges):
                return OperationResult(
                    False,
                    "Origin template graph plot count does not match the explicit XY ranges",
                    {
                        "graph_name": safe_graph,
                        "template_path": str(path),
                        "expected_plot_count": len(normalized_ranges),
                        "actual_plot_count": actual_plot_count,
                    },
                )

        if group_plots and not requested_group_layers:
            if uses_explicit_layers:
                requested_group_layers.update(
                    layer_index
                    for layer_index, expected_count in expected_by_layer.items()
                    if expected_count > 1
                )
            else:
                requested_group_layers.add(1)

        available_layer_counts = (
            expected_by_layer
            if uses_explicit_layers
            else {1: len(normalized_ranges)}
        )
        for layer_index in sorted(requested_group_layers):
            expected_count = available_layer_counts.get(layer_index, 0)
            if expected_count < 2:
                return OperationResult(
                    False,
                    "Origin template plot grouping requires at least two plots in the requested layer",
                    {
                        "graph_name": safe_graph,
                        "template_path": str(path),
                        "layer_index": layer_index,
                        "plot_count": expected_count,
                    },
                )
            grouped = self.run_labtalk(
                f'win -a "{quote_labtalk(safe_graph)}"; '
                f"layer -s {layer_index}; layer -g;"
            )
            if not grouped.ok:
                return OperationResult(
                    False,
                    "Origin template graph plots could not be grouped",
                    {
                        "graph_name": safe_graph,
                        "template_path": str(path),
                        "layer_index": layer_index,
                    },
                )

        plot_format_readback: list[dict[str, object]] = []
        for contract in normalized_plot_formats:
            layer_index = int(contract["layer_index"])
            plot_index = int(contract["plot_index"])
            layer = self._graph_layer(safe_graph, layer_index)
            if layer is None or plot_index > int(layer.DataPlots.Count):
                return OperationResult(
                    False,
                    "Origin native plot-format target does not exist",
                    {
                        "graph_name": safe_graph,
                        "layer_index": layer_index,
                        "plot_index": plot_index,
                    },
                )
            plot_name = str(layer.DataPlots.Item(plot_index - 1).Name)
            expected = {
                key: float(value)
                for key, value in contract.items()
                if key in plot_format_option_map
            }
            activated_format_layer = self.run_labtalk(
                f'win -a "{quote_labtalk(safe_graph)}"; layer -s {layer_index};'
            )
            if not activated_format_layer.ok:
                return OperationResult(
                    False,
                    "Origin native plot-format target layer could not be activated",
                    {
                        "graph_name": safe_graph,
                        "layer_index": layer_index,
                        "plot_index": plot_index,
                    },
                )
            commands = " ".join(
                f"set {plot_name} -{plot_format_option_map[key]} {value:.17g};"
                for key, value in expected.items()
            )
            applied = self.run_labtalk(commands)
            if not applied.ok:
                return OperationResult(
                    False,
                    "Origin native plot-format properties could not be applied",
                    {
                        "graph_name": safe_graph,
                        "layer_index": layer_index,
                        "plot_index": plot_index,
                        "plot_name": plot_name,
                    },
                )
            actual: dict[str, float] = {}
            for key, expected_value in expected.items():
                option = plot_format_option_map[key]
                variable = f"__rdop_plotfmt_{layer_index}_{plot_index}_{option}"
                queried = self.run_labtalk(
                    f"get {plot_name} -{option} {variable};"
                )
                if not queried.ok:
                    return OperationResult(
                        False,
                        "Origin native plot-format readback failed",
                        {
                            "graph_name": safe_graph,
                            "layer_index": layer_index,
                            "plot_index": plot_index,
                            "property": key,
                        },
                    )
                try:
                    actual_value = float(
                        self.get_labtalk_variable(variable).payload.get("value")
                    )
                except (TypeError, ValueError, OverflowError):
                    return OperationResult(
                        False,
                        "Origin native plot-format readback was nonnumeric",
                        {
                            "graph_name": safe_graph,
                            "layer_index": layer_index,
                            "plot_index": plot_index,
                            "property": key,
                        },
                    )
                if not math.isclose(
                    actual_value,
                    expected_value,
                    rel_tol=1e-12,
                    abs_tol=1e-9,
                ):
                    return OperationResult(
                        False,
                        "Origin native plot-format readback did not match the contract: "
                        f"layer {layer_index}, plot {plot_index}, {key}, "
                        f"expected {expected_value:.17g}, actual {actual_value:.17g}",
                        {
                            "graph_name": safe_graph,
                            "layer_index": layer_index,
                            "plot_index": plot_index,
                            "property": key,
                            "expected": expected_value,
                            "actual": actual_value,
                        },
                    )
                actual[key] = actual_value
            plot_format_readback.append(
                {
                    "layer_index": layer_index,
                    "plot_index": plot_index,
                    "plot_name": plot_name,
                    **actual,
                }
            )

        stack_offsets_by_layer: dict[int, list[dict[str, float | int]]] = {}
        for contract in normalized_stack_offsets:
            stack_offsets_by_layer.setdefault(int(contract["layer_index"]), []).append(
                contract
            )
        stack_readback: list[dict[str, object]] = []
        for layer_index, contracts in sorted(stack_offsets_by_layer.items()):
            layer = self._graph_layer(safe_graph, layer_index)
            if layer is None:
                return OperationResult(
                    False,
                    "Origin individual stack-offset target layer was not created",
                    {"graph_name": safe_graph, "layer_index": layer_index},
                )
            x_enabled = any(
                float(contract["x_offset"]) != 0.0
                or float(contract["x_multiplier"]) != 1.0
                for contract in contracts
            )
            y_enabled = any(
                float(contract["y_offset"]) != 0.0
                or float(contract["y_multiplier"]) != 1.0
                for contract in contracts
            )
            configured = self.run_labtalk(
                f'win -a "{quote_labtalk(safe_graph)}"; '
                f"layer -s {layer_index}; "
                f"layer -b s 4 {1 if x_enabled else 0} {1 if y_enabled else 0};"
            )
            if not configured.ok:
                return OperationResult(
                    False,
                    "Origin individual stack-offset mode could not be enabled",
                    {"graph_name": safe_graph, "layer_index": layer_index},
                )
            for contract in sorted(contracts, key=lambda item: int(item["plot_index"])):
                plot_index = int(contract["plot_index"])
                if plot_index > int(layer.DataPlots.Count):
                    return OperationResult(
                        False,
                        "Origin individual stack-offset plot index is out of range",
                        {
                            "graph_name": safe_graph,
                            "layer_index": layer_index,
                            "plot_index": plot_index,
                        },
                    )
                plot_name = str(layer.DataPlots.Item(plot_index - 1).Name)
                expected = {
                    "sx": float(contract["x_offset"]),
                    "sy": float(contract["y_offset"]),
                    "sxs": float(contract["x_multiplier"]),
                    "sys": float(contract["y_multiplier"]),
                }
                enabled_options = (
                    ({"sx", "sxs"} if x_enabled else set())
                    | ({"sy", "sys"} if y_enabled else set())
                )
                commands = " ".join(
                    f"set {plot_name} -{option} {value:.17g};"
                    for option, value in expected.items()
                    if option in enabled_options
                )
                applied = self.run_labtalk(commands) if commands else OperationResult(
                    True,
                    "No enabled stack-offset dimension required a write",
                )
                if not applied.ok:
                    return OperationResult(
                        False,
                        "Origin individual stack-offset values could not be applied",
                        {
                            "graph_name": safe_graph,
                            "layer_index": layer_index,
                            "plot_index": plot_index,
                            "plot_name": plot_name,
                        },
                    )
                actual: dict[str, float] = {}
                for option, expected_value in expected.items():
                    variable = f"__rdop_stack_{layer_index}_{plot_index}_{option}"
                    queried = self.run_labtalk(
                        f"get {plot_name} -{option} {variable};"
                    )
                    if not queried.ok:
                        return OperationResult(
                            False,
                            "Origin individual stack-offset readback failed",
                            {
                                "graph_name": safe_graph,
                                "layer_index": layer_index,
                                "plot_index": plot_index,
                                "option": option,
                            },
                        )
                    try:
                        actual_value = float(
                            self.get_labtalk_variable(variable).payload.get("value")
                        )
                    except (TypeError, ValueError, OverflowError):
                        return OperationResult(
                            False,
                            "Origin individual stack-offset readback was nonnumeric",
                            {
                                "graph_name": safe_graph,
                                "layer_index": layer_index,
                                "plot_index": plot_index,
                                "option": option,
                            },
                        )
                    if not math.isclose(
                        actual_value,
                        expected_value,
                        rel_tol=1e-12,
                        abs_tol=1e-9,
                    ):
                        return OperationResult(
                            False,
                            "Origin individual stack-offset readback did not match the contract",
                            {
                                "graph_name": safe_graph,
                                "layer_index": layer_index,
                                "plot_index": plot_index,
                                "option": option,
                                "expected": expected_value,
                                "actual": actual_value,
                            },
                        )
                    actual[option] = actual_value
                stack_readback.append(
                    {
                        "layer_index": layer_index,
                        "plot_index": plot_index,
                        "plot_name": plot_name,
                        **actual,
                    }
                )
        axis_scale_readback: dict[int, dict[str, float]] = {}
        for layer_index, scale in sorted(template_axis_scales.items()):
            # Linked overlay layers derive their scales from their parent.
            # Restoring an inherited scale directly can break the link; only
            # restore independent layers whose native range was changed by
            # plot insertion or Individual Stack mode.
            if int(round(scale["link"])) != 0:
                continue
            restored = self.run_labtalk(
                f'win -a "{quote_labtalk(safe_graph)}"; layer -s {layer_index}; '
                f'layer.x.from={scale["x_from"]:.17g}; '
                f'layer.x.to={scale["x_to"]:.17g}; '
                f'layer.y.from={scale["y_from"]:.17g}; '
                f'layer.y.to={scale["y_to"]:.17g};'
            )
            if not restored.ok:
                return OperationResult(
                    False,
                    "Origin template axis scales could not be restored after plotting",
                    {"graph_name": safe_graph, "layer_index": layer_index},
                )
            variables = {
                "x_from": f"rr{layer_index}xf",
                "x_to": f"rr{layer_index}xt",
                "y_from": f"rr{layer_index}yf",
                "y_to": f"rr{layer_index}yt",
            }
            queried = self.run_labtalk(
                " ".join(
                    [
                        f'{variables["x_from"]}=layer.x.from;',
                        f'{variables["x_to"]}=layer.x.to;',
                        f'{variables["y_from"]}=layer.y.from;',
                        f'{variables["y_to"]}=layer.y.to;',
                    ]
                )
            )
            if not queried.ok:
                return OperationResult(
                    False,
                    "Origin restored axis scale readback failed",
                    {"graph_name": safe_graph, "layer_index": layer_index},
                )
            actual_scale: dict[str, float] = {}
            for key, variable in variables.items():
                actual_value = float(
                    self.get_labtalk_variable(variable).payload.get("value")
                )
                if not math.isclose(
                    actual_value,
                    scale[key],
                    rel_tol=1e-12,
                    abs_tol=1e-9,
                ):
                    return OperationResult(
                        False,
                        "Origin restored axis scale did not match the template: "
                        f"layer {layer_index}, {key}, expected {scale[key]:.17g}, "
                        f"actual {actual_value:.17g}",
                        {
                            "graph_name": safe_graph,
                            "layer_index": layer_index,
                            "property": key,
                            "expected": scale[key],
                            "actual": actual_value,
                        },
                    )
                actual_scale[key] = actual_value
            axis_scale_readback[layer_index] = actual_scale
        return OperationResult(
            True,
            "Graph created from absolute template with explicit X/Y ranges",
            {
                "graph_name": safe_graph,
                "template_path": str(path),
                "plot_type": plot_type,
                "group_plots": bool(group_plots),
                "group_layer_indices": sorted(requested_group_layers),
                "individual_stack_offsets": normalized_stack_offsets,
                "individual_stack_readback": stack_readback,
                "plot_format_contracts": normalized_plot_formats,
                "plot_format_readback": plot_format_readback,
                "template_axis_scales": template_axis_scales,
                "axis_scale_readback": axis_scale_readback,
                "xy_ranges": normalized_ranges,
                "plot_count": actual_plot_count,
            },
        )

    def get_worksheet_column_metadata(
        self,
        book_name: str,
        column_indices: Iterable[int],
        *,
        sheet_index: int = 1,
    ) -> OperationResult:
        """Read Origin column labels and designations through LabTalk variables."""

        book = str(book_name).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", book):
            return OperationResult(False, "Worksheet book has an unsafe internal name")
        try:
            sheet = int(sheet_index)
        except (TypeError, ValueError):
            return OperationResult(False, "Worksheet index is not numeric")
        if sheet < 1:
            return OperationResult(False, "Worksheet index must be one-based and positive")
        activated = self.run_labtalk(
            f'win -a "{quote_labtalk(book)}"; layer -s {sheet};'
        )
        if not activated.ok:
            return OperationResult(
                False,
                f"Could not activate worksheet book/sheet: {book}/{sheet}",
            )
        metadata: list[dict[str, object]] = []
        for raw_index in column_indices:
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                return OperationResult(False, "Worksheet column index is not numeric")
            if index < 1:
                return OperationResult(False, "Worksheet column index must be one-based and positive")
            script = (
                f'string __rdop_col_lname$=wks.col{index}.lname$; '
                f'string __rdop_col_unit$=wks.col{index}.unit$; '
                f'string __rdop_col_comment$=wks.col{index}.comment$; '
                f'__rdop_col_type=wks.col{index}.type;'
            )
            read = self.run_labtalk(script)
            if not read.ok:
                return OperationResult(False, f"Could not read worksheet column metadata: {book} col {index}")
            try:
                column_type = int(round(float(self.app.LTVar("__rdop_col_type"))))
            except (TypeError, ValueError, OverflowError):
                return OperationResult(False, f"Worksheet column type readback failed: {book} col {index}")
            metadata.append(
                {
                    "column_index": index,
                    "long_name": str(self.app.LTStr("__rdop_col_lname$") or ""),
                    "unit": str(self.app.LTStr("__rdop_col_unit$") or ""),
                    "comment": str(self.app.LTStr("__rdop_col_comment$") or ""),
                    "type": column_type,
                }
            )
        if not metadata:
            return OperationResult(False, "No worksheet column indices were provided")
        return OperationResult(
            True,
            "Worksheet column metadata read",
            {"book_name": book, "sheet_index": sheet, "columns": metadata},
        )

    def set_worksheet_column_metadata(
        self,
        book_name: str,
        columns: Iterable[dict[str, object]],
        *,
        sheet_index: int = 1,
    ) -> OperationResult:
        """Write labels while preserving Origin rich-text backslashes."""

        book = str(book_name).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", book):
            return OperationResult(False, "Worksheet book has an unsafe internal name")
        try:
            sheet = int(sheet_index)
        except (TypeError, ValueError):
            return OperationResult(False, "Worksheet index is not numeric")
        if sheet < 1:
            return OperationResult(False, "Worksheet index must be one-based and positive")
        activated = self.run_labtalk(
            f'win -a "{quote_labtalk(book)}"; layer -s {sheet};'
        )
        if not activated.ok:
            return OperationResult(
                False,
                f"Could not activate worksheet book/sheet: {book}/{sheet}",
            )
        updated: list[int] = []
        for raw in columns:
            if not isinstance(raw, dict):
                return OperationResult(False, "Every worksheet metadata record must be an object")
            try:
                index = int(raw.get("column_index"))
                column_type = int(raw.get("type"))
            except (TypeError, ValueError):
                return OperationResult(False, "Worksheet metadata has invalid column/type values")
            if index < 1 or column_type not in {1, 2, 3, 4, 5, 6, 7}:
                return OperationResult(False, "Worksheet metadata has unsupported column/type values")
            long_name = quote_origin_markup(raw.get("long_name", ""))
            unit = quote_origin_markup(raw.get("unit", ""))
            comment = quote_origin_markup(raw.get("comment", ""))
            written = self.run_labtalk(
                f'wks.col{index}.lname$="{long_name}"; '
                f'wks.col{index}.unit$="{unit}"; '
                f'wks.col{index}.comment$="{comment}"; '
                f'wks.col{index}.type={column_type};'
            )
            if not written.ok:
                return OperationResult(False, f"Could not write worksheet column metadata: {book} col {index}")
            updated.append(index)
        if not updated:
            return OperationResult(False, "No worksheet column metadata was provided")
        return OperationResult(
            True,
            "Worksheet column metadata written",
            {"book_name": book, "sheet_index": sheet, "column_indices": updated},
        )

    def save_graph_theme(
        self,
        graph_name: str,
        file_path: str | Path,
        timeout_seconds: float = 8.0,
    ) -> OperationResult:
        output_path = Path(file_path)
        if output_path.suffix.casefold() != ".oth":
            output_path = output_path.with_suffix(".oth")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
        graph = quote_labtalk(graph_name)
        self.run_labtalk(f'win -a "{graph}";')
        loaded = self.run_labtalk("run.section(,PrepareCopyFormats);")
        if not loaded.ok:
            return OperationResult(False, "Origin built-in Copy Format loader failed", {"graph_name": graph_name})
        self.run_labtalk("__rdop_theme_copy_ok=0;")
        ok = self.run_labtalk("run -oc {__rdop_theme_copy_ok=CopyFormat()};")
        copied = bool(getattr(self.app, "LTVar", lambda _name: 0)("__rdop_theme_copy_ok"))
        if not ok.ok:
            return OperationResult(False, f"Origin Copy Format command failed for {graph_name}", {"file_path": str(output_path)})
        if not copied:
            return OperationResult(False, f"Origin Copy Format did not produce a graph style for {graph_name}")
        theme_bytes = _read_origin_xml_style_clipboard(timeout_seconds)
        if not theme_bytes:
            return OperationResult(
                False,
                f"Origin clipboard did not contain {ORIGIN_XML_STYLE_CLIPBOARD_FORMAT!r}",
                {"graph_name": graph_name, "file_path": str(output_path)},
            )
        output_path.write_bytes(theme_bytes)
        if not _wait_for_file(output_path, timeout_seconds):
            return OperationResult(False, f"No graph theme produced at {output_path}", {"file_path": str(output_path)})
        return OperationResult(True, "Graph theme saved", {"graph_name": graph_name, "file_path": str(output_path)})

    def apply_graph_theme(self, graph_name: str, theme_path: str | Path) -> OperationResult:
        path = Path(theme_path)
        if not path.is_file():
            return OperationResult(False, f"Graph theme file not found: {path}")
        graph = quote_labtalk(graph_name)
        source = quote_labtalk(to_origin_path(path))
        self.run_labtalk(f'win -a "{graph}";')
        loaded = self.run_labtalk("run.section(,PrepareCopyFormats);")
        if not loaded.ok:
            return OperationResult(False, "Origin built-in graph theme loader failed", {"graph_name": graph_name})
        self.run_labtalk("__rdop_theme_apply_ok=0;")
        ok = self.run_labtalk(
            f'run -oc {{__rdop_theme_apply_ok=theme_apply_graph_options("{source}", {THEME_APPLY_PAGE}, 0)}};'
        )
        applied = bool(getattr(self.app, "LTVar", lambda _name: 0)("__rdop_theme_apply_ok"))
        if not ok.ok or not applied:
            return OperationResult(
                False,
                f"Origin graph theme apply failed for {graph_name}",
                {"graph_name": graph_name, "theme_path": str(path)},
            )
        return OperationResult(True, "Graph theme applied", {"graph_name": graph_name, "theme_path": str(path)})

    def add_plot_to_graph(
        self,
        graph_name: str,
        data_book: str,
        data_sheet: str,
        x_col: int,
        y_col: int,
        plot_type: str = "line",
        y_error_col: int = 0,
        row_from: int = 0,
        row_to: int = 0,
    ) -> OperationResult:
        ptype = PLOT_TYPES.get(plot_type)
        if ptype is None:
            return OperationResult(False, f"Unsupported plot type: {plot_type}")
        data_ref = _plotxy_data_reference(
            data_book,
            data_sheet,
            x_col,
            y_col,
            y_error_col=y_error_col,
            row_from=row_from,
            row_to=row_to,
        )
        self.run_labtalk(f"plotxy iy:={data_ref} plot:={ptype} ogl:=[{graph_name}]Layer1;")
        return OperationResult(True, "Plot added", {"graph_name": graph_name, "plot_type": plot_type})

    def set_axis_labels(self, graph_name: str, x_label: str = "", y_label: str = "", title: str = "") -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        if x_label:
            self.run_labtalk(f'xb.text$ = "{quote_origin_text(x_label)}";')
        if y_label:
            self.run_labtalk(f'yl.text$ = "{quote_origin_text(y_label)}";')
        if title:
            self.run_labtalk(f'label -n title -s "{quote_origin_text(title)}"; title.x = 50; title.y = 95;')
        return OperationResult(True, "Axis labels updated", {"graph_name": graph_name})

    def set_axis_range(
        self,
        graph_name: str,
        x_min: float | None = None,
        x_max: float | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
    ) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        commands = []
        if x_min is not None:
            commands.append(f"layer.x.from = {x_min};")
        if x_max is not None:
            commands.append(f"layer.x.to = {x_max};")
        if y_min is not None:
            commands.append(f"layer.y.from = {y_min};")
        if y_max is not None:
            commands.append(f"layer.y.to = {y_max};")
        if commands:
            self.run_labtalk(" ".join(commands))
        return OperationResult(True, "Axis range updated", {"graph_name": graph_name})

    def export_graph(
        self,
        graph_name: str,
        file_path: str | Path,
        export_format: str = "tif",
        dpi: int = 600,
        timeout_seconds: float = 8.0,
        pixel_width: int | None = None,
    ) -> OperationResult:
        try:
            output_path, resolved_format = normalize_export_path(file_path, export_format)
        except ValueError as exc:
            return OperationResult(False, str(exc))
        if (
            isinstance(dpi, bool)
            or not isinstance(dpi, Integral)
            or not MIN_EXPORT_DPI <= int(dpi) <= MAX_EXPORT_DPI
        ):
            return OperationResult(
                False,
                f"Export DPI must be an integer between {MIN_EXPORT_DPI} and {MAX_EXPORT_DPI}, got {dpi!r}",
            )
        resolved_dpi = int(dpi)
        if pixel_width is not None and (
            isinstance(pixel_width, bool)
            or not isinstance(pixel_width, Integral)
            or int(pixel_width) <= 0
        ):
            return OperationResult(
                False,
                f"Export pixel width must be a positive integer, got {pixel_width!r}",
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        folder = quote_labtalk(to_origin_path(output_path.parent))
        filename = quote_labtalk(output_path.stem)
        graph = quote_labtalk(graph_name)
        activated = self.run_labtalk(f'win -a "{graph}";')
        if not activated.ok:
            return OperationResult(
                False,
                f"Origin graph page does not exist or could not be activated: {graph_name}",
                {"graph_name": graph_name},
            )
        if output_path.exists():
            output_path.unlink()
        raster_dpi_setting = (
            (
                " sysopts:=0"
                " tr.Margin:=2"
                + (
                    f" tr1.Unit:=2 tr1.Width:={int(pixel_width)}"
                    if pixel_width is not None
                    else ""
                )
                + f" tr2.{resolved_format.upper()}.dotsperinch:={resolved_dpi}"
            )
            if resolved_format in RASTER_EXPORT_FORMATS
            else ""
        )
        ok = self.run_labtalk(
            f'expGraph type:={resolved_format} path:="{folder}" filename:="{filename}" '
            f"overwrite:=replace{raster_dpi_setting};"
        )
        if not ok.ok:
            return OperationResult(False, f"Origin expGraph failed for {graph_name}")
        if not _wait_for_file(output_path, timeout_seconds):
            return OperationResult(False, f"No exported file produced at {output_path}", {"file_path": str(output_path)})
        return OperationResult(True, "Graph exported", {"graph_name": graph_name, "file_path": str(output_path)})

    def save_graph_template(
        self,
        graph_name: str,
        file_path: str | Path,
        timeout_seconds: float = 8.0,
    ) -> OperationResult:
        output_path = Path(file_path)
        if output_path.suffix.casefold() != ".otpu":
            output_path = output_path.with_suffix(".otpu")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
        graph = quote_labtalk(graph_name)
        template_name = quote_labtalk(output_path.stem)
        output_folder = quote_labtalk(to_origin_path(output_path.parent.resolve()))
        self.run_labtalk(f'win -a "{graph}";')
        ok = self.run_labtalk(
            f'template_saveas pg:={graph} category:="ResearchDataOrigin" '
            f'template:="{template_name}" filepath:="{output_folder}" '
            'emf:=0 bmp:=0 loadsys:=0;'
        )
        if not ok.ok:
            return OperationResult(False, f"Origin template_saveas failed for {graph_name}", {"file_path": str(output_path)})
        if not _wait_for_file(output_path, timeout_seconds):
            return OperationResult(False, f"No graph template produced at {output_path}", {"file_path": str(output_path)})
        return OperationResult(True, "Graph template saved", {"graph_name": graph_name, "file_path": str(output_path)})

    def export_all_graphs(self, output_dir: str | Path, export_format: str = "tif", dpi: int = 600) -> OperationResult:
        pages = self.list_worksheets()
        graph_pages = [item["name"] for item in pages.payload.get("pages", []) if item.get("type") == "graph"]
        exported = []
        failures = []
        for graph_name in graph_pages:
            result = self.export_graph(str(graph_name), Path(output_dir) / f"{graph_name}.{export_format}", export_format, dpi)
            if result.ok:
                exported.append(result.payload["file_path"])
            else:
                failures.append({"graph_name": graph_name, "message": result.message})
        return OperationResult(
            not failures,
            "All graphs exported" if not failures else "Some graph exports failed",
            {"exported": exported, "failures": failures},
        )

    def replace_legend_with_plain_text_labels(
        self,
        graph_name: str,
        entries: Iterable[str],
        font_name: str = "Arial",
        font_size: int = 26,
        max_entries: int = 12,
        prefer_existing_text: bool = False,
    ) -> OperationResult:
        labels = [_legend_entry_text(entry) for entry in entries]
        labels = [label for label in labels if label][: max(0, int(max_entries))]
        graph = quote_labtalk(graph_name)
        layer = self.app.FindGraphLayer(f"[{graph_name}]Layer1")
        if not layer:
            return OperationResult(False, f"Graph layer not found: [{graph_name}]Layer1")
        try:
            self.run_labtalk(f'win -a "{graph}";')
            objects = _graph_object_infos(layer)
            legend = _find_legend_info(objects)
            if prefer_existing_text:
                existing_labels = _existing_plain_legend_labels(objects, legend)
                if existing_labels:
                    labels = existing_labels[: max(0, int(max_entries))]
            text_objects = _plain_legend_text_objects(objects, legend)
            data_anchor = _plain_legend_data_anchor(self) if legend else None
            base_left, base_top = _plain_legend_anchor(objects, legend)
            row_step = max(220, int(font_size) * 10)
            delete_names = _plain_legend_delete_names(objects, legend)
            self.run_labtalk(f'win -a "{graph}"; legend.show=0;')
            for name in delete_names:
                self.run_labtalk(f'win -a "{graph}"; label -r {quote_labtalk(name)};')
            layer = self.app.FindGraphLayer(f"[{graph_name}]Layer1")
            created_labels = _write_plain_legend_labels(
                self,
                layer,
                graph,
                labels,
                text_objects,
                data_anchor=data_anchor,
                fallback_left=base_left,
                fallback_top=base_top,
                row_step=row_step,
                font_name=font_name,
                font_size=int(font_size),
            )
        except Exception as exc:
            return OperationResult(False, f"Plain-text legend replacement failed: {exc}")
        return OperationResult(
            True,
            "Legend line samples replaced by plain text labels",
            {
                "graph_name": graph_name,
                "deleted_objects": delete_names,
                "created_labels": created_labels,
                "anchor_left": base_left,
                "anchor_top": base_top,
                "anchor_data": {"x": data_anchor[0], "y": data_anchor[1]} if data_anchor else {},
                "font_name": font_name,
                "font_size": int(font_size),
                "text_source": "existing_legend" if prefer_existing_text else "entries",
            },
        )

    def _plot_names(self, graph_name: str) -> list[str]:
        names: list[str] = []
        for layer_index in range(1, self._graph_layer_count(graph_name) + 1):
            layer = self._graph_layer(graph_name, layer_index)
            if not layer:
                if names:
                    break
                continue
            data_plots = layer.DataPlots
            names.extend(str(data_plots.Item(index).Name) for index in range(data_plots.Count))
        return names

    def _graph_layer_count(self, graph_name: str) -> int:
        try:
            self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; __rdop_page_nlayers=page.nlayers;')
            count = int(float(self.app.LTVar("__rdop_page_nlayers")))
        except Exception:
            count = 1
        if count <= 0:
            return 1
        return min(count, 24)

    def set_plot_style(
        self,
        graph_name: str,
        plot_index: int = 1,
        line_width: float = 1.5,
        symbol_size: int = 8,
        symbol_shape: int = 0,
        color: str = "",
    ) -> OperationResult:
        plot_names = self._plot_names(graph_name)
        index = plot_index - 1
        if index < 0 or index >= len(plot_names):
            return OperationResult(False, f"Plot index {plot_index} not found", {"available_plots": plot_names})
        plot_name = plot_names[index]
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        if color:
            color_code = COLOR_MAP.get(color.lower())
            if color_code is None:
                return OperationResult(False, f"Unsupported color: {color}")
            self.run_labtalk(f"set {plot_name} -c {color_code};")
        self.run_labtalk(f"set {plot_name} -wp {float(line_width):g};")
        self.run_labtalk(f"set {plot_name} -k {symbol_shape or SYMBOL_SHAPES.get(plot_index, 2)};")
        self.run_labtalk(f"set {plot_name} -z {symbol_size};")
        self.run_labtalk(f"set {plot_name} -l 1;")
        return OperationResult(True, "Plot style updated", {"plot_name": plot_name})

    def set_graph_font(
        self,
        graph_name: str,
        font_name: str = "Arial",
        axis_title_size: int = 36,
        target: str = "all",
        x_tick_label_size: int = 28,
        y_tick_label_size: int = 36,
        legend_font_size: int = 26,
        annotation_font_size: int = 26,
    ) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        if target in {"all", "axes"}:
            self.run_labtalk(f'xb.font$ = "{quote_labtalk(font_name)}"; xb.fsize = {axis_title_size}; xb.bold = 1;')
            self.run_labtalk(f'yl.font$ = "{quote_labtalk(font_name)}"; yl.fsize = {axis_title_size}; yl.bold = 1;')
        if target in {"all", "tick"}:
            self.run_labtalk(f"layer.x.label.pt = {x_tick_label_size}; layer.y.label.pt = {y_tick_label_size};")
            self.run_labtalk("layer.x.label.bold = 1; layer.y.label.bold = 1;")
        if target in {"all", "legend"}:
            self.run_labtalk(
                f'legend.font$ = "{quote_labtalk(font_name)}"; '
                f"legend.font = font({quote_labtalk(font_name)}); "
                f"legend.fsize = {legend_font_size}; "
                "legend.bold = 1; legend.color = color(black);"
            )
            self._disable_legend_box()
        if target in {"all", "annotation"}:
            self.run_labtalk(f'doc -e O {{if(object.type==4) {{object.font$="{quote_labtalk(font_name)}"; object.fsize={annotation_font_size}; object.bold=1;}}}}')
        if target == "title":
            self.run_labtalk(f'title.font$ = "{quote_labtalk(font_name)}"; title.fsize = {axis_title_size}; title.bold = 1;')
        return OperationResult(True, "Graph font updated", {"graph_name": graph_name, "target": target})

    def set_y_tick_values_visible(self, graph_name: str, visible: bool) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        value = 1 if visible else 0
        self.run_labtalk(f"layer.y.label.show = {value}; layer.y.showLabels = {value};")
        return OperationResult(True, "Y tick value visibility updated", {"graph_name": graph_name, "visible": visible})

    def set_axis_and_tick_visibility(
        self,
        graph_name: str,
        y_axis: bool = True,
        y_ticks: bool = True,
        y_tick_values: bool = True,
        x_tick_values: bool = True,
    ) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        self.run_labtalk(f"layer.y.show = {1 if y_axis else 0};")
        self.run_labtalk(f"layer.y.ticks = {1 if y_ticks else 0};")
        y_label_value = 1 if y_tick_values else 0
        x_label_value = 1 if x_tick_values else 0
        self.run_labtalk(f"layer.y.label.show = {y_label_value}; layer.y.showLabels = {y_label_value};")
        self.run_labtalk(f"layer.x.label.show = {x_label_value}; layer.x.showLabels = {x_label_value};")
        return OperationResult(
            True,
            "Axis and tick visibility updated",
            {
                "graph_name": graph_name,
                "y_axis": y_axis,
                "y_ticks": y_ticks,
                "y_tick_values": y_tick_values,
                "x_tick_values": x_tick_values,
            },
        )

    def apply_graph4_fixed_style(self, graph_name: str, style_policy: Graph4FixedStyle = GRAPH4_FIXED_STYLE) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        self.run_labtalk(
            "page.kar=0; "
            f"page.width={style_policy.page_width}; page.height={style_policy.page_height}; "
            "page.customwidth=1; page.customheight=1;"
        )
        self.run_labtalk(
            f"layer.left={style_policy.layer_left}; layer.top={style_policy.layer_top}; "
            f"layer.width={style_policy.layer_width}; layer.height={style_policy.layer_height};"
        )
        self.run_labtalk(
            f"layer.x.thickness = {style_policy.axis_line_width}; "
            f"layer.y.thickness = {style_policy.axis_line_width};"
        )
        self.set_graph_font(
            graph_name,
            style_policy.font_family,
            axis_title_size=style_policy.axis_title_size,
            x_tick_label_size=style_policy.x_tick_label_size,
            y_tick_label_size=style_policy.y_tick_label_size,
            legend_font_size=style_policy.legend_font_size,
            annotation_font_size=style_policy.annotation_font_size,
        )
        self._disable_legend_box()
        self.run_labtalk(f"doc -e DY {{set %C -lw {style_policy.line_width};}}")
        return OperationResult(True, "Graph4 fixed style applied", {"graph_name": graph_name})

    def set_legend(
        self,
        graph_name: str,
        visible: bool = True,
        position: str = "top-right",
        entries: Iterable[str] | None = None,
    ) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        if not visible:
            self.run_labtalk("legend.show = 0;")
            return OperationResult(True, "Legend hidden", {"graph_name": graph_name})
        self.run_labtalk("legend -r;")
        if entries:
            legend_text = _legend_text_from_entries(list(entries))
            if legend_text:
                self.run_labtalk(f"legend.text$ = {legend_text};")
        self.run_labtalk("legend.bold = 1; legend.color = color(black);")
        self._disable_legend_box()
        fractions = {
            "top-left": (0.05, 0.85),
            "top-right": (0.65, 0.85),
            "bottom-left": (0.05, 0.15),
            "bottom-right": (0.65, 0.15),
        }
        if position in fractions:
            x_fraction, y_fraction = fractions[position]
            self.run_labtalk(
                f"legend.x = layer.x.from + {x_fraction} * (layer.x.to - layer.x.from); "
                f"legend.y = layer.y.from + {y_fraction} * (layer.y.to - layer.y.from);"
            )
        return OperationResult(True, "Legend updated", {"graph_name": graph_name, "position": position})

    def set_tick_style(
        self,
        graph_name: str,
        tick_direction: str = "in",
        major_length: int = 8,
        minor_count: int = 4,
        show_minor: bool = True,
    ) -> OperationResult:
        direction = {"in": 1, "out": 2, "both": 3}.get(tick_direction, 1)
        minor = minor_count if show_minor else 0
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        self.run_labtalk(
            f"layer.x.ticks = {direction}; layer.y.ticks = {direction}; "
            f"layer.x.minor = {minor}; layer.y.minor = {minor}; "
            f"layer.x.majorLen = {major_length}; layer.y.majorLen = {major_length};"
        )
        return OperationResult(True, "Tick style updated", {"graph_name": graph_name})

    def apply_publication_style(
        self,
        graph_name: str,
        x_label: str = "",
        y_label: str = "",
        x_min: float | None = None,
        x_max: float | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
        legend_entries: Iterable[str] | None = None,
        legend_position: str = "top-right",
        font_name: str = "Arial",
        axis_title_size: int = 36,
        line_width: float = 3.0,
        x_tick_label_size: int = 28,
        y_tick_label_size: int = 36,
        legend_font_size: int = 26,
        annotation_font_size: int = 26,
        axis_line_width: int = 3,
    ) -> OperationResult:
        self.set_axis_labels(graph_name, x_label, y_label)
        self.set_axis_range(graph_name, x_min, x_max, y_min, y_max)
        self.set_graph_font(
            graph_name,
            font_name,
            axis_title_size,
            "all",
            x_tick_label_size,
            y_tick_label_size,
            legend_font_size,
            annotation_font_size,
        )
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        self.run_labtalk(f"layer.x.thickness = {axis_line_width}; layer.y.thickness = {axis_line_width};")
        self.set_tick_style(graph_name)
        self.set_legend(graph_name, True, legend_position, legend_entries)
        self._disable_legend_box()
        for index, color in enumerate(("blue", "red", "green", "orange", "purple", "cyan"), start=1):
            result = self.set_plot_style(graph_name, index, line_width=line_width, color=color)
            if not result.ok and index == 1:
                break
        return OperationResult(True, "Publication-style operation bundle applied", {"graph_name": graph_name})

    def _disable_legend_box(self) -> None:
        self.run_labtalk(
            "legend.background = 0; legend.border = 0; legend.frame = 0; legend.fill = 0; "
            "legend.fillColor = 0; legend.borderColor = 0; legend.lineWidth = 0;"
        )


def _legend_text_from_entries(entries: list[str]) -> str:
    lines = []
    for index, entry in enumerate(entries, start=1):
        text = _legend_entry_text(entry)
        if text:
            lines.append(f"\\l({index}) {text}")
    return "\n".join(lines)


def _legend_entry_text(entry: object) -> str:
    text = origin_bold_text(entry)
    return str(text).replace(";", ",").replace("\r", " ").replace("\n", " ").strip()


def _graph_object_infos(layer: object) -> list[dict[str, object]]:
    collection = getattr(layer, "GraphObjects", None)
    if collection is None:
        return []
    try:
        count = int(getattr(collection, "Count", 0))
    except Exception:
        return []
    if count <= 0:
        return []
    base_index = 0
    try:
        collection.Item(0)
    except Exception:
        base_index = 1
    infos: list[dict[str, object]] = []
    for offset in range(count):
        try:
            graph_object = collection.Item(offset + base_index)
        except Exception:
            continue
        name = str(getattr(graph_object, "Name", "") or "")
        if not name:
            continue
        infos.append(
            {
                "name": name,
                "object": graph_object,
                "text": str(getattr(graph_object, "Text", "") or ""),
                "left": _graph_object_float(graph_object, "Left"),
                "top": _graph_object_float(graph_object, "Top"),
                "width": _graph_object_float(graph_object, "Width"),
                "height": _graph_object_float(graph_object, "Height"),
            }
        )
    return infos


def _find_graph_object(layer: object, name: str) -> object | None:
    for info in _graph_object_infos(layer):
        if str(info.get("name", "")).casefold() == name.casefold():
            return info.get("object")
    return None


def _graph_object_float(graph_object: object, attr: str) -> float:
    try:
        return float(getattr(graph_object, attr))
    except Exception:
        return 0.0


def _find_legend_info(objects: list[dict[str, object]]) -> dict[str, object] | None:
    for info in objects:
        if str(info.get("name", "")).casefold() == "legend":
            return info
    return None


def _plain_legend_anchor(
    objects: list[dict[str, object]],
    legend: dict[str, object] | None,
) -> tuple[int, int]:
    if legend:
        text_objects = _plain_legend_text_objects(objects, legend)
        if text_objects:
            left = min(float(info.get("left", 3600.0)) for info in text_objects)
            top = min(float(info.get("top", 650.0)) for info in text_objects)
            return int(round(left)), int(round(top))
        else:
            left = max(0.0, float(legend.get("left", 3600.0)))
            top = float(legend.get("top", 650.0))
        return int(round(left)), int(round(top))
    existing = [info for info in objects if str(info.get("name", "")).casefold().startswith("rdop_plain_legend_")]
    if existing:
        left = min(float(info.get("left", 3600.0)) for info in existing)
        top = min(float(info.get("top", 650.0)) for info in existing)
        return int(round(left)), int(round(top))
    return 3600, 650


def _plain_legend_delete_names(
    objects: list[dict[str, object]],
    legend: dict[str, object] | None,
) -> list[str]:
    text_objects = _plain_legend_text_objects(objects, legend)
    text_names = {str(info.get("name", "") or "").casefold() for info in text_objects}
    names: list[str] = []
    for info in objects:
        name = str(info.get("name", "") or "")
        if not name:
            continue
        lowered = name.casefold()
        if lowered == "legend" or lowered.startswith("rdop_plain_legend_"):
            names.append(name)
            continue
        if legend and _is_plain_legend_related_object(info, legend):
            if lowered.startswith("line") or (lowered.startswith("text") and lowered not in text_names):
                names.append(name)
    return names


def _plain_legend_text_objects(
    objects: list[dict[str, object]],
    legend: dict[str, object] | None,
) -> list[dict[str, object]]:
    if legend is None:
        return []
    text_objects = [
        info
        for info in objects
        if str(info.get("name", "")).casefold().startswith("text")
        and _is_plain_legend_related_object(info, legend)
    ]
    text_objects.sort(key=lambda item: (float(item.get("top", 0.0)), float(item.get("left", 0.0))))
    return text_objects


def _plain_legend_data_anchor(operations: "OriginOperations") -> tuple[float, float] | None:
    x_value = _operation_float(operations.get_labtalk_variable("legend.x").payload.get("value"))
    y_value = _operation_float(operations.get_labtalk_variable("legend.y").payload.get("value"))
    if x_value is None or y_value is None:
        return None
    return x_value, y_value


def _operation_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _origin_numeric_or_missing(value: object) -> float:
    """Normalize an Origin worksheet value without dropping missing cells."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return math.nan
    return float(value)


def _write_plain_legend_labels(
    operations: "OriginOperations",
    layer: object | None,
    graph: str,
    labels: list[str],
    text_objects: list[dict[str, object]],
    *,
    data_anchor: tuple[float, float] | None,
    fallback_left: int,
    fallback_top: int,
    row_step: int,
    font_name: str,
    font_size: int,
) -> list[str]:
    if not labels:
        return []
    if text_objects:
        return _write_plain_legend_text_object_rows(
            operations,
            layer,
            graph,
            labels,
            text_objects,
            fallback_left=fallback_left,
            fallback_top=fallback_top,
            row_step=row_step,
            font_name=font_name,
            font_size=font_size,
        )
    return _write_plain_legend_single_block(
        operations,
        layer,
        graph,
        labels,
        data_anchor=data_anchor,
        fallback_left=fallback_left,
        fallback_top=fallback_top,
        font_name=font_name,
        font_size=font_size,
    )


def _write_plain_legend_text_object_rows(
    operations: "OriginOperations",
    layer: object | None,
    graph: str,
    labels: list[str],
    text_objects: list[dict[str, object]],
    *,
    fallback_left: int,
    fallback_top: int,
    row_step: int,
    font_name: str,
    font_size: int,
) -> list[str]:
    created: list[str] = []
    for index, label in enumerate(labels, start=1):
        if index <= len(text_objects):
            name = str(text_objects[index - 1].get("name", "") or f"rdop_plain_legend_{index}")
            label_object = text_objects[index - 1].get("object")
        else:
            name = f"rdop_plain_legend_{index}"
            operations.run_labtalk(f'win -a "{graph}"; label -n {name} -s " ";')
            label_object = _find_graph_object(layer, name) if layer else None
            if label_object is not None:
                label_object.Left = fallback_left
                label_object.Top = fallback_top + row_step * (index - 1)
        if label_object is not None:
            label_object.Text = label
        _style_plain_legend_object(operations, graph, name, font_name, font_size)
        created.append(name)
    for extra in text_objects[len(labels) :]:
        name = str(extra.get("name", "") or "")
        if name:
            operations.run_labtalk(f'win -a "{graph}"; label -r {quote_labtalk(name)};')
    return created


def _write_plain_legend_single_block(
    operations: "OriginOperations",
    layer: object | None,
    graph: str,
    labels: list[str],
    *,
    data_anchor: tuple[float, float] | None,
    fallback_left: int,
    fallback_top: int,
    font_name: str,
    font_size: int,
) -> list[str]:
    name = "rdop_plain_legend"
    operations.run_labtalk(f'win -a "{graph}"; label -n {name} -s " ";')
    label_object = _find_graph_object(layer, name) if layer else None
    if label_object is not None:
        label_object.Text = "\r\n".join(labels)
        if data_anchor is None:
            label_object.Left = fallback_left
            label_object.Top = fallback_top
    if data_anchor is not None:
        x_value, y_value = data_anchor
        operations.run_labtalk(f'win -a "{graph}"; {name}.x={x_value:g}; {name}.y={y_value:g};')
    _style_plain_legend_object(operations, graph, name, font_name, font_size)
    return [name]


def _style_plain_legend_object(
    operations: "OriginOperations",
    graph: str,
    name: str,
    font_name: str,
    font_size: int,
) -> None:
    operations.run_labtalk(
        f'win -a "{graph}"; '
        f'{name}.font$="{quote_labtalk(font_name)}"; '
        f"{name}.fsize={int(font_size)}; "
        f"{name}.bold=1; {name}.color=color(black); "
        f"{name}.background=0; {name}.border=0; {name}.frame=0; {name}.fill=0;"
    )


def _is_plain_legend_related_object(info: dict[str, object], legend: dict[str, object]) -> bool:
    left = float(info.get("left", 0.0))
    top = float(info.get("top", 0.0))
    legend_left = float(legend.get("left", 0.0))
    legend_top = float(legend.get("top", 0.0))
    legend_width = max(float(legend.get("width", 0.0)), 1.0)
    legend_height = max(float(legend.get("height", 0.0)), 1.0)
    return (
        legend_left - 800 <= left <= legend_left + legend_width + 800
        and legend_top - 700 <= top <= legend_top + legend_height + 800
    )


def _existing_plain_legend_labels(
    objects: list[dict[str, object]],
    legend: dict[str, object] | None,
) -> list[str]:
    if legend is None:
        return []
    text_objects = [
        info
        for info in objects
        if str(info.get("name", "")).casefold().startswith("text")
        and _is_plain_legend_related_object(info, legend)
    ]
    text_objects.sort(key=lambda item: (float(item.get("top", 0.0)), float(item.get("left", 0.0))))
    labels: list[str] = []
    for info in text_objects:
        label = _clean_existing_legend_label(str(info.get("text", "") or ""))
        if label:
            labels.append(label)
    labels.extend(_legend_labels_from_text(str(legend.get("text", "") or "")))
    labels = [label for label in labels if label and "%(" not in label]
    return labels


def _legend_labels_from_text(value: str) -> list[str]:
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    labels: list[str] = []
    pattern = re.compile(r"(?:\\|/)l\(\d+\)\s*(.*?)(?=(?:\\|/)l\(\d+\)|$)", re.DOTALL)
    matches = list(pattern.finditer(text))
    if matches:
        for match in matches:
            label = _clean_existing_legend_label(match.group(1))
            if label:
                labels.append(label)
        return labels
    for line in text.split("\n"):
        label = _clean_existing_legend_label(line)
        if label:
            labels.append(label)
    return labels


def _clean_existing_legend_label(value: str) -> str:
    text = value.replace("/", "\\").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"^\\l\(\d+\)\s*", "", text).strip()
    text = text.strip(" /	")
    if not text:
        return ""
    if text.startswith("\\b("):
        return text
    return origin_bold_text(text)
