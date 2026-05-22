# quality_checker

## Description

Runs ASAM/OpenMSL quality checker applications for OpenX files and converts generated `.xqar` reports to text reports.

## Usage

```bash
python -m quality_checker.main <asset_file> -out <report.xqar> -config <template.xml> -app <checker_app> -checkerbundle <bundle_name>
```

## Arguments

- `filename` (required): Input OpenX file (`.xodr` or `.xosc`).
- `-out` (required): Target `.xqar` output file path.
- `-config` (required): XML config template filename from `quality_checker/templates`.
- `-app` (required): Checker executable name (for example `qc_opendrive`, `qc_openscenario`, `openmsl_qc_opendrive`).
- `-checkerbundle` (required): Checker bundle name used in config.

## Input

- OpenX file
- Checker config template

## Output

- `.xqar` validation report
- `*_QCReport.txt` text report

## Install

```bash
make install  # from repository root
```

## Notes

- Text reports are generated using the pure-Python `qc_baselib.Result` API (no native binaries required).
