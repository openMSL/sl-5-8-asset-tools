# Description
calculates the bounding box of the road data in the OpenDRIVE and outputs the lat/lon box as a print

# Motivation
in some OpenDRIVE files the bounding specification is missing

# How to run
- main.py with arguments
    - [filename] : filename of OpenDRIVE file
    - -box : bounding box as 4 values: x_min, y_min, x_max, y_max

# Install
    To install the required libraries run: `pip install -r requirements.txt` or `python -m pip install -r requirements.txt`    