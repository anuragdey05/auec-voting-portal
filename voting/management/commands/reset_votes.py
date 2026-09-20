from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.sessions.models import Session
from voting.models import Vote, VotingToken, Voter


class Command(BaseCommand):
    help = "Clears all cast votes, issued tokens, voter completion states, and active sessions before the election."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-sessions",
            action="store_true",
            help="Do not clear active user login sessions.",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            num_votes, _ = Vote.objects.all().delete()
            num_tokens, _ = VotingToken.objects.all().delete()
            for voter in Voter.objects.all():
                voter.has_voted_races.clear()

            num_sessions = 0
            if not options.get("keep_sessions"):
                num_sessions, _ = Session.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully reset election data:\n"
                f"  • {num_votes} votes deleted (hash chain reset to GENESIS)\n"
                f"  • {num_tokens} tokens deleted\n"
                f"  • {Voter.objects.count()} voters reset to unvoted state\n"
                f"  • {num_sessions} active sessions cleared"
            )
        )
