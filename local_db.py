"""Manage an isolated project database; no login service or global cluster."""
import argparse
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from config import ENV_PATH, load_env

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/private/postgres'
BIN = Path('/opt/homebrew/opt/postgresql@18/bin')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['init','start','stop','status'])
    args = parser.parse_args()
    load_env()
    if args.action == 'init':
        if (DATA / 'PG_VERSION').exists():
            print('Project database already initialized.')
            return
        DATA.parent.mkdir(parents=True, exist_ok=True)
        if os.getenv('DATABASE_URL'):
            url=urlparse(os.environ['DATABASE_URL'])
            if (url.hostname,url.port,url.username,url.path)!=('127.0.0.1',55437,'choicematch','/choicematch') or not url.password:
                raise SystemExit('DATABASE_URL is not the isolated local instance; refusing to overwrite it.')
            password=url.password
        else:
            password = secrets.token_urlsafe(32)
            # Save first so a retry can reuse the credential after failed initialization.
            with ENV_PATH.open('a') as handle:
                handle.write(f'\nDATABASE_URL=postgresql://choicematch:{password}@127.0.0.1:55437/choicematch\n')
        ENV_PATH.chmod(0o600)
        with tempfile.NamedTemporaryFile(mode='w', dir=DATA.parent) as handle:
            handle.write(password+'\n');handle.flush()
            subprocess.run([str(BIN/'initdb'),'-D',str(DATA),'-U','choicematch','--auth=scram-sha-256',
                            '--pwfile='+handle.name,'--encoding=UTF8','--locale=C'],check=True)
        with (DATA/'postgresql.conf').open('a') as handle:
            handle.write("\nlisten_addresses = '127.0.0.1'\nport = 55437\nunix_socket_directories = ''\n")
        print('Initialized isolated database; credential saved to ignored .env.')
    elif args.action == 'start':
        status = subprocess.run([str(BIN/'pg_ctl'),'-D',str(DATA),'status'],capture_output=True)
        if status.returncode != 0:
            subprocess.run([str(BIN/'pg_ctl'),'-D',str(DATA),'-l',str(DATA.parent/'postgres.log'),'-w','start'],check=True)
        import psycopg
        from psycopg.conninfo import conninfo_to_dict
        values=conninfo_to_dict(os.environ['DATABASE_URL']);values['dbname']='postgres'
        with psycopg.connect(**values,autocommit=True) as conn:
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname='choicematch'").fetchone():
                conn.execute('CREATE DATABASE choicematch')
        print('ChoiceMatch database ready on localhost:55437.')
    else:
        command=[str(BIN/'pg_ctl'),'-D',str(DATA),args.action]
        if args.action=='stop':command.extend(['-m','fast'])
        subprocess.run(command,check=True)


if __name__=='__main__':
    main()
