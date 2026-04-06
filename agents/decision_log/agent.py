import json
from vertexai.generative_models import GenerativeModel

class DecisionAgent:
    def __init__(self, project_id, db_client):
        self.model = GenerativeModel("gemini-2.5-flash-lite")
        self.fc = db_client
        self.system_prompt = """
        You are a Decision Log Assistant for Product Owners.
        Your role is to extract and retrieve structured decisions.
        
        When storing:
        Extract the decision statement, rationale, and any linked Epic.
        Format: { "decision", "rationale", "epic", "timestamp", "tags" }
        
        When retrieving:
        Return the most relevant decision with its timestamp and rationale.
        """

    def process_decision(self, telegram_id, message, mode="store"):
        """Stores or retrieves a decision."""
        if mode == "store":
            prompt = f"Extract decision data from this message: '{message}'. Return as JSON."
            response = self.model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            data = json.loads(response.text)
            self.fc.log_decision(telegram_id, data)
            return f"✅ Decision logged: {data.get('decision')}"
        else:
            # Retrieval mode
            kw_prompt = f"Extract 1-2 search keywords for this decision query: '{message}'. Return as JSON array."
            kw_response = self.model.generate_content(kw_prompt, generation_config={"response_mime_type": "application/json"})
            keywords = json.loads(kw_response.text)
            
            decisions = self.fc.get_decisions(telegram_id, keywords)
            if not decisions:
                return "I couldn't find any decisions matching that query."
            
            # Simple most-recent or most-relevant logic (using LLM to pick)
            pick_prompt = f"From these decisions, pick the most relevant one to answer '{message}': {decisions}. Return a concise human-readable answer."
            final_response = self.model.generate_content(pick_prompt)
            return final_response.text
            
