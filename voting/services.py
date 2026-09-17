"""
voting/services.py  v3

Multi-vote + NOTA rules:
- max_votes=1 races (President, GenSec): exactly 1 candidate OR NOTA.
- max_votes=N races (councils): 1..N candidates OR NOTA (not both).
- NOTA exclusivity: if any vote for a token+race is NOTA, no other votes allowed.
- submit_ballot() accepts a list of candidate_ref_ids in one atomic call.
  Each produces one Vote row. The token is marked used after all rows inserted.
- Unique voter count = COUNT(DISTINCT token_hash) per race.
- Election window enforcement delegated to voting.timeline.
"""
import pytz
import hashlib
import hmac
import secrets
import logging
from collections import defaultdict
from django.db import transaction, IntegrityError
from django.utils import timezone
from datetime import datetime
from .models import Race, Candidate, Voter, VotingToken, Vote
from .timeline import require_active_election

logger = logging.getLogger("voting")


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _get_previous_hash(race: Race) -> str:
    last = Vote.objects.filter(race=race).order_by("-id").first()
    return last.hash_chain if last else "GENESIS"


def compute_hash_chain(token_hash, candidate_ref_id, race_id, timestamp_iso, prev_hash):
    payload = f"{token_hash}|{candidate_ref_id}|{race_id}|{timestamp_iso}|{prev_hash}"
    return sha256(payload)


def compute_receipt(token_hash: str, race_id: str, candidate_ref_ids: list[int]) -> str:
    """
    Receipt covers the full ballot (all selected candidates) for a race.
    Sorted so order doesn't matter.
    """
    ids_str = ",".join(str(i) for i in sorted(candidate_ref_ids))
    return sha256(f"{token_hash}|{race_id}|{ids_str}")


# ── Token issuance ─────────────────────────────────────────────────────────────

def issue_token_for_race(voter: Voter, race: Race) -> str:
    require_active_election()
    with transaction.atomic():
        v = Voter.objects.select_for_update().get(id=voter.id)
        if not v.eligible_races.filter(id=race.id).exists():
            raise ValueError(f"Not eligible for: {race.race_name}")
        if v.has_voted_races.filter(id=race.id).exists():
            raise ValueError(f"Already voted in: {race.race_name}")
        existing = VotingToken.objects.filter(voter=v, race=race, used=False).first()
        if existing:
            raise ValueError("Token already issued for this race.")

        raw_token  = secrets.token_urlsafe(32)
        token_hash = sha256(raw_token)
        try:
            VotingToken.objects.create(token_hash=token_hash, voter=v, race=race)
        except IntegrityError:
            raise ValueError("Token already issued for this race.")

    logger.info("Token issued. voter_id=%d race=%s", voter.id, race.race_id)
    return raw_token


class VoteError(Exception):
    pass


# ── Ballot submission ──────────────────────────────────────────────────────────



def submit_ballot(raw_token: str, race_id: str, candidate_ref_ids: list[int]) -> str:
    """
    Submit a complete ballot for one race.

    candidate_ref_ids: list of candidate_ref_id values selected by the voter.
      - Must have 1..max_votes entries, OR exactly [nota_ref_id].
      - If nota_ref_id is in the list, it must be the ONLY entry.

    Returns receipt hash covering the full ballot.
    All Vote rows inserted atomically; token marked used on commit.
    """
    if not candidate_ref_ids:
        raise VoteError("No candidates selected.")
    
    require_active_election()

    token_hash = sha256(raw_token)

    with transaction.atomic():
        # ── Lock token row ────────────────────────────────────────────────
        try:
            token = (VotingToken.objects
                     .select_for_update()
                     .select_related("race")
                     .get(token_hash=token_hash))
        except VotingToken.DoesNotExist:
            raise VoteError("Invalid token.")

        if token.used:
            raise VoteError("Token already used.")

        if token.race.race_id != race_id:
            raise VoteError("Token is not valid for this race.")

        try:
            # Row lock on Race serializes hash chain computation per race, preventing forks
            race = Race.objects.select_for_update().get(race_id=race_id, is_active=True)
        except Race.DoesNotExist:
            raise VoteError("Race not found or not active.")

        # ── NOTA check ────────────────────────────────────────────────────
        is_nota_ballot = (len(candidate_ref_ids) == 1 and
                          candidate_ref_ids[0] == race.nota_ref_id)

        if not is_nota_ballot:
            # Ensure NOTA is not mixed with real candidates
            if race.nota_ref_id in candidate_ref_ids:
                raise VoteError("NOTA cannot be combined with other candidates.")
            if len(candidate_ref_ids) > race.max_votes:
                raise VoteError(
                    f"Too many candidates selected. Maximum for this race: {race.max_votes}."
                )
            if len(candidate_ref_ids) != len(set(candidate_ref_ids)):
                raise VoteError("Duplicate candidates in selection.")

        # ── Resolve candidates ────────────────────────────────────────────
        candidates = []
        for ref_id in candidate_ref_ids:
            try:
                candidates.append(Candidate.objects.get(race=race, candidate_ref_id=ref_id))
            except Candidate.DoesNotExist:
                raise VoteError(f"Candidate {ref_id} not found in race {race_id}.")

        if not token.voter_id:
            raise VoteError("Invalid token state.")
        voter_id = token.voter_id   # capture before null
        now      = timezone.now()

        # ── Insert one Vote row per candidate ─────────────────────────────
        for candidate in candidates:
            prev_hash  = _get_previous_hash(race)
            chain_hash = compute_hash_chain(
                token_hash, candidate.candidate_ref_id,
                race.race_id, now.isoformat(), prev_hash,
            )
            try:
                Vote.objects.create(
                    token_hash=token_hash,
                    candidate=candidate,
                    race=race,
                    is_nota=candidate.is_nota,
                    timestamp=now,
                    hash_chain=chain_hash,
                )
            except IntegrityError:
                raise VoteError("Duplicate vote detected.")

        # ── Mark token used, privacy unlink ──────────────────────────────
        token.used         = True
        token.used_at      = now
        token.ballot_count = len(candidates)
        token.voter        = None   # PRIVACY UNLINK
        token.save(update_fields=["used", "used_at", "ballot_count", "voter"])

        if voter_id:
            Voter.objects.get(id=voter_id).has_voted_races.add(race)

    logger.info("Ballot recorded. race=%s selections=%d nota=%s",
                race_id, len(candidates), is_nota_ballot)
    return compute_receipt(token_hash, race_id, candidate_ref_ids)


# ── Results + unique voter count ───────────────────────────────────────────────

def get_results(race_id: str | None = None):
    """
    Returns tallies per race including unique_voters count.
    unique_voters = COUNT(DISTINCT token_hash) — privacy-safe, no user data.
    """
    from django.db.models import Count

    qs = Vote.objects.select_related("candidate", "race")
    if race_id:
        qs = qs.filter(race__race_id=race_id)

    tally = (
        qs.values(
            "race__race_id", "race__race_name", "race__max_votes",
            "candidate__candidate_ref_id", "candidate__name",
            "candidate__affiliation", "candidate__is_nota",
        )
        .annotate(count=Count("id"))
        .order_by("race__race_id", "candidate__is_nota", "-count")
    )

    # Unique voter count per race
    unique_voters_qs = (
        Vote.objects
        .values("race__race_id")
        .annotate(unique_voters=Count("token_hash", distinct=True))
    )
    unique_map = {row["race__race_id"]: row["unique_voters"] for row in unique_voters_qs}

    races: dict = {}
    for row in tally:
        rid = row["race__race_id"]
        if rid not in races:
            races[rid] = {
                "race_id":      rid,
                "race_name":    row["race__race_name"],
                "max_votes":    row["race__max_votes"],
                "unique_voters": unique_map.get(rid, 0),
                "candidates":   [],
            }
        races[rid]["candidates"].append({
            "candidate_ref_id": row["candidate__candidate_ref_id"],
            "name":        row["candidate__name"],
            "affiliation": row["candidate__affiliation"],
            "is_nota":     row["candidate__is_nota"],
            "votes":       row["count"],
        })

    return list(races.values())


# ── Ledger + receipt ───────────────────────────────────────────────────────────

def build_ledger(race_id: str | None = None) -> list[dict]:
    qs = Vote.objects.select_related("candidate", "race").order_by("id")
    if race_id:
        qs = qs.filter(race__race_id=race_id)
    entries = []
    for vote in qs:
        entries.append({
            "vote_id":           vote.id,
            "race_id":           vote.race.race_id,
            "race_name":         vote.race.race_name,
            "candidate_ref_id":  vote.candidate.candidate_ref_id,
            "candidate_name":    vote.candidate.name,
            "is_nota":           vote.is_nota,
            "token_hash":        vote.token_hash,
            "timestamp":         vote.timestamp.isoformat(),
            "hash_chain":        vote.hash_chain,
        })
    return entries


def verify_receipt(receipt_hash: str) -> bool:
    """
    Verify receipt by recomputing for every distinct (token_hash, race) group.
    Runs a single query and groups in-memory to prevent N+1 query Denial-of-Service.
    Uses constant-time comparison to mitigate timing side channels.
    """
    qs = (
        Vote.objects
        .values("token_hash", "race__race_id", "candidate__candidate_ref_id")
        .order_by("token_hash", "race__race_id")
    )
    ballots = defaultdict(list)
    for row in qs:
        key = (row["token_hash"], row["race__race_id"])
        ballots[key].append(row["candidate__candidate_ref_id"])

    for (th, rid), ref_ids in ballots.items():
        computed = compute_receipt(th, rid, ref_ids)
        if hmac.compare_digest(computed, receipt_hash):
            return True
    return False