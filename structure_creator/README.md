# Description
Creates the file and folder structure for the asset archive. Creates a JSON file with the structure for further processing in JSONLD Creator for generating the manifest file.

# Motivation
Script that creates the desired structure for the asset archive and manifest.

# How to run
- main.py with arguments
	- [filenname] : json file with uploaded files from frontend
    - -out : output filname for reduced file as binary json
    - -path : path to copy/parse data.
    - -asset_json : filename to final asset json. Required for DID
    - -asset_extractor : filename to temp asset json. Required for recording Time

# Install
    To install the required libraries run: `pip install -r requirements.txt` or `python -m pip install -r requirements.txt`    