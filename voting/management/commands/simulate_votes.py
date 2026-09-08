"""
voting/management/commands/simulate_votes.py

Creates 1000 voters, issues tokens, casts randomised votes,
then exports the ledger and prints a final tally.

Run: python manage.py simulate_votes [--voters 1000] [--reset]
check 
"""

import random
from django.core.management.base import BaseCommand
from django.db import transaction

from voting.models import Voter, Candidate, VotingToken, Vote
from voting.services import issue_token, submit_vote_v2, VoteError, build_ledger

import json, pathlib


class Command(BaseCommand):
    help = "Simulate N voters casting votes end-to-end"

    def add_arguments(self, parser):
        parser.add_argument("--voters", type=int, default=1000)
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Wipe all votes/tokens/voters before running (for re-runs).",
        )

    def handle(self, *args, **options):
        n = options["voters"]

        if options["reset"]:
            self.stdout.write("Resetting data...")
            Vote.objects.all().delete()
            VotingToken.objects.all().delete()
            Voter.objects.all().delete()

        candidates = list(Candidate.objects.all())
        if not candidates:
            self.stderr.write("No candidates found. Run: python manage.py shell < scripts/seed_candidates.py")
            return

        # ── 1. Create voters ──────────────────────────────────────────────
        self.stdout.write(f"Creating {n} voters...")
        voters = []
        existing_emails = set(Voter.objects.values_list("email", flat=True))
        to_create = []
        for i in range(1, n + 1):
            email = f"student{i}@university.edu"
            if email not in existing_emails:
                to_create.append(Voter(email=email))
        Voter.objects.bulk_create(to_create, ignore_conflicts=True)
        voters = list(Voter.objects.filter(has_voted=False)[:n])
        self.stdout.write(f"  {len(voters)} eligible voters ready.")

        # ── 2. Issue tokens ───────────────────────────────────────────────
        self.stdout.write("Issuing tokens...")
        token_map = {}   # voter_id → raw_token
        issued = 0
        for voter in voters:
            try:
                raw = issue_token(voter)
                token_map[voter.id] = raw
                issued += 1
            except ValueError:
                pass   # already has token
        self.stdout.write(f"  {issued} tokens issued.")

        # ── 3. Cast votes ──────────────────────────────────────────────────
        self.stdout.write("Casting votes...")
        success = 0
        errors = 0
        for voter_id, raw_token in token_map.items():
            candidate = random.choice(candidates)
            try:
                receipt = submit_vote_v2(raw_token, candidate.id)
                success += 1
            except VoteError as e:
                errors += 1
                self.stderr.write(f"  VoteError voter_id={voter_id}: {e}")

        self.stdout.write(f"  {success} votes cast, {errors} errors.")

        # ── 4. Export ledger ───────────────────────────────────────────────
        ledger = build_ledger()
        out_path = pathlib.Path("audit_ledger.json")
        out_path.write_text(json.dumps(ledger, indent=2))
        self.stdout.write(f"  Ledger exported → {out_path.resolve()}")

        # ── 5. Print tally ─────────────────────────────────────────────────
        tally: dict[str, int] = {}
        for entry in ledger:
            name = entry["candidate_name"]
            tally[name] = tally.get(name, 0) + 1

        self.stdout.write("\n── Final Tally ──────────────────────")
        for name, count in sorted(tally.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {name:<30} {count:>5} votes")
        self.stdout.write(f"  {'TOTAL':<30} {sum(tally.values()):>5}")
        self.stdout.write("─────────────────────────────────────\n")
        self.stdout.write("Done. Run `python manage.py verify_audit` to check chain integrity.")