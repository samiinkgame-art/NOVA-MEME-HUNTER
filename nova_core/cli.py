"""Offline administrative operations. Never starts providers or submits transactions."""
import argparse,json,os,sqlite3
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['migrate','reconcile','backup'])
    parser.add_argument('--output')
    args=parser.parse_args()
    if args.command=='backup':
        from sqlalchemy.engine import make_url
        u=make_url(os.getenv('DATABASE_URL','sqlite:///./nova_trader.db'))
        if u.get_backend_name()!='sqlite':parser.error('For PostgreSQL use pg_dump with protected environment credentials')
        if not args.output:parser.error('--output is required')
        source=Path(u.database).resolve();destination=Path(args.output).resolve()
        if not source.is_file() or source==destination or destination.exists():parser.error('Source must exist and backup destination must be new')
        with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as src,sqlite3.connect(destination) as dst:src.backup(dst)
        destination.chmod(0o600)
        print(json.dumps({'backup':str(destination),'completed':True}));return
    import app as core
    result=core.integrity.reconcile()
    print(json.dumps({'operation':args.command,'schema':core.getv('integrity_schema_version'),'reconciliation':result}))
    if not result['ok']:raise SystemExit(2)

if __name__=='__main__':main()
