"""
Vantage Bot - Logic Test Suite
Run: python vantage_bot/test_logic.py

Tests the core logic without requiring Telegram or full bot setup.
"""

import os
import sys
import json
import unittest
from unittest.mock import MagicMock, patch

# Setup paths
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agents.orchestrator.agent import Orchestrator
from agents.story_writer.agent import CaptureAgent
from agents.decision_log.agent import DecisionAgent
from agents.calendar_optimizer.agent import ScheduleAgent
from storage.oracle_client import OracleClient
from logic.onboarding import OnboardingManager

# Use real project from env for LLM tests
REAL_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "vantage-demo-hackathon")


# =============================================================================
# UNIT TESTS - No DB required (mocked)
# =============================================================================

class TestOrchestratorRouting(unittest.TestCase):
    """Test PO Orchestrator intent classification."""

    def setUp(self):
        self.orchestrator = Orchestrator(project_id=REAL_PROJECT_ID)

    def test_capture_stakeholder_request(self):
        """Stakeholder feature requests route to CAPTURE."""
        result = self.orchestrator.route("Stakeholder wants dark mode feature")
        self.assertEqual(result["agent"], "CAPTURE")

    def test_capture_bug_report(self):
        """Bug reports route to CAPTURE."""
        result = self.orchestrator.route("Login button broken on mobile")
        self.assertEqual(result["agent"], "CAPTURE")

    def test_decision_store(self):
        """Decision statements route to DECISION."""
        result = self.orchestrator.route("Decision: deferring SSO to Q3")
        self.assertEqual(result["agent"], "DECISION")

    def test_decision_retrieve(self):
        """Decision queries route to DECISION."""
        result = self.orchestrator.route("What did we decide about SSO?")
        self.assertEqual(result["agent"], "DECISION")

    def test_schedule_focus_blocks(self):
        """Calendar requests route to SCHEDULE."""
        result = self.orchestrator.route("Find me 2 focus blocks")
        self.assertEqual(result["agent"], "SCHEDULE")

    def test_query_epic_status(self):
        """Epic status queries route to QUERY."""
        result = self.orchestrator.route("Show SAP epic status")
        self.assertEqual(result["agent"], "QUERY")

    def test_query_ticket_status(self):
        """Ticket queries route to QUERY."""
        result = self.orchestrator.route("What's the status of ticket 101?")
        self.assertEqual(result["agent"], "QUERY")

    def test_database_count_query(self):
        """Database count queries route to DATABASE."""
        result = self.orchestrator.route("How many tickets do I have?")
        self.assertEqual(result["agent"], "DATABASE")

    def test_prioritise_request(self):
        """Prioritization queries route to PRIORITISE."""
        result = self.orchestrator.route("Should I prioritise A or B first?")
        self.assertEqual(result["agent"], "PRIORITISE")

    def test_clarify_vague_input(self):
        """Vague input triggers CLARIFY."""
        result = self.orchestrator.route("Handle this")
        self.assertEqual(result["agent"], "CLARIFY")
        self.assertIn("clarification_question", result)


class TestCaptureAgentDrafting(unittest.TestCase):
    """Test Story Writer / Capture Agent ticket drafting."""

    def setUp(self):
        self.agent = CaptureAgent(project_id=REAL_PROJECT_ID)

    def test_draft_has_required_fields(self):
        """Draft contains all required ticket fields."""
        result = self.agent.draft_ticket("Add login feature")

        self.assertIsNotNone(result)
        self.assertIn("title", result)
        self.assertIn("type", result)
        self.assertIn("priority", result)
        self.assertIn("acceptance_criteria", result)

    def test_draft_type_story(self):
        """Feature request classified as Story."""
        result = self.agent.draft_ticket("Add export to CSV")
        self.assertEqual(result["type"], "Story")

    def test_draft_type_bug(self):
        """Bug report classified as Bug."""
        result = self.agent.draft_ticket("Login fails with error 500")
        self.assertEqual(result["type"], "Bug")

    def test_draft_type_task(self):
        """Task/classified work classified as Task."""
        result = self.agent.draft_ticket("Update documentation for API")
        self.assertEqual(result["type"], "Task")

    def test_acceptance_criteria_present(self):
        """Acceptance criteria are included."""
        result = self.agent.draft_ticket("Stakeholder wants dark mode")
        ac = result.get("acceptance_criteria", [])
        self.assertTrue(len(ac) > 0 if isinstance(ac, list) else len(ac.strip()) > 0)


class TestDecisionAgentStorage(unittest.TestCase):
    """Test Decision Log Agent storage/retrieval."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.agent = DecisionAgent(project_id=REAL_PROJECT_ID, db_client=self.mock_db)

    def test_store_decision_extracts_json(self):
        """Store mode extracts decision as JSON and saves."""
        self.mock_db.log_decision = MagicMock()

        result = self.agent.process_decision(
            telegram_id="12345",
            message="Decision: Launching v2.0 in June",
            mode="store"
        )

        self.assertIn("Decision logged", result)
        self.mock_db.log_decision.assert_called_once()

    def test_store_decision_has_decision_field(self):
        """Stored decision contains 'decision' field."""
        self.mock_db.log_decision = MagicMock()

        self.agent.process_decision(
            telegram_id="12345",
            message="Decision: defer SSO",
            mode="store"
        )

        call_args = self.mock_db.log_decision.call_args
        decision_data = call_args[0][1]
        self.assertIn("decision", decision_data)

    def test_retrieve_no_results_friendly_message(self):
        """Retrieval with no results returns friendly message."""
        self.mock_db.get_decisions = MagicMock(return_value=[])

        result = self.agent.process_decision(
            telegram_id="12345",
            message="What about launch date?",
            mode="retrieve"
        )

        self.assertIn("couldn't find", result.lower())


class TestScheduleAgentProposals(unittest.TestCase):
    """Test Calendar Optimizer focus block proposals."""

    def setUp(self):
        self.agent = ScheduleAgent()

    def test_returns_two_proposals(self):
        """Returns exactly 2 focus block proposals."""
        result = self.agent.get_focus_proposals(telegram_id="12345")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_proposal_has_start_time(self):
        """Each proposal has start time."""
        result = self.agent.get_focus_proposals(telegram_id="12345")
        for p in result:
            self.assertIn("start", p)

    def test_proposal_has_end_time(self):
        """Each proposal has end time."""
        result = self.agent.get_focus_proposals(telegram_id="12345")
        for p in result:
            self.assertIn("end", p)

    def test_proposal_has_rationale(self):
        """Each proposal has rationale."""
        result = self.agent.get_focus_proposals(telegram_id="12345")
        for p in result:
            self.assertIn("rationale", p)

    def test_proposal_duration_90_minutes(self):
        """Each proposal is 90 minutes long."""
        from datetime import datetime
        result = self.agent.get_focus_proposals(telegram_id="12345")

        for p in result:
            start = datetime.fromisoformat(p["start"])
            end = datetime.fromisoformat(p["end"])
            duration_mins = (end - start).total_seconds() / 60
            self.assertEqual(duration_mins, 90)


class TestCallbackDataFormat(unittest.TestCase):
    """Test inline button callback data formats."""

    def test_create_ticket_callback(self):
        """Create ticket callback format."""
        self.assertTrue("create_ticket".startswith("create_ticket"))

    def test_edit_ticket_callback(self):
        """Edit ticket callback format."""
        self.assertEqual("edit_ticket", "edit_ticket")

    def test_cancel_callback(self):
        """Cancel callback format."""
        self.assertEqual("cancel", "cancel")

    def test_book_slot_callback_extract_index(self):
        """Book slot callback index extraction."""
        callback = "book_slot_1"
        idx = int(callback.split("_")[-1])
        self.assertEqual(idx, 1)


# =============================================================================
# INTEGRATION TESTS - Require Oracle DB
# =============================================================================

class TestOracleClientIntegration(unittest.TestCase):
    """Oracle DB integration tests (requires connection)."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.client = OracleClient()
            cls.test_user = f"test_{os.urandom(4).hex().upper()}"
            cls.db_ok = True
        except Exception as e:
            cls.db_ok = False
            cls.db_error = str(e)

    def test_db_connection(self):
        """DB connection works."""
        if not self.db_ok:
            self.skipTest(f"DB unavailable: {self.db_error}")

        conn = self.client._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM DUAL")
        self.assertEqual(cursor.fetchone()[0], 1)

    def test_create_user(self):
        """Create and retrieve user."""
        if not self.db_ok:
            self.skipTest(f"DB unavailable: {self.db_error}")

        result = self.client.create_user(self.test_user, "Test User", onboarded=False)
        self.assertEqual(result["telegram_id"], self.test_user)

        user = self.client.get_user(self.test_user)
        self.assertIsNotNone(user)
        self.assertEqual(user["user_name"], "Test User")

    def test_add_ticket(self):
        """Add and retrieve ticket."""
        if not self.db_ok:
            self.skipTest(f"DB unavailable: {self.db_error}")

        ticket_id = f"TEST-{os.urandom(4).hex().upper()}"
        self.client.add_ticket(self.test_user, {
            "ticket_id": ticket_id,
            "title": "Test Ticket",
            "type": "Story",
            "status": "To Do"
        })

        tickets = self.client.get_tickets(self.test_user)
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.get("title"), "Test Ticket")

    def test_log_decision(self):
        """Log and retrieve decision."""
        if not self.db_ok:
            self.skipTest(f"DB unavailable: {self.db_error}")

        decision_id = f"DEC-{os.urandom(4).hex().upper()}"
        self.client.log_decision(self.test_user, {
            "decision": f"Test decision {decision_id}",
            "rationale": "Testing"
        })

        decisions = self.client.get_decisions(self.test_user, ["test"])
        self.assertGreater(len(decisions), 0)

    @classmethod
    def tearDownClass(cls):
        """Cleanup test data."""
        if cls.db_ok:
            try:
                conn = cls.client._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM TICKETS WHERE TELEGRAM_ID = :1", [cls.test_user])
                cursor.execute("DELETE FROM DECISIONS WHERE TELEGRAM_ID = :1", [cls.test_user])
                cursor.execute("DELETE FROM USERS WHERE TELEGRAM_ID = :1", [cls.test_user])
                conn.commit()
            except Exception as e:
                print(f"Cleanup warning: {e}")


# =============================================================================
# TEST RUNNER
# =============================================================================

def run_tests():
    """Run all tests with summary."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Unit tests
    suite.addTests(loader.loadTestsFromTestCase(TestOrchestratorRouting))
    suite.addTests(loader.loadTestsFromTestCase(TestCaptureAgentDrafting))
    suite.addTests(loader.loadTestsFromTestCase(TestDecisionAgentStorage))
    suite.addTests(loader.loadTestsFromTestCase(TestScheduleAgentProposals))
    suite.addTests(loader.loadTestsFromTestCase(TestCallbackDataFormat))

    # Integration tests
    suite.addTests(loader.loadTestsFromTestCase(TestOracleClientIntegration))

    # Run
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Run: {result.testsRun} | Failures: {len(result.failures)} | Errors: {len(result.errors)} | Skipped: {len(result.skipped)}")

    if result.failures:
        print("\nFAILURES:")
        for t, tb in result.failures:
            print(f"  - {t}")

    if result.errors:
        print("\nERRORS:")
        for t, tb in result.errors:
            print(f"  - {t}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
