# Description
A georeferenced vector format (Google KML or GeoJSON) is required for web display of the asset in order to show the route in a Google Map or OpenStreetMap view.

This script parses all street lines and converts them into LatLon coordinates and outputs them as a georeferenced vector format such as Google KML or GeoJSON.

Input
- Asset file

Output
- Georeferenced line geometry (in KML or GeoJSON)
- Georeferenced bounding box geometry (in KML or GeoJSON)

# How to run
- main.py with arguments
    - [filename] : filename of OpenDRIVE file
    - -out : filename of exported file - use extension for format selection ('kml', 'geojson')
	- -box : filename for boundingbox geo file - use extension for format selection ('kml', 'geojson')

# Install
```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```     