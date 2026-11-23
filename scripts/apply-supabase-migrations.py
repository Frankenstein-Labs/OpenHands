#!/usr/bin/env python3
"""Apply supabase/migrations in order through the Supabase Management API.

Use this when no direct Postgres connection is available. It needs a Supabase
access token (a `sbp_...` personal access token) that can reach the project.

  SUPABASE_ACCESS_TOKEN=sbp_...
  SUPABASE_PROJECT_REF=hmqbdhkufqvbjafyubxd
  python scripts/apply-supabase-migrations.py --confirm-project hmqbdhkufqvbjafyubxd

`--dry-run` prints the plan without executing anything.

Each migration is recorded in `public.cortex_migrations`, so rerunning is safe:
already applied versions are skipped. The token is never printed and never
written to disk.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / 'supabase' / 'migrations'
API = 'https://api.supabase.com/v1/projects/{ref}/database/query'

LEDGER = """
create table if not exists public.cortex_migrations (
  version text primary key,
  name text not null,
  applied_at timestamptz not null default now()
);
"""


def query(token: str, ref: str, sql: str) -> list[dict]:
    request = urllib.request.Request(
        API.format(ref=ref),
        data=json.dumps({'query': sql}).encode(),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode()
            return json.loads(body) if body else []
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:400]
        raise SystemExit(f'FAIL management API returned {exc.code}: {detail}') from exc


def migrations() -> list[Path]:
    return sorted(p for p in MIGRATIONS_DIR.glob('*.sql') if p.is_file())


def applied(token: str, ref: str) -> set[str]:
    query(token, ref, LEDGER)
    rows = query(token, ref, 'select version from public.cortex_migrations order by version;')
    return {row['version'] for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument(
        '--confirm-project',
        required=True,
        help='project ref you intend to migrate; must match SUPABASE_PROJECT_REF',
    )
    args = parser.parse_args()

    token = os.environ.get('SUPABASE_ACCESS_TOKEN', '').strip()
    ref = os.environ.get('SUPABASE_PROJECT_REF', '').strip()
    if not token or not ref:
        print('FAIL set SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF')
        return 1
    if args.confirm_project != ref:
        print('FAIL --confirm-project does not match SUPABASE_PROJECT_REF')
        return 1

    files = migrations()
    if not files:
        print(f'FAIL no migrations found in {MIGRATIONS_DIR}')
        return 1

    done = set() if args.dry_run else applied(token, ref)
    pending = [path for path in files if path.name not in done]
    print(f'{len(files)} migrations, {len(pending)} pending')
    for path in pending:
        print(f'  {"would apply" if args.dry_run else "applying"} {path.name}')
        if args.dry_run:
            continue
        sql = path.read_text()
        query(token, ref, f'begin;\n{sql}\ncommit;')
        query(
            token,
            ref,
            'insert into public.cortex_migrations (version, name) values '
            f"({path.name!r}, {path.stem!r}) on conflict (version) do nothing;",
        )

    if args.dry_run:
        print('dry run: nothing executed')
        return 0
    print('done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
