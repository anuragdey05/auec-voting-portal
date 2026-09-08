"""
voting/management/commands/verify_audit.py

Loads audit_ledger.json and:
  1. Recomputes the hash chain from GENESIS
  2. Verifies every stored hash_chain matches
  3. Verifies all receipts are unique
  4. Prints the final tally

Run: python manage.py verify_audit [--ledger audit_ledger.json]
"""

import json
import pathlib
import hashlib
from django.core.management.base import BaseCommand


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = "Verify hash-chain integrity and receipt uniqueness of the exported ledger."

    def add_arguments(self, parser):
        parser.add_argument("--ledger", default="audit_ledger.json")

    def handle(self, *args, **options):
        path = pathlib.Path(options["ledger"])
        if not path.exists():
            self.stderr.write(f"Ledger file not found: {path}")
            return

        ledger = json.loads(path.read_text())
        self.stdout.write(f"Loaded {len(ledger)} entries from {path}\n")

        errors = []
        prev_hash = "GENESIS"
        receipts = []
        tally: dict[str, int] = {}

        for i, entry in enumerate(ledger):
            # ── Recompute chain hash ──────────────────────────────────────
            payload = (
                f"{entry['token_hash']}|"
                f"{entry['candidate_id']}|"
                f"{entry['timestamp']}|"
                f"{prev_hash}"
            )
            expected = sha256(payload)

            if expected != entry["hash_chain"]:
                errors.append(
                    f"  [entry {i}] CHAIN MISMATCH: "
                    f"expected {expected[:16]}… got {entry['hash_chain'][:16]}…"
                )

            # ── Recompute receipt ─────────────────────────────────────────
            expected_receipt = sha256(f"{entry['token_hash']}|{entry['candidate_id']}")
            if expected_receipt != entry["receipt"]:
                errors.append(
                    f"  [entry {i}] RECEIPT MISMATCH: "
                    f"expected {expected_receipt[:16]}… got {entry['receipt'][:16]}…"
                )

            receipts.append(entry["receipt"])
            prev_hash = entry["hash_chain"]
            name = entry["candidate_name"]
            tally[name] = tally.get(name, 0) + 1

        # ── Check receipt uniqueness ──────────────────────────────────────
        if len(receipts) != len(set(receipts)):
            errors.append("  DUPLICATE RECEIPTS DETECTED — possible double-vote.")

        # ── Report ────────────────────────────────────────────────────────
        if errors:
            self.stdout.write("── AUDIT RESULT: FAIL ───────────────────")
            for e in errors:
                self.stdout.write(e)
        else:
            self.stdout.write("── AUDIT RESULT: PASS ───────────────────")
            self.stdout.write(f"  Chain intact across {len(ledger)} votes.")
            self.stdout.write(f"  All {len(receipts)} receipts unique.")

        self.stdout.write("\n── Tally ─────────────────────────────────")
        for name, count in sorted(tally.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {name:<30} {count:>5} votes")
        self.stdout.write(f"  {'TOTAL':<30} {sum(tally.values()):>5}")
        self.stdout.write("──────────────────────────────────────────\n")