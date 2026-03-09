# openDrive® meta data extractor
Parse openDrive® files (.xodr) for extracting and calculating meta data defined in the context of GaiaX.  
Link to defined meta data: https://ascs2008.sharepoint.com/:x:/r/sites/team/Freigegebene%20Dokumente/TP4%20%20-%20%20Automated%20Driving%20Function%20PLC/AP4.1/Metadata/Metadata.xlsx?d=w29f2c96ba33b44b992e30f513a0ed58b&csf=1&web=1&e=xr5cOU

# Motivation
We want to offer data providers a simple way to create metadata and also create a uniform definition of this data.

# Installation / How to setup

1. **Clone this git repository:** ``` git clone https://github.com/GAIA-X4PLC-AAD/xodr-metadaten-parser.git ~/xodr-parser ``` -> TBD

2. **Install python** (https://www.python.org/, used python version: Python 3.11.2)

    How to check current version on windows: ```py --version```
    How to check current version on macOS: ```python3 --version```

3. **Install packages**

    All dependencies are managed via the root `pyproject.toml`:

    ```bash
    make install  # from repository root
    ```

# Development
Used integrated development environment: PyCharm 2022.3.2

# How to run
1. Open your console/terminal
2. Navigate to cloned folder from GitHub with the main.py in it
3. Use on windows: ```py main.py``` or on macOS: ```python3 main.py```
4. Select the openDrive file you want to parse in the file dialog.
5. You will find the parsed file in the same file path as the source file.


# List of meta data defined in the context of GaiaX:
 
| variable name                  | description                                                  | computable/readable | unit                 |
|--------------------------------|--------------------------------------------------------------|---------------------|----------------------|
| description_type               | short data type description                                  | yes                 ||
| description_family             | town district                                                | no                  ||
| description_character          | with traffic signs                                           | no                  ||
|||||
| data_format                    |                                                              | yes                 ||
| format_version                 |                                                              | yes                 ||
|||||
| vendor_name                    |                                                              | yes                 ||
| vendor_date                    |                                                              | yes                 ||
| vendor_creation_source_version | tool for the creation of the data                            | no                  ||
|||||
| country                        |                                                              | in process          ||
| state                          |                                                              | in process          ||
| town                           |                                                              | in process          ||
| bounding                       |                                                              | in process          ||
|||||
| data_link                      | reference to dependent data                                  | not completely      ||
| media_link                     | reference to screenshot data                                 | no                  ||
|||||
| licence_type                   |                                                              | no                  ||
| licence_link                   |                                                              | no                  ||
|||||
| length_of_road                 | Road network length                                          | yes                 | km                   |
| elevation_range                |                                                              | yes                 | [min in m, max in m] |
| number_of_intersections        |                                                              | yes                 ||
| number_of_traffic_lights       |                                                              | yes                 ||
| number_of_traffic_signs        |                                                              | yes                 ||
| number_of_objects              |                                                              | yes                 ||
| number_of_outlines             |                                                              | yes                 ||
| speed_limit                    | range of speed limits                                        | yes                 | km/h or ms/s         |
| range_of_modeling              | how wide is the area beyond the traffic space modeled        | in process          ||
| lane_types                     | covered / used lane types                                    | yes                 ||
| level_of_detail                | covered object classes                                       | yes                 ||
|||||
| precision                      |                                                              | no                  ||
| accuracy                       | lane modell 2d, lane modell heigth, signs / signals, objects | no                  ||
||||
| road_types                     |                                                              | yes                 ||
||||
| recording_time                 |                                                              | in process          ||
| traffic_direction              |                                                              | in process          ||
||||
| projection_type                |                                                              | yes                 ||
| origin                         |                                                              | yes                 ||
| height_system                  | ellipsodial height or orthometric height                     | yes                 ||
| geodetic_datum                 | ETRF or ITRF                                                 | yes                 ||
|||||
| used_data_sources              |                                                              | no                  ||                                                           
| measurement_system             |                                                              | no                  ||                                                        
