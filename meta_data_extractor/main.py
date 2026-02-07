   
from .extractor import extract
from pathlib import Path

import argparse
import logging

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(prog='main.py', description='extractor meta data from a given file.')
    parser.add_argument('filename', help='filename to extract metadata')
    parser.add_argument('-out', '--output', type=str, help='filename to exported json dict.')
    parser.add_argument('-u', '--user_input', action='store_true', help='Activates the user query via dialogues for non-extractable attributes.')    

    # 1. get and check arguments
    args = parser.parse_args()

    # get output dir
    output_file = Path(args.output)
    if not output_file:
        exit(1)
    
    directory = output_file.parent
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)

    
    file = Path(args.filename)
    if not file.exists():
        exit(1)

    # extract meta data depended on asset type
    valid = extract(file, output_file)
    if valid is not True:
        logger.error(f'file {file.absolute()} can not be extraced')

if __name__ == '__main__':
    main()
