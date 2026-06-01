# Origin Errors

- EIS_B11-2-A_4fa41d00: Generated graph layer not found: EIS_B11_2_A_4fa41d00_db92cfff

- EIS_B11-2-A_4fa41d00: Generated graph layer not found: EIS_B11_2_A_4fa4_db92cfff

- EIS_B11-2-A_4fa41d00: TIF export was not exported.

- EIS_B11-A_7cbd9639: Origin is already running. Close it or rerun with -AllowRunningOrigin after confirming no unsaved work will be affected

- EIS_BOBC-2-A_5198492f: Origin is already running. Close it or rerun with -AllowRunningOrigin after confirming no unsaved work will be affected

- EIS_CWO_EIS_d19d6b60: Origin is already running. Close it or rerun with -AllowRunningOrigin after confirming no unsaved work will be affected

- EIS_EIS-2GOOD_13d173c9: Origin is already running. Close it or rerun with -AllowRunningOrigin after confirming no unsaved work will be affected

- EIS_EIS_6625ff31: Origin is already running. Close it or rerun with -AllowRunningOrigin after confirming no unsaved work will be affected

- Mott-Schottky_MS3000_2d7575e1: Command '['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', 'D:\\Codex Project\\科研数据处理\\ResearchDataOriginPipeline\\output\\origin_jobs\\Mott-Schottky_MS3000_2d7575e1.ps1']' timed out after 600 seconds

- Mott-Schottky_MS3500_2_8433d93b: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS3500_3_7118b056: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS3500_4_4a28b0db: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS3500_539e4140: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS3500_5_d15c14c5: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS4000RE_5e3022ed: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS4000_2_9deeb279: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS4000_c58ce246: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS4000_f350a573: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS4000_re2_27f7c76d: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS4500_e0942275: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS5000_47b259fd: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- Mott-Schottky_MS5000_ec63b24b: Origin is still running before starting export; aborting to avoid attaching to an unsafe session.

- XPS_Br_BOBC_vs_BC_stacked: D:\CodexData\.codex\skills\origin-plotting\scripts\origin_plot_from_template.ps1 : The RPC server is unavailable. (Exce

- XPS_C_BOBC_vs_BC_stacked: <built-in function ApplicationBase_LT_execute> returned a result with an exception set

- XPS_Cl_BOBC_vs_BC_stacked: <built-in function ApplicationBase_LT_set_var> returned a result with an exception set

- XPS_O_BOBC_vs_BC_stacked: <built-in function ApplicationBase_LT_set_var> returned a result with an exception set

- XPS_C_CWO_vs_BC_stacked: <built-in function ApplicationBase_LT_set_var> returned a result with an exception set

- XPS_Cu_CWO_vs_BC_stacked: <built-in function ApplicationBase_LT_set_var> returned a result with an exception set

- XPS_O_CWO_vs_BC_stacked: <built-in function ApplicationBase_LT_set_var> returned a result with an exception set

- XPS_W_CWO_vs_BC_stacked: <built-in function ApplicationBase_LT_set_var> returned a result with an exception set

- XPS_C_CWO_vs_BC_stacked: New-Object : Retrieving the COM class factory for component with CLSID {B0F21977-8AAB-4632-A73D-528B909C5663} failed du

- XPS_Cl_BOBC_vs_BC_stacked: Origin peak annotation failed: Origin remained running after export.

- XPS_Bi_BOBC_vs_BC_stacked: Origin peak annotation failed: Origin remained running after export.

- XPS_W_CWO_vs_BC_stacked: Origin peak annotation failed: Traceback (most recent call last):

- XPS_Bi_BOBC_vs_BC_stacked: D:\CodexData\.codex\skills\origin-plotting\scripts\origin_plot_from_template.ps1 : The RPC server is unavailable. (Exce

- XPS_Cl_BOBC_vs_BC_stacked: Generated graph layer not found: XPS_Cl_BOBC_vs_2b8d8766

- XPS_O_BOBC_vs_BC_stacked: Generated graph layer not found: XPS_O_BOBC_vs_B_f812b077

- XPS_Cu_CWO_vs_BC_stacked: Origin peak annotation/image export failed: RuntimeError: Exception in OriginExt::ApplicationBase::LT_execute ==> 无效指针

- XPS_O_CWO_vs_BC_stacked: Origin peak annotation/image export failed: RuntimeError: Exception in OriginExt::ApplicationBase::LT_execute ==> 无效指针

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output\xps_heterojunction_stacked\origin_projects\origin_jobs\XPS_O_CWO_vs_BC_stacked_annotate.py", line 7, in <module>
    op.set_show(False)
  File "D:\Python\Lib\site-packages\originpro\utils.py", line 194, in set_show
    set_lt_var("@VIS", val)
  File "D:\Python\Lib\site-packages\originpro\utils.py", line 127, in set_lt_var
    po.LT_set_var(name, value)
    ^^^^^^^^^^^^^
  File "D:\Python\Lib\site-packages\originpro\config.py", line 29, in __getattr__
    self._app.LT_execute('sec -poc') # wait until OC ready
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Python\Lib\site-packages\OriginExt\OriginExt.py", line 2799, in LT_execute
    return _OriginExt.ApplicationBase_LT_execute(self, lpcszScript)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
SystemError: <built-in function ApplicationBase_LT_execute> returned a result with an exception set
