# Phase 1.10 Output Directory Governance

- `output/`: primary project output root. It contains canonical result packages, reports, manifests, review dashboards, dry-run plans, and final locked manifests.
- `outputs/`: specialized or historical run outputs. It is not raw data and is not canonical unless explicitly referenced by a report.
- Current canonical package: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output\phase1_6_origin_results_20260531_041538`
- Current freeze manifest: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output\final_locked_results\freeze_20260602_011419`
- Material collections are selection/extraction packages. Do not treat them as standard origin-batch manifests unless normalized.
- Do not delete OPJU/TIF/PNG, processed CSV, metadata, reports, Phase 1.5/1.6 packages, or `final_locked_results`.
- Future new result packages should be written under `output/phase*_...` or `output/final_locked_results/freeze_*`; specialized experiments may use `outputs/` only with a README/report.
