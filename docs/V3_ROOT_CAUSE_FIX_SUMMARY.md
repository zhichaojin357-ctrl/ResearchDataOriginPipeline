# V3 root-cause fix summary

- User style overrides now activate the named graph for every LabTalk style command.
- V3 export saves, reopens, reads back the final graph object, then exports TIF/PNG.
- V3 status no longer uses success/review; products are accepted only after strict gates, otherwise blocked/failed/skipped.
- V3 EIS recomputes cleaning and Randles-CPE fitting, then uses a measured-range main-plot segment and stores the full fit in debug.
- F-drive OPJU/OPJ template candidates are scanned and selected per data type; missing subtype-matched XPS templates are blocked rather than substituted.
