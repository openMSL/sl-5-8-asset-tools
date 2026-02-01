# Description
Creates the folder and file structure for the asset archive and writes the structure to a JSON file for further processing in JSONLD Creator for generating the manifest file. 
    
Additional data on the asset, such as documentation, images, and videos, are defined by the user in the front end (see https://github.com/openMSL/sl-5-7-asset-services/tree/main/asset_extractor) and evaluated in this module as a JSON file.

Input
- JSON file with additional asset data (from the frontend)

Output
- Folder and file structure        
- JSON attribute file (for Manifest)      

# How to run
- main.py with arguments
	- [filenname] : json file with uploaded files from frontend
    - -out : output filname for reduced file as binary json
    - -path : path to copy/parse data.
    - -asset_json : filename to final asset json. Required for DID
    - -asset_extractor : filename to temp asset json. Required for recording Time

# Install
```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```     