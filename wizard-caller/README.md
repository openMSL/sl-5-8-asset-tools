# Description
With the pre-filled jsonLD and the combined Shacl file, the [SD Creation Wizard](https://github.com/eclipse-xfsc/sd-creation-wizard-frontend) is called up for the user to complete.

*This module is currently __disabled__ in the pipeline because the SD Creation Wizard is not compatible with the latest Shacl version!*

Input
- JSON LD file
- combined Shacl file  

Output
- extended JSON LD file 

# How to run
- main.py with arguments
	- [filename] : filename of json LD file
    - -shacl : merged shacl file
    - -out : output filename for enhanced json LD file

# Install
```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```     