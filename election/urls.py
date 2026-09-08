from django.urls import path, include
from django.http import JsonResponse
from voting import views

urlpatterns = [
    path("health/", lambda r: JsonResponse({"ok": True}), name="health"), # for railway deployment

    path("",                         views.index_view,          name="index"),
    path("logout/",                  views.logout_view,         name="logout"),
    path("auth/error/",              views.auth_error_view,     name="auth_error"),
    path("auth/",                    include("social_django.urls", namespace="social")),

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