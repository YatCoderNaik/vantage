import json
import vertexai
from vertexai.generative_models import GenerativeModel, Part

class Orchestrator:
    def __init__(self, project_id, location="global"):
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel("gemini-3.1-flash-lite-preview")
        self.system_prompt = """
        You are the PO Orchestrator for Vantage, a mobile-first AI assistant for Product Owners.
        Your role is to classify the user's message and route it to exactly one sub-agent.
        
        Classify intent into exactly one of: [CAPTURE, SCHEDULE, DECISION, PRIORITISE, QUERY, CLARIFY, DATABASE].
        
        - CAPTURE: For new stakeholder requests, feature asks, or rough notes that need to be turned into tickets.
        - SCHEDULE: For finding focus blocks, deep work slots, or calendar optimization.
        - DECISION: For logging a decision or asking "What did we decide about X?".
        - PRIORITISE: For asking which tasks or features should come first.
        - QUERY: For asking about the status, history, or current state of any ticket, epic, or feature (e.g. "What happened to the SAP task?").
        - DATABASE: For complex reporting, raw SQL requests, or technical database questions (e.g. "How many tickets do I have?", "Run a count of bugs").
        - CLARIFY: If the message is too vague to classify with high confidence (>0.75).
        
        Return a JSON object in this format:
        {
            "agent": "AGENT_NAME",
            "confidence": 0.0-1.0,
            "extracted_context": { ... },
            "clarification_question": "String (only if agent is CLARIFY)"
        }
        """

    def route(self, message):
        """Classify and route the incoming message."""
        try:
            response = self.model.generate_content(
                [self.system_prompt, f"User message: {message}"],
                generation_config={"response_mime_type": "application/json"}
            )
            data = json.loads(response.text)
            
            # Additional heuristic: if confidence is low, force CLARIFY
            if data.get('confidence', 0) < 0.75 and data.get('agent') != 'CLARIFY':
                data['agent'] = 'CLARIFY'
                if not data.get('clarification_question'):
                    data['clarification_question'] = "I'm not quite sure I follow. Could you provide a bit more detail so I can help?"
            
            return data
        except Exception as e:
            print(f"Error in Orchestrator: {e}")
            return {
                "agent": "CLARIFY",
                "confidence": 0,
                "clarification_question": "I'm having a bit of trouble processing that. Could you try rephrasing?"
            }
