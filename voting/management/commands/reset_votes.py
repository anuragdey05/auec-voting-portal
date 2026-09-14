from django.core.management.base import BaseCommand
from django.db import transaction
from voting.models import Vote, VotingToken, Voter


class Command(BaseCommand):
    help = "Clears all cast votes and issued tokens for test re-runs."

    def handle(self, *args, **options):
        with transaction.atomic():
            num_votes, _ = Vote.objects.all().delete()
            num_tokens, _ = VotingToken.objects.all().delete()
            for voter in Voter.objects.all():
                voter.has_voted_races.clear()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully reset test data: {num_votes} votes deleted, {num_tokens} tokens cleared, all voters reset to unvoted state."
            )
        )
