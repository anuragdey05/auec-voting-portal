"""
voting/management/commands/simulate_votes.py

Creates N voters, issues tokens for their eligible races, casts randomized ballots,
exports the decoupled ledger, and displays verified tallies.

Run: python manage.py simulate_votes [--voters 100] [--reset]
"""

import random
import pathlib
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User

from voting.models import Voter, Candidate, VotingToken, Vote, Race
from voting.services import issue_token_for_race, submit_ballot, VoteError, build_ledger


class Command(BaseCommand):
    help = "Simulate N voters casting ballots end-to-end"

    def add_arguments(self, parser):
        parser.add_argument("--voters", type=int, default=100)
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Wipe all votes/tokens/voters before running.",
        )

    def handle(self, *args, **options):
        n = options["voters"]

        if options["reset"]:
            self.stdout.write("Resetting data...")
            with transaction.atomic():
                Vote.objects.all().delete()
                VotingToken.objects.all().delete()
                for v in Voter.objects.all():
                    v.has_voted_races.clear()

        races = list(Race.objects.filter(is_active=True).prefetch_related("candidates"))
        if not races:
            self.stderr.write("No active races found. Run: python manage.py seed_data")
            return

        # ── 1. Create voters ──────────────────────────────────────────────
        self.stdout.write(f"Creating / ensuring {n} simulation voters...")
        voters = []
        for i in range(1, n + 1):
            email = f"sim_student_{i}_ug2026@ashoka.edu.in"
            user, _ = User.objects.get_or_create(username=f"sim_{i}", email=email)
            voter, _ = Voter.objects.get_or_create(user=user, defaults={"email": email})
            # Ensure eligible for races
            voter.eligible_races.set(races)
            voters.append(voter)
        self.stdout.write(f"  {len(voters)} eligible voters ready.")

        # ── 2. Cast ballots across races ──────────────────────────────────
        self.stdout.write("Casting simulated ballots across eligible races...")
        success = 0
        errors = 0

        for voter in voters:
            for race in list(voter.remaining_races()):
                try:
                    raw_token = issue_token_for_race(voter, race)
                except ValueError as e:
                    continue

                cands = [c for c in race.candidates.all() if not c.is_nota]
                nota = [c for c in race.candidates.all() if c.is_nota]

                # Random choice: 10% chance NOTA, 90% candidate(s)
                if nota and random.random() < 0.10:
                    selections = [nota[0].candidate_ref_id]
                else:
                    k = random.randint(1, min(race.max_votes, len(cands)))
                    selected_cands = random.sample(cands, k)
                    selections = [c.candidate_ref_id for c in selected_cands]

                try:
                    submit_ballot(raw_token, race.race_id, selections)
                    success += 1
                except VoteError as e:
                    errors += 1
                    self.stderr.write(f"  VoteError race={race.race_id}: {e}")

        self.stdout.write(f"  {success} ballots recorded, {errors} errors.")

        # ── 3. Export decoupled ledger ────────────────────────────────────
        ledger = build_ledger()
        out_path = pathlib.Path("audit_ledger.json")
        out_path.write_text(json.dumps(ledger, indent=2))
        self.stdout.write(
            f"  Decoupled ledger exported → {out_path.resolve()}\n"
            f"  • {len(ledger['receipts_ledger'])} ballots in receipts ledger\n"
            f"  • {len(ledger['shuffled_votes'])} votes in shuffled pool"
        )
        self.stdout.write("\nDone. Run `python manage.py verify_audits` to check chain integrity.")