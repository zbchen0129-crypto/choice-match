"""Explicit migration, import, embedding and health commands."""
import argparse
import json
from pathlib import Path
from config import load_env
from database import migrate,import_candidates,counts
from fixtures import CANDIDATES

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['migrate','import','embed','status'])
    args=parser.parse_args();load_env()
    if args.action=='migrate':migrate();print('Migrations applied.')
    elif args.action=='import':
        print('demo import:',import_candidates(CANDIDATES,'demo'))
        path=Path(__file__).parent/'data/private/chicago.json'
        if path.exists():print('historical import:',import_candidates(json.loads(path.read_text())['candidates'],'historical'))
        print(json.dumps(counts()))
    elif args.action=='embed':
        from hybrid import build_embeddings
        print(json.dumps(build_embeddings()))
    else:print(json.dumps(counts()))
