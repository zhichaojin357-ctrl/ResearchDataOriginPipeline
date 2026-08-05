# Agilent OpenLab processing runtime bundle

This directory contains the approved OpenLab Data Analysis 2.5 processing
closure used by `hplc-openlab-export --vendor-reprocess`:

- `agilent_openlab_processing_2_5.zip`: original Processing Server runtime,
  compiled project bridge, and the selected complete PMX method.
- `manifest.json`: archive hash, per-file hashes and sizes, entrypoints,
  minimization evidence, and the R01 natural-exit validation baseline.

The archive is not unpacked into the source tree. The Python adapter rejects
path traversal and non-regular archive members, verifies every member against
the manifest, and extracts to `.local_vendor_runtime` using a cache directory
keyed by the archive hash.

The binaries and method retain their respective vendor ownership and notices.
Their inclusion here records the project owner's authorization to version the
components required by this processing workflow; it does not replace any
applicable instrument/software entitlement.

The conservative payload is intentional. OpenLab discovers components through
PMX-embedded type names and runtime composition. Smaller 89-file and 127-file
sets failed bounded Processing Server tests, while the bundled closure completed
the R01 single-injection smoke test naturally and left no bridge/server process.
