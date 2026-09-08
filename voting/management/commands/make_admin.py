"""
voting/management/commands/make_admin.py

Promote a voter to AUEC admin by email.

Usage:
    python manage.py make_admin admin@ashoka.edu.in
"""

from django.core.management.base import BaseCommand
from voting.models import Voter


class Command(BaseCommand):
    help = "Promote a voter to AUEC admin role."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str)

    def handle(self, *args, **options):
        email = options["email"].lower().strip()
        try:
            voter = Voter.objects.get(email=email)
        except Voter.DoesNotExist:
            self.stderr.write(
                f"No voter found with email: {email}\n"
                "They must log in via Google OAuth at least once before being promoted."
            )
            return
        voter.role = Voter.ROLE_AUEC_ADMIN
        voter.save(update_fields=["role"])
        self.stdout.write(f"✓ {email} is now an AUEC admin.")