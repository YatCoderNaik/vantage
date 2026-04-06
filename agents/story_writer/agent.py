import json
from vertexai.generative_models import GenerativeModel

class CaptureAgent:
    def __init__(self, project_id):
        self.model = GenerativeModel("gemini-2.5-flash-lite")
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

    def draft_ticket(self, context):
        """Converts raw input into a structured ticket draft."""
        try:
            response = self.model.generate_content(
                [self.system_prompt, f"Context: {context}"],
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Error in CaptureAgent: {e}")
            return None
