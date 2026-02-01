# Description
In order to fill in metadata in a standardized and simple way, metadata that is already contained directly in the data or calculated from it should be filled in automatically.

This script extracts the required metadata from the file and converts it into a JSON attribute table, 
which is converted into valid JSON LD in JSONLD Creator. 

This Script supports the following formats:
- [ASAM OpenDRIVE](https://www.asam.net/standards/detail/opendrive/)
- [ASAM OpenSCENARI XML](https://www.asam.net/standards/detail/openscenario-xml/)
- 3D Environment model (with metadata json input from [Trian3DBuilder](https://trian3dbuilder.de/))


Input
- Asset file

Output
- JSON attribute file 

# How to run
- main.py with arguments
    - [filename] : asset file to extract metadata - support xodr, xosc
    - -out : filename to exported json dict 
    - -u : Activates the user query via dialogues for non-extractable attributes - deprecated

# Install
```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```       
