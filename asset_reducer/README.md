# Description
Reduces the original xml to relevant nodes and attributes (see [mapping_tables](https://github.com/openMSL/sl-5-8-asset-tools/tree/main/asset_reducer/mapping_tables)) and writes a binary json for the extended search. 

An advanced search is designed to access individual asset information directly, for quick access and without legal concerns.
See https://github.com/openMSL/sl-5-7-asset-services/tree/main/extended_search

Input
- Asset file

Output
- Asset archive

# How to run
- main.py with arguments
	- [filenname] : filename of asset in xml format
    - -out : output filname for reduced file as binary json

# Install
To install the required libraries run
    
```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```     