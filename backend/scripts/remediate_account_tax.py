"""One-time pre-registry cleanup. Dry-run unless --apply; never called at startup."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sqlalchemy import text

EXPECTED = {
    4: ('SQWHDQDIOH3HWFW', 'WHDQDIOH3H'),
    5: ('DHFBADSJBJHABSD', 'FBADSJBJHA'),
    10: ('27AT1234F2Z5YUI', 'AT1234F2Z5'),
}
REVISION = 'c4a9e7120d35'


def remediate(engine, *, apply=False, audit_path=None):
    """Caller supplies the engine; tests use disposable PostgreSQL only.

    Artifact records intent, not a claim that the following commit succeeded.
    Exclusive file creation prevents overwriting previous provenance.
    """
    if apply and audit_path is None:
        raise ValueError('--audit-file is required with --apply')
    with engine.begin() as connection:
        if apply:
            connection.execute(text('LOCK TABLE alembic_version, parties IN SHARE ROW EXCLUSIVE MODE'))
        else:
            connection.execute(text('SET TRANSACTION READ ONLY'))
        revisions = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
        if revisions != [REVISION]:
            raise ValueError('Expected pre-registry revision c4a9e7120d35; no changes made.')
        rows = connection.execute(text(
            'SELECT id,party_code,name,gstin,pan_card FROM parties WHERE id IN (4,5,10) ORDER BY id'
        )).mappings().all()
        if {r['id']: (r['gstin'], r['pan_card']) for r in rows} != EXPECTED:
            raise ValueError('Party tax baseline differs; entire remediation aborted.')
        artifact = dict(revision=REVISION, recorded_at=datetime.now(timezone.utc).isoformat(),
                        operation='set gstin and pan_card to NULL',
                        status='pre-mutation intent' if apply else 'dry-run',
                        parties=[dict(row) for row in rows])
        if audit_path is not None:
            with Path(audit_path).open('x', encoding='utf-8') as stream:
                json.dump(artifact, stream, indent=2, ensure_ascii=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
        if apply:
            result = connection.execute(text(
                'UPDATE parties SET gstin=NULL, pan_card=NULL WHERE id IN (4,5,10)'))
            if result.rowcount != 3:
                raise RuntimeError('Unexpected update count; rolling back.')
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--audit-file', type=Path)
    args = parser.parse_args()
    from api.config.database import engine
    try:
        artifact = remediate(engine, apply=args.apply, audit_path=args.audit_file)
    except Exception:
        # Driver exceptions may contain connection details; do not print them.
        parser.exit(1, 'Remediation failed; no transaction committed. Check revision, exact values and artifact path.\n')
    print(json.dumps(artifact, indent=2))
    print('Committed three tax-only updates.' if args.apply else 'DRY RUN: no data modified.')


if __name__ == '__main__':
    main()
