# Description
It is often helpful to have only part of an OpenDRIVE file, e.g., for debugging purposes. This script reduces the original OpenDRIVE file to the specified bounding box data.

Input
- OpenDRIVE file
- bounding box

Output
- reduced OpenDRIVE file (with postif "_reduced")

# How to run
- main.py with arguments
    - [filename] : filename of OpenDRIVE file
	- -bbox : bounding box as 4 values: x_min, y_min, x_max, y_max

# Install
```bash
pip install -r requirements.txt` 
```      
or 
```bash
python -m pip install -r requirements.txt`    
```    