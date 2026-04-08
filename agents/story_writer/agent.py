import json
import vertexai
from vertexai.generative_models import GenerativeModel
from logic.retries import po_retry_policy

class CaptureAgent:
    def __init__(self, project_id, location="global"):
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel("gemini-3.1-flash-lite-preview")
        self.system_prompt = """
        You are a Senior Product Owner. Your role is to convert a raw stakeholder request into a structured JSON ticket.
        
        Fields for the JSON ticket:
        - title: Concise and descriptive
        - type: Exactly one of [Story, Bug, Task]
        - priority: Exactly one of [High, Medium, Low]
        - epic: Associated epic name or "General"
        - acceptance_criteria: List of 3-5 specific bullet points
        - dependencies: List of strings or empty list
        
        Be specific. Never leave Acceptance Criteria vague. Ensure the output is valid JSON.
        """

    @po_retry_policy
    def draft_ticket(self, context):
        """Converts raw input into a structured ticket draft."""
        response = self.model.generate_content(
            [self.system_prompt, f"Context: {context}"],
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
