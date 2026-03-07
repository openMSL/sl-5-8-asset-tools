from pathlib import Path

import time
import logging
import argparse
import requests
import shutil

logger = logging.getLogger(__name__)

#  trigger if SD Creation Wizard is open
def trigger_open_sd_wizard(endpoint_url):
    try:
        response = requests.post(endpoint_url)
        if response.status_code == 200:
            print("Triggered the SD Wizard successfully")
        else:
            print(f"Failed to trigger SD Wizard: {response.status_code}")
    except Exception as e:
        print(f"Error triggering SD Wizard: {e}")


def post_filepath(file_path, endpoint_url, output_path = None):
    try:
        data = {"file_path": file_path, 'meta_data_location': output_path} if output_path is not None else {"file_path": file_path}
        response = requests.post(endpoint_url,json = data)
        if response.status_code == 200:
            print("Tools successfully sent file path: "+ file_path)
            if output_path is not None : print("and meta data location: " + output_path)
        else:
            print(f"Tools got sending error: {response.status_code}")
    except Exception as e:
        print(f"Error sending file path: {e}")
        
# check if combined json is avaiable     
def check_combined_json(endpoint_url):
    while True:
        response = requests.get(endpoint_url)  # Repeat the GET request
        if response.status_code == 204:
            print("File is not ready yet, sleeping 10 seconds ...")
            time.sleep(10)
        elif response.status_code == 200:
            print("File is ready, continue execution")
            return  # Exit the function when the file is ready
        else:
            print(f"Tools got receiving error: {response.status_code}")
            break  # Exit the loop if there is an error
        
def main():
    # parse arguments
    parser = argparse.ArgumentParser(prog='main.py', description='calls the sd creation wizard with json and merged shacl file to fill the non-extractable attributes from the user')
    parser.add_argument('filename', type=str, help='filename of json LD file')
    parser.add_argument('-shacl', type=str, help='merged shacl file')
    parser.add_argument('-enable', type=str, help='if true call wizard and copy file to out, if false copy input to out')
    parser.add_argument('-out', type=str, help='output filename for enhanced json LD file')
    args = parser.parse_args()

    jsonLD_file = Path(args.filename)
    if not jsonLD_file.exists():
        raise FileNotFoundError(f'jsonLD file not exist {jsonLD_file}')

    shacl_file = Path(args.shacl)
    if not shacl_file.exists():
        raise FileNotFoundError(f'shacl file not exist {shacl_file}')

    output_path = Path(args.out)         

    enable = str(args.enable).strip().lower() == "true"
    if enable:
        # call sd wizrad in docker composed
        trigger_open_sd_wizard('http://localhost:3000/openSdWizard')

        # use jsonLD_file, shacl_file
        post_filepath(str(jsonLD_file), 'http://localhost:3000/processJsonLDFile', str(output_path))
        post_filepath(str(shacl_file), 'http://localhost:3000/processShaclFile')
        # get enhanced jsonLD file
        # copy to target file location
        check_combined_json('http://localhost:3000/processCombinedJsonFile')
    else:
        # copy only input file to output
        shutil.copy2(jsonLD_file, output_path)
        logger.info(f'copy json ld to {output_path}')
        return


if __name__ == '__main__':
    main()
