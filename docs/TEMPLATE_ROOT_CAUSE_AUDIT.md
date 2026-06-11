# Template-format root-cause audit

- Historical baseline products are treated as rejected reference material, not final products.
- Root cause 1: style overrides were not bound to the named graph in every LabTalk command; later commands could depend on the active page.
- Root cause 2: historical products saved and exported from the live in-memory graph without a save/reopen/readback gate.
- Root cause 3: conformance checked internal readback but did not enforce exported-preview visual acceptance as the status gate.
- Root cause 4: the EIS full Randles-CPE extension expanded far beyond the measured Z' range, causing the main plot to look like a large unreasonable arc.
- Root cause 5: historical products accepted `success/review` wording even when manual visual acceptance was still unresolved.
