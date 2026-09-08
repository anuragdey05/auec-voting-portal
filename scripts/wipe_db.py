from voting.models import Vote, VotingToken, Voter, Candidate, Race
from django.contrib.auth.models import User
from django.db import transaction
with transaction.atomic():
    Vote.objects.all().delete()
    VotingToken.objects.all().delete()
    Voter.objects.all().delete()
    User.objects.all().delete()
    Candidate.objects.all().delete()
    Race.objects.all().delete()
    
print('Wiped.')
