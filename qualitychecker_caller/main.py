from pathlib import Path
from lxml import etree
from utils.subprocess import run_command

import argparse
import stat
import logging
import os
import sys

logger = logging.getLogger(__name__)

# update config file and replace input, output file and bundle name
def update_config_file(template_file: Path, checkerbundle_name: str, input_file: Path, result_file: Path, config_file: Path) -> Path:
    # Parse the XML file
    logger.info(f"Using template {template_file}")
    tree = etree.parse(template_file)
    root = tree.getroot()

    # Find the Param element 'application' in 'CheckerBundle' and update its value attribute
    for param in root.xpath("//*[local-name()='CheckerBundle']"):    
        param.set("application", checkerbundle_name)

    # Find the Param element 'InputFile' and update its value attribute
    for param in root.findall(".//Param[@name='InputFile']"):
        param.set("value", input_file.as_posix())

    # Find the Param element 'resultFile' and update its value attribute
    for param in root.findall(".//Param[@name='resultFile']"):
        param.set("value", result_file.as_posix())

    # Write the updated XML to the output file
    tree.write(config_file, encoding="utf-8", pretty_print=True, xml_declaration=True)
    logger.info(f"Created configuration file {config_file}")

    return config_file

# create config file
def create_config_file(config_file_name: Path, checkerbundle_name: str, input_file: Path, result_file : Path) -> Path:
    script_folder = Path(__file__).parent
    templates_folder = script_folder / 'templates'
    template_file = templates_folder / config_file_name

    if not template_file.exists():
        logger.error(f'template file not exist {template_file}')
        exit(1)

    return update_config_file(template_file, checkerbundle_name, input_file, result_file, Path("qc_config.xml"))

def main():
    # parse arguments
    parser = argparse.ArgumentParser(prog='main.py', description='setup and run quality checker')
    parser.add_argument('filename', type=str,help='ASAM OpenX file, e.g. xodr, xosc')
    parser.add_argument('-out', type=str, help='output result file')
    parser.add_argument('-config', type=str, help='name of config file in subfolder templates')    
    parser.add_argument('-app', type=str, help='name of quality checker application')
    parser.add_argument('-checkerbundle', type=str, help='name of checkerbundle')
    args = parser.parse_args()

    input_file = Path(args.filename)
    if not input_file.exists():
        logger.error(f'input file {input_file} not exists')
        exit(1)

    # create config file from templates with input_file replacement
    output_file = Path(args.out)
    if not output_file.parent.exists():
        output_file.parent.mkdir()   

    config_file_name = Path(args.config)
    if not config_file_name:
        logger.error(f'missing config file {config_file_name}')
        exit(1)    

    bundle_name = args.checkerbundle
    if not bundle_name:
        logger.error(f'bundle name not valid {bundle_name}')
        exit(1)        

    config_file = create_config_file(config_file_name, bundle_name, input_file, output_file)

    app_name = args.app
    if not app_name:
        logger.error(f'app name not valid {app_name}')
        exit(1)
    
    # call
    script_call = []
    script_call.append(app_name)
    script_call.append('-c')
    script_call.append(config_file.as_posix())

    run_command(cmd=script_call, name=app_name)

    # write als txt
    os.chdir(output_file.parent) # change system path
    script_call = []
    script_path = Path(__file__).resolve()
    if sys.platform.startswith("win"):
        appname = Path('TextReport.exe')
    elif sys.platform.startswith("linux"):
        appname = Path('TextReport')
    else:
        print(f"unknown system: {sys.platform}")
    text_report_executable_path = script_path.parent / 'apps' / appname
    script_call.append (f'{text_report_executable_path}') # call Textreport
    script_call.append(f'{output_file}')

    if sys.platform.startswith("linux") :
        os.chmod(text_report_executable_path, stat.S_IXUSR) #chmode +x TextReport (in docker i.e. the Docker )
        # Confirm permissions (optional)
        permissions = oct(os.stat(text_report_executable_path).st_mode)[-3:]
        logger.info(f"Permissions: {permissions}")
    run_command(script_call, f"Start Converting xqar to human readable form :")
    
    xqar_path_without_extension = output_file.with_suffix('')  # Get full path without extension
    new_path = f"{xqar_path_without_extension}_QCReport.txt"
    result_text_path = output_file.parent / 'Report.txt'
    result_text_path.rename(new_path)


if __name__ == "__main__":
    main()
