from django.test import TestCase
from django.contrib.auth.models import User
from django.core.management import call_command
import json
import io

from voting.models import Race, Candidate, Voter, VotingToken, Vote
from voting.services import (
    issue_token_for_race, submit_ballot, build_ledger, verify_receipt, VoteError
)


class DecoupledLedgerTests(TestCase):
    def setUp(self):
        # Create test race 1 (single-vote: President)
        self.pres_race = Race.objects.create(
            race_id="president",
            race_name="Student Body President",
            is_active=True,
            max_votes=1,
            nota_ref_id=999,
        )
        self.p_cand1 = Candidate.objects.create(race=self.pres_race, candidate_ref_id=1, name="Candidate One")
        self.p_cand2 = Candidate.objects.create(race=self.pres_race, candidate_ref_id=2, name="Candidate Two")
        self.p_nota  = Candidate.objects.create(race=self.pres_race, candidate_ref_id=999, name="None of the Above", is_nota=True)

        # Create test race 2 (multi-vote: 1st Year Council, max 4)
        self.counc_race = Race.objects.create(
            race_id="council_1st_year",
            race_name="1st Year Student Council",
            is_active=True,
            max_votes=4,
            nota_ref_id=999,
        )
        self.c_cand1 = Candidate.objects.create(race=self.counc_race, candidate_ref_id=10, name="Council Alice")
        self.c_cand2 = Candidate.objects.create(race=self.counc_race, candidate_ref_id=11, name="Council Bob")
        self.c_cand3 = Candidate.objects.create(race=self.counc_race, candidate_ref_id=12, name="Council Charlie")
        self.c_cand4 = Candidate.objects.create(race=self.counc_race, candidate_ref_id=13, name="Council Diana")
        self.c_nota  = Candidate.objects.create(race=self.counc_race, candidate_ref_id=999, name="None of the Above", is_nota=True)

        # Create voters
        self.voters = []
        for i in range(1, 4):
            user = User.objects.create_user(username=f"student{i}", email=f"student{i}_ug2026@ashoka.edu.in")
            voter = Voter.objects.create(user=user, email=user.email)
            voter.eligible_races.add(self.pres_race, self.counc_race)
            self.voters.append(voter)

    def test_ballot_submission_and_hash_chaining(self):
        # Voter 1 votes for President (Candidate 1)
        token1 = issue_token_for_race(self.voters[0], self.pres_race)
        receipt1 = submit_ballot(token1, "president", [1])
        self.assertEqual(len(receipt1), 64)
        self.assertTrue(verify_receipt(receipt1))

        # Check Vote row
        vote1 = Vote.objects.filter(race=self.pres_race).first()
        self.assertIsNotNone(vote1)
        self.assertEqual(len(vote1.hash_chain), 64)

        # Voter 2 votes for President (Candidate 2)
        token2 = issue_token_for_race(self.voters[1], self.pres_race)
        receipt2 = submit_ballot(token2, "president", [2])
        self.assertNotEqual(receipt1, receipt2)
        self.assertTrue(verify_receipt(receipt2))

        # Voter 3 votes for President (NOTA)
        token3 = issue_token_for_race(self.voters[2], self.pres_race)
        receipt3 = submit_ballot(token3, "president", [999])
        self.assertTrue(verify_receipt(receipt3))

        # Voter 1 votes for Council (Multi-candidate: 10, 11, 12)
        token_c1 = issue_token_for_race(self.voters[0], self.counc_race)
        receipt_c1 = submit_ballot(token_c1, "council_1st_year", [10, 11, 12])
        self.assertTrue(verify_receipt(receipt_c1))

        # Multi-vote should create 3 Vote rows with the exact same chain_hash
        c_votes = list(Vote.objects.filter(race=self.counc_race))
        self.assertEqual(len(c_votes), 3)
        self.assertEqual(c_votes[0].hash_chain, c_votes[1].hash_chain)
        self.assertEqual(c_votes[1].hash_chain, c_votes[2].hash_chain)

    def test_decoupled_ledger_structure(self):
        # Cast ballots
        t1 = issue_token_for_race(self.voters[0], self.pres_race)
        submit_ballot(t1, "president", [1])

        t2 = issue_token_for_race(self.voters[1], self.pres_race)
        submit_ballot(t2, "president", [2])

        t_c = issue_token_for_race(self.voters[0], self.counc_race)
        submit_ballot(t_c, "council_1st_year", [10, 11])

        ledger = build_ledger()
        self.assertIn("receipts_ledger", ledger)
        self.assertIn("shuffled_votes", ledger)
        self.assertIn("tallies", ledger)

        receipts_ledger = ledger["receipts_ledger"]
        shuffled_votes = ledger["shuffled_votes"]

        # 3 ballots total: 2 in President, 1 in Council
        self.assertEqual(len(receipts_ledger), 3)
        # 4 total votes: 2 in President, 2 in Council
        self.assertEqual(len(shuffled_votes), 4)

        # CRITICAL TEST: Ensure NO candidate info or token_hash exists in receipts_ledger
        for entry in receipts_ledger:
            self.assertNotIn("candidate_name", entry)
            self.assertNotIn("candidate_ref_id", entry)
            self.assertNotIn("token_hash", entry)
            self.assertIn("receipt", entry)
            self.assertIn("hash_chain", entry)
            self.assertIn("race_id", entry)
            self.assertIn("timestamp", entry)

        # CRITICAL TEST: Ensure NO receipts or timestamps exist in shuffled_votes
        for entry in shuffled_votes:
            self.assertNotIn("receipt", entry)
            self.assertNotIn("timestamp", entry)
            self.assertNotIn("token_hash", entry)
            self.assertNotIn("hash_chain", entry)
            self.assertIn("candidate_name", entry)
            self.assertIn("candidate_ref_id", entry)

    def test_verify_audits_command(self):
        # Cast votes
        t1 = issue_token_for_race(self.voters[0], self.pres_race)
        submit_ballot(t1, "president", [1])
        t2 = issue_token_for_race(self.voters[1], self.pres_race)
        submit_ballot(t2, "president", [2])

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w+", delete=False) as f:
            ledger = build_ledger()
            json.dump(ledger, f)
            temp_path = f.name

        out = io.StringIO()
        call_command("verify_audits", ledger=temp_path, stdout=out)
        output = out.getvalue()

        self.assertIn("AUDIT RESULT: PASS", output)
        self.assertIn("All 2 receipts unique", output)
        self.assertIn("Hash chains intact", output)
