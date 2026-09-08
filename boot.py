#!/usr/bin/env python
"""
  1. Checks .env exists and required keys are set
  2. Checks PostgreSQL is reachable
  3. Installs/verifies pip dependencies
  4. Runs migrations
  5. Seeds races and candidates from JSON files
  6. Starts Django dev server on 127.0.0.1:8000
"""

import os
import sys
import subprocess
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"

# ── Colours ───────────────────────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; E = "\033[0m"
def ok(msg):   print(f"  {G}✓{E}  {msg}")
def warn(msg): print(f"  {Y}!{E}  {msg}")
def err(msg):  print(f"  {R}✗{E}  {msg}"); sys.exit(1)
def step(msg): print(f"\n{B}▶ {msg}{E}")

print(f"\n{B}══ AUEC Election System — Boot ══{E}\n")

# ── 1. .env check ─────────────────────────────────────────────────────────────
step("Checking .env")
if not ENV_FILE.exists():
    err(".env not found. Copy .env and fill in your values.")

from dotenv import load_dotenv
load_dotenv(ENV_FILE)

required_keys = [
    "DJANGO_SECRET_KEY",
    "GOOGLE_OAUTH2_CLIENT_ID",
    "GOOGLE_OAUTH2_CLIENT_SECRET",
]
missing = [k for k in required_keys if not os.getenv(k) or os.getenv(k, "").startswith("replace")]
if missing:
    err(f"Missing or placeholder values in .env: {', '.join(missing)}\nEdit .env before booting.")
ok(".env loaded and keys present")

# ── 2. Dependencies ───────────────────────────────────────────────────────────
step("Installing dependencies")
req = ROOT / "requirements.txt"
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
    capture_output=True, text=True
)
if result.returncode != 0:
    err(f"pip install failed:\n{result.stderr}")
ok("Dependencies satisfied")

# ── 3. PostgreSQL reachability ────────────────────────────────────────────────
step("Checking PostgreSQL connection")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "election.settings")
sys.path.insert(0, str(ROOT))

import django
django.setup()

from django.db import connection
for attempt in range(1, 6):
    try:
        connection.ensure_connection()
        ok(f"PostgreSQL connected ({os.getenv('DB_HOST','127.0.0.1')}:{os.getenv('DB_PORT','5432')})")
        break
    except Exception as e:
        if attempt == 5:
            err(f"Cannot reach PostgreSQL after 5 attempts: {e}\nCheck DB_* values in .env and that PostgreSQL is running.")
        warn(f"Attempt {attempt}/5 failed, retrying in 2s…")
        time.sleep(2)

# ── 4. Migrations ─────────────────────────────────────────────────────────────
step("Running migrations")
result = subprocess.run(
    [sys.executable, "manage.py", "migrate", "--run-syncdb"],
    cwd=ROOT, capture_output=True, text=True
)
if result.returncode != 0:
    # Print output for debugging, but only if there's an actual error
    print(result.stdout[-2000:] if result.stdout else "")
    err(f"Migration failed:\n{result.stderr[-1000:]}")
ok("Migrations applied")

# ── 5. Seed races + candidates ────────────────────────────────────────────────
step("Seeding races and candidates")
from voting.eligibility import seed_races_and_candidates
try:
    seed_races_and_candidates()
    ok("Races and candidates seeded from JSON files")
except Exception as e:
    warn(f"Seeding warning (non-fatal): {e}")

# ── 6. Summary ────────────────────────────────────────────────────────────────
from voting.models import Race, Candidate, Voter, Vote
print(f"\n  Races:      {Race.objects.count()}")
print(f"  Candidates: {Candidate.objects.count()}")
print(f"  Voters:     {Voter.objects.count()} registered")
print(f"  Votes:      {Vote.objects.count()} cast")

admin_emails = list(
    Voter.objects.filter(role="auec_admin").values_list("email", flat=True)
)
if admin_emails:
    print(f"  Admins:     {', '.join(admin_emails)}")
else:
    print(f"\n  {Y}No AUEC admins yet.{E}")
    print(f"  After first login, promote someone with:")
    print(f"    python manage.py make_admin their@ashoka.edu.in")

# ── 7. Start server ───────────────────────────────────────────────────────────
print(f"\n{G}══ Starting server ═══════════════════════{E}")
print(f"  URL:  http://127.0.0.1:8000")
print(f"  OAuth redirect: http://127.0.0.1:8000/auth/complete/google-oauth2/")
print(f"  Stop: Ctrl+C\n")

os.execv(sys.executable, [sys.executable, "manage.py", "runserver", "127.0.0.1:8000"])