# Maintenance Scripts

Reusable maintenance scripts should live here when they are not part of the public CLI.

Do not place one-off report generators, raw-data processing outputs, or result artifacts here.

Current scripts:

- `opju_exemplar_regression.py`: compares OPJU exemplar outputs and records regression evidence. It may depend on Origin-related artifacts; do not treat it as a production data processor or run it during layout cleanup.
