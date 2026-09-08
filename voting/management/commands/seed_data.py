"""
voting/management/commands/seed_data.py

Seeds races and candidates from JSON files.
Safe to run multiple times — uses update_or_create (idempotent).

Run: python manage.py seed_data
Called automatically by Railway's releaseCommand on every deploy.
"""

from django.core.management.base import BaseCommand
from voting.eligibility import seed_races_and_candidates


class Command(BaseCommand):
    help = "Seed races and candidates from JSON files (idempotent)."

    def handle(self, *args, **options):
        try:
            seed_races_and_candidates()
            self.stdout.write(self.style.SUCCESS("Races and candidates seeded successfully."))
        except Exception as e:
            self.stderr.write(f"Seeding error: {e}")
            raise