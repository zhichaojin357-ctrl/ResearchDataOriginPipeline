# XPS Origin Plotting Guardrails

These rules are project-specific guardrails for the BOBC/CWO/BC fitted XPS stacked plots.

## Do Not Repeat These Mistakes

- Do not copy the whole Graph4/template style. Only reuse the user-specified parts: axis title size, bold weight, page/layer dimensions, and related axis formatting.
- Do not place peak labels on top of fitted peaks, filled components, the envelope, or the region enclosed by the curve and baseline. Peak labels must sit in the blank area above each sample trace.
- Do not match fitted-component colors by `Scan A`, `Scan B`, or Excel column order. Match colors by fitted peak binding energy, using the integer part of binding energy as the cross-sample color key.
- Do not use Origin rich text `\b(...)` for multi-line peak labels. It can leave stray parentheses in exported figures. Use object-level font size and bold settings for peak labels.
- Do not move the y-axis title inward. If the user says it is too close, move it away from the axis and verify visually.
- Do not let labels at low binding energy sit outside the plot frame. Clamp label x positions inside the frame with enough right/left margin.
- Do not reintroduce y-axis numeric tick labels unless the user asks for them again.

## Current User Requirements

- X and Y axis titles: 36 pt, bold.
- Y-axis title should be farther from the y-axis than the default placement.
- Peak labels: bold, large, outside the curve/fill area, inside the plot frame.
- Plot/page geometry should use the requested Graph4 dimensions/axis proportions without importing unrelated Graph4 objects.
- Cu2p colors must correspond by binding energy, not by Scan label or component order.
- Residuals are not plotted.
- Backgnd. is grey; Envelope is black solid.
