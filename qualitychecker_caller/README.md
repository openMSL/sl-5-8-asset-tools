# Description
Calls ASAM's Quality Checker bundles (for [OpenDRIVE](https://github.com/asam-ev/qc-opendrive) and [OpenSCENARIO](https://github.com/asam-ev/qc-openscenarioxml)) and OpenMSL Simulation Checker bundle for [OpenDRIVE](https://github.com/openMSL/sl-5-9-openmsl-qc-opendrive) to validate the ASAM OpenX formats.

Input
- Asset file
- Default configuration file for QualityChecker (see [template](https://github.com/openMSL/sl-5-8-asset-tools/tree/main/qualitychecker_caller/templates) folder)

Output
- validation files in xqar and txt   
  
# How to run
- main.py with arguments
    - [filename] : ASAM OpenX file, e.g. xodr, xosc
    - -out : output result file
    - -config : name of config file in subfolder templates
    - -checkerbundle : name of checkerbundle

# Install
```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```    