"""Additive migration, same metadata and recovery as startup. Run with engine stopped."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
result=app.integrity.reconcile()
print({'schema':app.getv('integrity_schema_version'),'reconciliation':result})
if not result['ok']:raise SystemExit(2)
