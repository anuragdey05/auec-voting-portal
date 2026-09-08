"""
voting/models.py

v3 changes:
- Race.max_votes: max candidates selectable per race (1 for President/GenSec, 4 for councils)
- Race.nota_ref_id: the candidate_ref_id that represents NOTA in this race
- Vote unique constraint is now (token_hash, candidate) — allows multiple votes per token per race
- VotingToken.ballot_count: how many individual vote rows have been cast with this token
- NOTA exclusivity enforced in services.py (not at DB level — business logic)
- Unique voter count derived from distinct token_hashes per race (privacy-preserving)
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Race(models.Model):
    race_id      = models.CharField(max_length=64, unique=True, db_index=True)
    race_name    = models.CharField(max_length=255)
    is_active    = models.BooleanField(default=True)
    max_votes    = models.IntegerField(default=1)   # max candidates selectable (excl. NOTA)
    nota_ref_id  = models.IntegerField(default=999) # candidate_ref_id reserved for NOTA

    class Meta:
        db_table = "races"

    def __str__(self):
        return self.race_name


class Candidate(models.Model):
    race             = models.ForeignKey(Race, on_delete=models.PROTECT, related_name="candidates")
    candidate_ref_id = models.IntegerField(db_index=True)
    name             = models.CharField(max_length=255)
    affiliation      = models.CharField(max_length=255, blank=True)
    year             = models.CharField(max_length=32, blank=True)
    bio              = models.TextField(blank=True)
    manifesto_url    = models.URLField(blank=True)
    photo_initials   = models.CharField(max_length=4, blank=True)
    is_nota          = models.BooleanField(default=False)

    class Meta:
        db_table = "candidates"
        unique_together = [("race", "candidate_ref_id")]

    def __str__(self):
        return f"{self.name} ({self.race.race_name})"


class Voter(models.Model):
    ROLE_STUDENT    = "student"
    ROLE_AUEC_ADMIN = "auec_admin"
    ROLE_CHOICES = [
        (ROLE_STUDENT,    "Student"),
        (ROLE_AUEC_ADMIN, "AUEC Admin"),
    ]

    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name="voter_profile")
    email           = models.EmailField(unique=True, db_index=True)
    role            = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    eligible_races  = models.ManyToManyField(Race, related_name="eligible_voters", blank=True)
    has_voted_races = models.ManyToManyField(Race, related_name="completed_voters", blank=True)
    created_at      = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "voters"

    @property
    def is_admin(self):
        return self.role == self.ROLE_AUEC_ADMIN

    def remaining_races(self):
        voted_ids = self.has_voted_races.values_list("id", flat=True)
        return self.eligible_races.filter(is_active=True).exclude(id__in=voted_ids)

    def __str__(self):
        return f"{self.email} [{self.role}]"


class VotingToken(models.Model):
    token_hash  = models.CharField(max_length=64, unique=True, db_index=True)
    voter       = models.ForeignKey(
        Voter,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="voting_tokens",
        db_column="voter_id",
    )
    race        = models.ForeignKey(Race, on_delete=models.PROTECT, related_name="tokens")
    used        = models.BooleanField(default=False)
    ballot_count = models.IntegerField(default=0)  # votes cast with this token
    issued_at   = models.DateTimeField(default=timezone.now)
    used_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "voting_tokens"
        constraints = [
            models.UniqueConstraint(
                fields=["voter", "race"],
                condition=models.Q(used=False),
                name="unique_active_token_per_voter_race",
            )
        ]

    def __str__(self):
        return f"Token:{self.token_hash[:12]}... race={self.race_id} used={self.used}"


class Vote(models.Model):
    """
    One row per candidate selected. A multi-vote ballot produces multiple rows
    sharing the same token_hash. NOTA produces exactly one row with is_nota=True.

    Unique constraint: (token_hash, candidate) — one vote per candidate per token.
    NOTA exclusivity (cannot coexist with other votes for same token+race) is
    enforced in services.py inside the atomic transaction.

    Unique voter count = COUNT(DISTINCT token_hash) per race — privacy-safe.
    """
    token_hash = models.CharField(max_length=64, db_index=True)
    candidate  = models.ForeignKey(Candidate, on_delete=models.PROTECT, related_name="votes")
    race       = models.ForeignKey(Race, on_delete=models.PROTECT, related_name="votes")
    is_nota    = models.BooleanField(default=False)
    timestamp  = models.DateTimeField(default=timezone.now)
    hash_chain = models.CharField(max_length=64)

    class Meta:
        db_table = "votes"
        constraints = [
            # One vote per candidate per token (prevents double-voting same candidate)
            models.UniqueConstraint(
                fields=["token_hash", "candidate"],
                name="unique_vote_per_token_candidate",
            )
        ]

    def __str__(self):
        nota = " [NOTA]" if self.is_nota else ""
        return f"Vote:{self.hash_chain[:12]}...{nota} -> {self.candidate.name} [{self.race.race_name}]"