"""
voting/access.py

Reusable access-control decorators for views.

Usage:
    @require_voter          — must be logged in and have a Voter profile
    @require_student        — must be a student (not admin)
    @require_auec_admin     — must be AUEC admin
"""

import functools
from django.shortcuts import redirect
from django.http import JsonResponse


def _get_voter(request):
    """Return Voter profile for the logged-in user, or None."""
    if not request.user.is_authenticated:
        return None
    try:
        return request.user.voter_profile
    except Exception:
        return None


def require_voter(view_fn):
    """Require any authenticated voter (student or admin)."""
    @functools.wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        voter = _get_voter(request)
        if voter is None:
            if request.headers.get("Accept", "").startswith("application/json") or \
               request.path.startswith("/api/"):
                return JsonResponse({"ok": False, "error": "Authentication required."}, status=401)
            return redirect("/auth/login/google-oauth2/")
        request.voter = voter
        return view_fn(request, *args, **kwargs)
    return wrapper


def require_student(view_fn):
    """Require an authenticated student (not admin)."""
    @functools.wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        voter = _get_voter(request)
        if voter is None:
            if request.path.startswith("/api/"):
                return JsonResponse({"ok": False, "error": "Authentication required."}, status=401)
            return redirect("/auth/login/google-oauth2/")
        if voter.is_admin:
            if request.path.startswith("/api/"):
                return JsonResponse({"ok": False, "error": "Admins cannot vote."}, status=403)
            return redirect("/?error=admins_cannot_vote")
        request.voter = voter
        return view_fn(request, *args, **kwargs)
    return wrapper


def require_auec_admin(view_fn):
    """Require AUEC admin role."""
    @functools.wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        voter = _get_voter(request)
        if voter is None:
            if request.path.startswith("/api/"):
                return JsonResponse({"ok": False, "error": "Authentication required."}, status=401)
            return redirect("/auth/login/google-oauth2/")
        if not voter.is_admin:
            if request.path.startswith("/api/"):
                return JsonResponse({"ok": False, "error": "AUEC admin access required."}, status=403)
            return redirect("/?error=forbidden")
        request.voter = voter
        return view_fn(request, *args, **kwargs)
    return wrapper