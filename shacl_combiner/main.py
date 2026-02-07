from pathlib import Path
from utils.rdf import load_jsonld_file, get_shacle_from_json_graph
from utils.constants import ENVITEDX_URL, ENVITEDX_NAME

import argparse
import logging

logger = logging.getLogger(__name__)
   
def main():
    parser = argparse.ArgumentParser(prog='main.py', description='combine shalce file for jsonLD to one file')
    parser.add_argument('filename', type=str,help='json LD filename')
    parser.add_argument('-out', type=str, help='output path for combined shacle file')
    args = parser.parse_args()

    # load json
    json_LD_file = Path(args.filename)
    data_graph = load_jsonld_file(json_LD_file)  

    # load shacls
    prefixes_to_add = {ENVITEDX_NAME : f'{ENVITEDX_URL}{ENVITEDX_NAME}/v2/ontology#'}
    shacl_graph = get_shacle_from_json_graph(data_graph, prefixes_to_add)

    output_path = Path(args.out)
    if not output_path.exists():
        output_path.mkdir()    
    file = output_path / Path(json_LD_file.stem + '.ttl')
    with open(file, 'w', encoding='utf-8') as f:
        f.write(shacl_graph.serialize(format='turtle'))
        f.close()
        logger.info(f'write {file}')

if __name__ == '__main__':
    main()