"""Consistent SQLite backup, with integrity and restore verification."""

import argparse
import sqlite3
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("database")
parser.add_argument("destination")
args = parser.parse_args()
destination = Path(args.destination)
if destination.exists():
    raise SystemExit("Destinazione esistente: scegliere un nuovo nome")
with (
    sqlite3.connect(
        f"file:{Path(args.database).resolve()}?mode=ro", uri=True
    ) as source,
    sqlite3.connect(destination) as target,
):
    source.backup(target)
    assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
with tempfile.TemporaryDirectory() as tmp:
    restored = Path(tmp) / "restored.db"
    with sqlite3.connect(destination) as backup, sqlite3.connect(restored) as restore:
        backup.backup(restore)
        assert restore.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            restore.execute("SELECT count(*) FROM offers").fetchone()
            == backup.execute("SELECT count(*) FROM offers").fetchone()
        )
print("Backup e ripristino temporaneo verificati:", destination)
