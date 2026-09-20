"""
voting/management/commands/export_ledger.py

Exports the full audit ledger to audit_ledger.json.
Contains no user-identifiable fields.

Run: python manage.py export_ledger [--output myfile.json]
"""

import json
import pathlib
from django.core.management.base import BaseCommand
from voting.services import build_ledger


class Command(BaseCommand):
    help = "Export the decoupled audit ledger to a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="audit_ledger.json")

    def handle(self, *args, **options):
        ledger = build_ledger()
        out_path = pathlib.Path(options["output"])
        out_path.write_text(json.dumps(ledger, indent=2))
        num_ballots = len(ledger.get("receipts_ledger", []))
        num_votes   = len(ledger.get("shuffled_votes", []))
        self.stdout.write(
            f"Exported decoupled audit ledger → {out_path.resolve()}\n"
            f"  • {num_ballots} ballots in receipts ledger (proof of inclusion)\n"
            f"  • {num_votes} votes in shuffled pool (anonymized tallies)"
        )