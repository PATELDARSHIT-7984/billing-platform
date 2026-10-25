"""Environment settings shared by the API and Alembic."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

# Resolve from this file, not the working directory. Cloud variables take priority.
load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL is required. Set it in the environment or backend/.env.')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = 'postgresql://' + DATABASE_URL[len('postgres://'):]

FRONTEND_ORIGINS = [origin.strip().rstrip('/') for origin in
                    os.environ.get('FRONTEND_ORIGIN', 'http://localhost:5173').split(',') if origin.strip()]
for origin in FRONTEND_ORIGINS:
    parsed = urlsplit(origin)
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc or '*' in origin
            or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise RuntimeError('FRONTEND_ORIGIN must contain HTTP(S) origins without paths or wildcards.')
