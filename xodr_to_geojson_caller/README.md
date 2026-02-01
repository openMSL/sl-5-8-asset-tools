# Description
Calls the [opendriveconverter](https://github.com/virtualcitySYSTEMS/opendriveconverter) java tool from Virtual City Systems to convert an OpenDRIVE file into a geojson.

*This module is currently __disabled__ in the pipeline because the application requires a special Java version, which still needs to be set up! In addition, the generated geometry data takes up a large part of the asset archive!*  

Input
- Asset file

Output
- Geometry files in Geojson format

# How to run

- main.py with arguments
    - [filename] : filename of OpenDRIVE file
    - -out : geojson file
    - -path : path to the temp folder for a temporary opendrive with customized header

# Install
Java 17 or higher must be installed.

```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```    
