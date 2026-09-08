from django.urls import path
from . import views

urlpatterns = [
    path("login/",          views.login_view,          name="login"),
    path("issue-token/",    views.issue_token_view,    name="issue_token"),
    path("vote/",           views.vote_view,            name="vote"),
    path("verify-receipt/", views.verify_receipt_view, name="verify_receipt"),
    path("results/",        views.results_view,         name="results"),
]