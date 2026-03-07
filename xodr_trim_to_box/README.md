# xodr_trim_to_box

## Description
Reduces an OpenDRIVE file to a specified bounding box and writes a `_reduced` output file.

## Usage
```bash
python -m xodr_trim_to_box.main <file.xodr> --bbox <x_min> <y_min> <x_max> <y_max>
```

## Arguments
- `filename` (required): OpenDRIVE input file.
- `--bbox` (required): Bounding box values `x_min y_min x_max y_max`.

## Input
- OpenDRIVE file
- Bounding box coordinates

## Output
- Reduced OpenDRIVE file with `_reduced` suffix

## Install
```bash
python -m pip install -r xodr_trim_to_box/requirements.txt
```
