# Local setup

Run commands from the project directory. The no-key preview is the recommended review path: `python3 scripts/preview_lab.py`, then open http://127.0.0.1:8789/. It expires after five minutes and deliberately removes model/database variables from its process.

## Optional model-backed mode

1. Create a virtual environment and install the database adapter if using PostgreSQL:

   ```sh
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. If `.env` does not already exist, copy `.env.example` to `.env`. Enter credentials locally; do not commit or share them. Existing environment variables override `.env` values. Model and embedding names are configurable; examples reflect the project's tested configuration, not a promise of current availability.
3. Without `DATABASE_URL`, `python3 server.py` serves fictional fixtures and uses the keyword model path. With `DATABASE_URL`, it expects an initialized running PostgreSQL database. Open http://127.0.0.1:8767/. If that port is occupied, do not stop an unrelated service; use the no-key preview on 8789 for the portfolio walkthrough.
4. Model parsing, extraction, explanation, and embedding operations can incur API usage and transmit selected text. The no-key preview is separate from this mode.

## Optional PostgreSQL + pgvector

`local_db.py` is specific to Apple Silicon Homebrew PostgreSQL 18 paths. See [database setup](database.md) for that environment. On other platforms, provision PostgreSQL with pgvector and set a private `DATABASE_URL`; the helper itself is not portable.

After configuring a running empty development database:

```sh
.venv/bin/python db_manage.py migrate
.venv/bin/python db_manage.py import
.venv/bin/python db_manage.py embed
```

Inspect `db_manage.py --help` for import options. Embedding calls are paid; do not run them merely to review the UI. Historical files are optional and are not shipped in the repository.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

This runs local tests and skips five database integration tests. For database tests, use a running development database and the configured virtual environment:

```sh
.venv/bin/python - <<'PY'
import os
import unittest
from config import load_env
load_env()
os.environ['CHOICEMATCH_DB_TEST'] = '1'
result = unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.discover('tests'))
raise SystemExit(not result.wasSuccessful())
PY
```

Database tests create isolated test records and clean them up. Tests mock model requests; they are separate from paid live evaluation scripts. Development verification used Python 3.14 on macOS; a cross-platform CI matrix is not yet established.
