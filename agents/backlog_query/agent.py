import json
import vertexai
from vertexai.generative_models import GenerativeModel

class QueryAgent:
    def __init__(self, project_id, db_client, location="global"):
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel("gemini-3.1-flash-lite-preview")
        self.fc = db_client
        self.system_prompt = """
        You are a Product Owner assistant. Your role is to reason over existing backlog data to answer natural language questions.
        
        When given a query:
        1. Identify the core entity (a specific story or an epic).
        2. Summarize the status based on the provided data.
        3. If it's an Epic, aggregate the count of stories by status (Done/In Progress/To Do/Blocked).
        4. If it's a Story, return its status, backlog location, and sprint/epic details.
        
        Provide a concise, professional response. End with a proactive follow-up offer (e.g. flag a blocker, log a decision).
        """

    def answer_query(self, telegram_id, message):
        """Extract keywords, search Firestore, and summarize results."""
        # Step 1: Extract keywords from message
        kw_prompt = f"Extract 2-3 search keywords from this message: '{message}'. Return as JSON array of strings."
        kw_response = self.model.generate_content(kw_prompt, generation_config={"response_mime_type": "application/json"})
        keywords = json.loads(kw_response.text)
        
        # Step 2: Search Firestore
        tickets = self.fc.search_tickets(telegram_id, keywords)
        
        if not tickets:
            return "I couldn't find any tickets or epics matching those keywords. Could you provide more details?"

        # Step 3: Check if the best match is an Epic
        # For simplicity, if any match is an Epic, we'll treat it as an Epic query
        epics = [t for t in tickets if str(t.get('type', '')).lower() == 'epic']
        
        if epics:
            epic = epics[0]
            stories = self.fc.get_epic_stories(telegram_id, epic.get('ticket_id'))
            
            # Aggregate status
            status_counts = {"Done": 0, "In Progress": 0, "To Do": 0, "Blocked": 0}
            story_list = []
            for s in stories:
                stat = s.get('status', 'To Do')
                status_counts[stat] = status_counts.get(stat, 0) + 1
                emoji = {"Done": "✅", "In Progress": "🔄", "To Do": "⏳", "Blocked": "🔴"}.get(stat, "❓")
                story_list.append(f"{emoji} {s.get('title')} — {stat} ({s.get('sprint_id', 'Backlog')})")
            
            summary = f"Found Epic: {epic.get('title')} ({epic.get('ticket_id')}).\n"
            summary += f"Status summary: {status_counts['Done']} DONE, {status_counts['In Progress']} IN PROGRESS, {status_counts['To Do']} TO DO, {status_counts['Blocked']} BLOCKED.\n\n"
            summary += "\n".join(story_list)
            
            # Refine summary with LLM
            refine_prompt = f"Summarize this data for the user: {summary}. Maintain the list and end with a proactive follow-up."
            refined_response = self.model.generate_content(refine_prompt)
            return refined_response.text
        else:
            # Handle Story query
            story = tickets[0]
            summary = f"Ticket: {story.get('title')} ({story.get('ticket_id')})\nStatus: {story.get('status')}\nLocation: {story.get('backlog')} Backlog\nSprint: {story.get('sprint_id', 'N/A')}"
            
            refine_prompt = f"Summarize this ticket info for the user: {summary}. End with a proactive follow-up."
            refined_response = self.model.generate_content(refine_prompt)
            return refined_response.text
