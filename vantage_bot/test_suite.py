import asyncio
import os
import sys
import json
import logging
from unittest.mock import AsyncMock, MagicMock

# Ensure we can import from the root
sys.path.append(os.getcwd())

from vantage_bot.bot import handle_message, callback_handler, fc, onboarding, orchestrator, capture_agent, query_agent, decision_agent, schedule_agent, db_runner

# Configure logging for tests
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class MockBot:
    def __init__(self):
        self.sent_messages = []
        self.sent_actions = []

    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        self.sent_messages.append({"text": text, "reply_markup": reply_markup})
        return MagicMock(message_id=len(self.sent_messages))

    async def send_chat_action(self, chat_id, action):
        self.sent_actions.append(action)

    async def answer_callback_query(self, callback_query_id):
        pass

class MockUpdate:
    def __init__(self, text, user_id, user_name="TestUser", callback_data=None):
        self.message = MagicMock()
        self.message.text = text
        self.message.reply_text = AsyncMock()
        self.effective_user = MagicMock(id=user_id, first_name=user_name)
        self.callback_query = None
        
        if callback_data:
            self.callback_query = MagicMock()
            self.callback_query.data = callback_data
            self.callback_query.from_user = self.effective_user
            self.callback_query.answer = AsyncMock()
            self.callback_query.edit_message_text = AsyncMock()
            self.message = None # In a callback, message is handled differently

class MockContext:
    def __init__(self):
        self.bot = MockBot()
        self.user_data = {}

async def run_test(name, steps, user_id=999999):
    print(f"\n🚀 Running '{name}'...")
    context = MockContext()
    
    for i, (input_text, expected_keyword, is_callback) in enumerate(steps):
        print(f"  Step {i+1}: Action -> {input_text}")
        await asyncio.sleep(2) # Avoid rate limits
        
        if is_callback:
            update = MockUpdate(None, user_id, callback_data=input_text)
            await callback_handler(update, context)
            last_msg = update.callback_query.edit_message_text.call_args[0][0] if update.callback_query.edit_message_text.called else ""
        else:
            update = MockUpdate(input_text, user_id)
            await handle_message(update, context)
            last_msg = update.message.reply_text.call_args[0][0] if update.message.reply_text.called else ""
        
        # Simple verification
        if expected_keyword.lower() in last_msg.lower():
            print(f"  ✅ Result matched: {expected_keyword}")
        else:
            print(f"  ❌ Result MISMATCH!")
            print(f"     Expected to find: '{expected_keyword}'")
            print(f"     Actual Response: '{last_msg}'")

async def main():
    test_user_id = 999999
    
    # Cleanup previous test data
    try:
        conn = fc._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM TICKETS WHERE TELEGRAM_ID = :1", [str(test_user_id)])
        cursor.execute("DELETE FROM DECISIONS WHERE TELEGRAM_ID = :1", [str(test_user_id)])
        cursor.execute("DELETE FROM USERS WHERE TELEGRAM_ID = :1", [str(test_user_id)])
        conn.commit()
        print("🧹 Cleaned up previous test data.")
    except Exception as e:
        print(f"⚠️ Cleanup failed: {e}")

    # TEST 1: Onboarding
    await run_test("First-Time User Onboarding", [
        ("/start", "Welcome to Vantage", False),
        ("What did we decide about SSO?", "SSO", False),
        ("Show me SAP epic", "EPIC-04", False)
    ])

    # TEST 2: Capture Flow
    await run_test("Stakeholder Request -> Ticket Creation", [
        ("Stakeholder wants dark mode feature for the app", "Drafting Ticket", False),
        (f"create_ticket_{test_user_id}", "created in Oracle", True),
        ("Show my tickets", "dark mode", False)
    ])

    # TEST 3: Edit Flow
    await run_test("Edit Ticket Flow", [
        ("Add a bug for login failing", "Drafting", False),
        ("edit_ticket", "change", True),
        ("Make it High priority and add to Security epic", "High", False),
        (f"create_ticket_{test_user_id}", "created in Oracle", True)
    ])

    # TEST 4: Decision Logging
    await run_test("Decision Logging & Retrieval", [
        ("Decision: We're launching v2.0 in June instead of May", "Decision logged", False),
        ("What did we decide about launch date?", "June", False),
        ("Show all decisions", "launching", False)
    ])

    # TEST 5: Epic Aggregation
    await run_test("Epic Query (Aggregation)", [
        ("What's the status of SAP Integration?", "EPIC-04", False),
        ("What's the status of SAP Integration?", "DONE", False)
    ])

    # TEST 6: Focus Block
    await run_test("Focus Block Scheduling", [
        ("Find me 2 focus blocks for roadmap work", "Focus Blocks", False),
        ("book_slot_0", "confirmed", True)
    ])

    # TEST 7: Clarification
    await run_test("Clarification Flow", [
        ("Handle this", "detail", False),
        ("I mean, add a task for testing the API", "Drafting", False)
    ])

    # TEST 8: Database Expert
    await run_test("Database Expert", [
        ("How many tickets do I have?", "tickets", False)
    ])

    # TEST 9: Cancel
    await run_test("Cancel Action", [
        ("Add a bug for login failing", "Drafting", False),
        ("cancel", "cancelled", True)
    ])

    print("\n✅ All simulated tests completed.")

if __name__ == "__main__":
    asyncio.run(main())
