# Readiness Project Rename Path Guard

`run.py readiness` now verifies that the old `GroupMeetingAutoPPT` sibling path is absent and active project entry documents do not point to the old path.

Current status:

- Old sibling path: absent
- Active entry documents: current
- readiness: 20 checks, 0 failures, 0 warnings

Verification:

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 11 tests.
- `D:\Python\python.exe run.py readiness`: exit 0.
