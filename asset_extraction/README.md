# Description

The main script, which calls the other scripts according to their configuration and exchanges the generated data. Creates the asset.zip archive at the end.

The goal is to have a process that is as automated as possible, which uses asset data (OpenDRIVE, OpenSCENARIO) to create an asset archive for use in marketplaces such as [Envited Marketplace](https://staging.envited-x.net/).

Input
- json file with uploaded files from frontend
- Pipeline config file folder

Output
- Asset archive


# How to run
- main.py with arguments
	- [filenname] : json file with uploaded files from frontend
	- -config : config path for sub tools
    - -out : output path for asset archive

# Install
To install the required libraries run
    
```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```      