"""
voting/views.py  v3 — uses submit_ballot (multi-vote + NOTA)
"""

import json
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout

from .models import Race
from .services import (
    VoteError, issue_token_for_race, submit_ballot,
    verify_receipt, get_results, build_ledger,
)
from .access import require_voter, require_student, require_auec_admin

logger = logging.getLogger("voting")


def _json(request) -> dict:
    try:
        return json.loads(request.body)
    except Exception:
        return {}

def _ok(data, status=200):  return JsonResponse({"ok": True,  **data}, status=status)
def _err(msg,  status=400):  return JsonResponse({"ok": False, "error": msg}, status=status)


# ── Pages ─────────────────────────────────────────────────────────────────────

def index_view(request):
    voter = None
    if request.user.is_authenticated:
        try:
            voter = request.user.voter_profile
        except Exception:
            pass
    return render(request, "index.html", {"voter": voter})

def auth_error_view(request):
    reason = request.GET.get("message", "Authentication failed.")
    return render(request, "auth_error.html", {"reason": reason})

def logout_view(request):
    logout(request)
    return redirect("/")


# ── API: voter info ───────────────────────────────────────────────────────────

@require_voter
def me_view(request):
    voter = request.voter
    return _ok({
        "email":           voter.email,
        "role":            voter.role,
        "eligible_races":  list(voter.eligible_races.values("race_id", "race_name")),
        "voted_races":     list(voter.has_voted_races.values("race_id", "race_name")),
        "remaining_races": list(voter.remaining_races().values("race_id", "race_name")),
    })


# ── API: races + candidates (includes unique voter count) ─────────────────────

@require_student
def races_view(request):
    voter     = request.voter
    races     = voter.eligible_races.filter(is_active=True).prefetch_related("candidates")
    voted_ids = set(voter.has_voted_races.values_list("race_id", flat=True))

    # Unique voter counts (public — count of distinct token_hashes, no user data)
    from django.db.models import Count
    uv_map = {
        row["race__race_id"]: row["uv"]
        for row in (
            __import__("voting.models", fromlist=["Vote"])
            .Vote.objects
            .values("race__race_id")
            .annotate(uv=Count("token_hash", distinct=True))
        )
    }

    data = []
    for race in races:
        regular = [c for c in race.candidates.all() if not c.is_nota]
        nota    = [c for c in race.candidates.all() if c.is_nota]
        def cand_dict(c):
            return {
                "candidate_ref_id": c.candidate_ref_id,
                "name":             c.name,
                "affiliation":      c.affiliation,
                "year":             c.year,
                "bio":              c.bio,
                "photo_initials":   c.photo_initials,
                "is_nota":          c.is_nota,
            }
        data.append({
            "race_id":       race.race_id,
            "race_name":     race.race_name,
            "max_votes":     race.max_votes,
            "nota_ref_id":   race.nota_ref_id,
            "voted":         race.race_id in voted_ids,
            "unique_voters": uv_map.get(race.race_id, 0),
            "candidates":    [cand_dict(c) for c in regular],
            "nota":          cand_dict(nota[0]) if nota else None,
        })
    return _ok({"races": data})


# ── API: issue token ──────────────────────────────────────────────────────────

@csrf_exempt
@require_student
@require_http_methods(["POST"])
def issue_token_view(request):
    data    = _json(request)
    race_id = (data.get("race_id") or "").strip()
    if not race_id:
        return _err("race_id is required.")
    try:
        race = Race.objects.get(race_id=race_id, is_active=True)
    except Race.DoesNotExist:
        return _err("Race not found.")
    try:
        raw_token = issue_token_for_race(request.voter, race)
    except (ValueError, VoteError) as e:
        return _err(str(e), status=409)
    return _ok({"token": raw_token, "race_id": race_id})


# ── API: vote (ballot submission) ─────────────────────────────────────────────

@csrf_exempt
@require_student
@require_http_methods(["POST"])
def vote_view(request):
    """
    Body: { token, race_id, candidate_ref_ids: [int, ...] }
    candidate_ref_ids can be 1..max_votes regular candidates, OR [nota_ref_id].
    """
    data              = _json(request)
    raw_token         = (data.get("token") or "").strip()
    race_id           = (data.get("race_id") or "").strip()
    candidate_ref_ids = data.get("candidate_ref_ids", [])

    if not raw_token:          return _err("token is required.")
    if not race_id:            return _err("race_id is required.")
    if not isinstance(candidate_ref_ids, list) or not candidate_ref_ids:
        return _err("candidate_ref_ids must be a non-empty list.")

    try:
        candidate_ref_ids = [int(x) for x in candidate_ref_ids]
    except (TypeError, ValueError):
        return _err("candidate_ref_ids must be integers.")

    try:
        receipt = submit_ballot(raw_token, race_id, candidate_ref_ids)
    except VoteError as e:
        return _err(str(e), status=409)

    return _ok({"message": "Ballot recorded.", "receipt": receipt, "race_id": race_id})


# ── API: verify receipt ────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def verify_receipt_view(request):
    data    = _json(request)
    receipt = (data.get("receipt") or "").strip().lower()
    if len(receipt) != 64:
        return _err("receipt must be a 64-character hex SHA256 hash.")
    return _ok({"found": verify_receipt(receipt)})


# ── API: results (AUEC admin only) ────────────────────────────────────────────

@require_auec_admin
def results_view(request):
    race_id = request.GET.get("race_id")
    return _ok({"results": get_results(race_id or None)})


# ── API: ledger (AUEC admin only) ─────────────────────────────────────────────

@require_auec_admin
def ledger_view(request):
    race_id = request.GET.get("race_id")
    ledger  = build_ledger(race_id or None)
    return _ok({"ledger": ledger, "count": len(ledger)})

#triggering redeploy