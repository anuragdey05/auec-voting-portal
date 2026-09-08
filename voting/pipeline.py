"""
voting/pipeline.py

Custom social-auth pipeline step, runs after the Django User is created/found.

Responsibilities:
  1. Reject emails not from the allowed domain (defence-in-depth; the
     WHITELISTED_DOMAINS setting already blocks at OAuth level).
  2. Create or update the Voter profile linked to the Django User.
  3. Assign eligible_races based on email suffix.
  4. Preserve the 'auec_admin' role if already set (prevents demotion on re-login).
"""

import logging
from django.conf import settings
from social_core.exceptions import AuthForbidden

from .models import Voter
from .eligibility import get_eligible_race_ids

logger = logging.getLogger("voting")


def provision_voter(backend, user, response, *args, **kwargs):
    """
    Called by social-auth after user creation/login.
    `user` is a Django auth.User instance.
    """
    email = (user.email or "").lower().strip()
    allowed_domain = getattr(settings, "ALLOWED_EMAIL_DOMAIN", "ashoka.edu.in")

    # ── Domain guard ──────────────────────────────────────────────────────────
    if not email.endswith(f"@{allowed_domain}"):
        logger.warning("Blocked OAuth login from disallowed domain: %s", email)
        raise AuthForbidden(backend)

    # ── Fetch or create Voter profile ─────────────────────────────────────────
    voter, created = Voter.objects.get_or_create(
        user=user,
        defaults={"email": email, "role": Voter.ROLE_STUDENT},
    )

    if not created:
        # Update email in case it changed (unlikely but safe)
        if voter.email != email:
            voter.email = email
            voter.save(update_fields=["email"])

    # ── Assign eligible races (always refresh in case mapping changes) ────────
    from voting.models import Race
    race_ids = get_eligible_race_ids(email)
    eligible = Race.objects.filter(race_id__in=race_ids, is_active=True)
    voter.eligible_races.set(eligible)

    action = "created" if created else "updated"
    logger.info("Voter %s (%s). Role=%s. Eligible races=%s",
                action, voter.id, voter.role, race_ids)