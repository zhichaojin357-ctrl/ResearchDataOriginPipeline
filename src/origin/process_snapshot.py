"""Lightweight Windows process enumeration without spawning a command shell."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


def windows_process_snapshot() -> list[tuple[int, str, int]]:
    """Return PID, executable name and thread count from one Toolhelp snapshot.

    Toolhelp exposes names without opening each process, so protected Windows
    processes do not turn an ordinary ownership check into an access error.
    Windows bindings stay local to this function for non-Windows data workflows.
    """

    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel32.CreateToolhelp32Snapshot
    snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    snapshot.restype = wintypes.HANDLE
    first = kernel32.Process32FirstW
    next_entry = kernel32.Process32NextW
    for function in (first, next_entry):
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
        function.restype = wintypes.BOOL
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL

    handle = snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    records: list[tuple[int, str, int]] = []
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        available = first(handle, ctypes.byref(entry))
        while available:
            records.append((int(entry.th32ProcessID), entry.szExeFile, int(entry.cntThreads)))
            available = next_entry(handle, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES is the documented end of enumeration.
            raise ctypes.WinError(error)
    finally:
        close(handle)
    return records
