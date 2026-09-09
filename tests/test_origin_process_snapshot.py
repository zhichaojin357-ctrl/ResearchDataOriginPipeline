from __future__ import annotations

import ctypes
import os
from types import SimpleNamespace
from unittest import mock

import pytest

from src.origin import process_snapshot


@pytest.mark.skipif(os.name != "nt", reason="Requires the real Windows Toolhelp API")
def test_toolhelp_snapshot_includes_current_python_process_on_windows():
    records = process_snapshot.windows_process_snapshot()
    current = [(name, threads) for pid, name, threads in records if pid == os.getpid()]
    assert len(current) == 1
    name, threads = current[0]
    assert name.strip()
    assert threads > 0


@pytest.mark.parametrize("failure", [None, "snapshot", "first", "next"])
def test_toolhelp_snapshot_preserves_records_and_closes_handles(monkeypatch, failure):
    """Exercise the real ctypes adapter against the documented Win32 protocol."""
    records = iter([(8123, "Origin64.exe", 5), (42, "研究数据.exe", 2)])
    error = 0

    def advance(_handle, pointer):
        nonlocal error
        entry = pointer._obj
        assert entry.dwSize == ctypes.sizeof(entry)
        try:
            pid, name, threads = next(records)
        except StopIteration:
            error = 18  # ERROR_NO_MORE_FILES
            return False
        entry.th32ProcessID = pid
        entry.szExeFile = name
        entry.cntThreads = threads
        return True

    def reject(_handle, _pointer):
        nonlocal error
        error = 5  # ERROR_ACCESS_DENIED must not be treated as an empty list.
        return False

    kernel = SimpleNamespace(
        CreateToolhelp32Snapshot=mock.Mock(return_value=123),
        Process32FirstW=mock.Mock(side_effect=reject if failure == "first" else advance),
        Process32NextW=mock.Mock(side_effect=reject if failure == "next" else advance),
        CloseHandle=mock.Mock(return_value=True),
    )
    if failure == "snapshot":
        kernel.CreateToolhelp32Snapshot.return_value = ctypes.c_void_p(-1).value
        error = 5
    loader = mock.Mock(return_value=kernel)
    monkeypatch.setattr(ctypes, "WinDLL", loader, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    monkeypatch.setattr(ctypes, "WinError", lambda code: OSError(code, "Win32 error"), raising=False)

    if failure:
        with pytest.raises(OSError) as raised:
            process_snapshot.windows_process_snapshot()
        assert raised.value.errno == 5
    else:
        assert process_snapshot.windows_process_snapshot() == [
            (8123, "Origin64.exe", 5), (42, "研究数据.exe", 2),
        ]
    loader.assert_called_once_with("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.assert_called_once_with(2, 0)
    if failure == "snapshot":
        kernel.CloseHandle.assert_not_called()
    else:
        kernel.CloseHandle.assert_called_once_with(123)


def test_toolhelp_snapshot_can_return_an_empty_process_list(monkeypatch):
    kernel = SimpleNamespace(
        CreateToolhelp32Snapshot=mock.Mock(return_value=123),
        Process32FirstW=mock.Mock(return_value=False),
        Process32NextW=mock.Mock(),
        CloseHandle=mock.Mock(return_value=True),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: kernel, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 18, raising=False)
    assert process_snapshot.windows_process_snapshot() == []
    kernel.Process32NextW.assert_not_called()
    kernel.CloseHandle.assert_called_once_with(123)
