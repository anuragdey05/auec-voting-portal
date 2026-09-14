from django.urls import path, include
from django.http import JsonResponse
from voting import views
import social_django.views
from social_core.actions import do_auth
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.views.decorators.cache import never_cache

# social-auth-app-django v5.3+ enforces POST on login, which causes 405 on standard <a> links.
# This view permits both GET and POST to start the OAuth flow seamlessly.
@never_cache
@social_django.views.psa("social:complete")
def social_login_view(request, backend):
    return do_auth(request.backend, redirect_name=REDIRECT_FIELD_NAME)

social_patterns = (
    [
        path("login/<str:backend>/", social_login_view, name="begin"),
        path("complete/<str:backend>/", social_django.views.complete, name="complete"),
        path("disconnect/<str:backend>/", social_django.views.disconnect, name="disconnect"),
    ],
    "social",
)

urlpatterns = [
    path("health/", lambda r: JsonResponse({"ok": True}), name="health"), # for railway deployment

    path("",                         views.index_view,          name="index"),
    path("logout/",                  views.logout_view,         name="logout"),
    path("auth/error/",              views.auth_error_view,     name="auth_error"),
    path("auth/",                    include(social_patterns, namespace="social")),

    # Voter-facing API
    path("api/me/",                  views.me_view,             name="me"),
    path("api/races/",               views.races_view,          name="races"),
    path("api/issue-token/",         views.issue_token_view,    name="issue_token"),
    path("api/vote/",                views.vote_view,           name="vote"),
    path("api/verify-receipt/",      views.verify_receipt_view, name="verify_receipt"),

    # AUEC admin API
    path("api/results/",             views.results_view,        name="results"),
    path("api/ledger/",              views.ledger_view,         name="ledger"),
]