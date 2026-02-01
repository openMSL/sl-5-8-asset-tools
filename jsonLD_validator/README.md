# Description
Validates a jsonLD file based on its ontology files. The idea is to have an automatic verification of the generated JSON-LD files for the pipeline.

Input
- JSON LD file

# How to run
- main.py with arguments
    - [filename] : json LD file
    - -closed : Additional verification of the naming of properties in all NodeShapes

# Install
To install the required libraries run
    
```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```      