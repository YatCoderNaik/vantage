class OnboardingManager:
    def __init__(self, db_client):
        self.fc = db_client

    def seed_sample_data(self, telegram_id, user_name):
        """Seed the Oracle database with sample data for a new user."""
        # 1. Seed Decisions
        self.fc.log_decision(telegram_id, {
            "decision": "Deferred SSO to next quarter",
            "rationale": "Prioritizing SAP integration layer for the demo sprint.",
            "epic": "Platform Security",
            "timestamp": "2024-03-20T10:00:00Z",
            "tags": ["SSO", "Security", "Strategy"]
        })

        # 2. Seed Epic
        epic_id = "EPIC-04"
        self.fc.add_ticket(str(telegram_id), {
            "ticket_id": epic_id,
            "title": "SAP Integration Layer",
            "type": "Epic",
            "status": "In Progress",
            "priority": "High",
            "backlog": "Product",
            "tags": ["SAP", "Backend"]
        })

        # 3. Seed Stories for SAP Epic
        stories = [
            {
                "ticket_id": "STORY-101",
                "title": "SAP Auth Handshake",
                "type": "Story",
                "status": "Done",
                "priority": "High",
                "epic_id": epic_id,
                "backlog": "Sprint",
                "sprint_id": "Sprint 6",
                "acceptance_criteria": "- OAuth2 handshake successful\n- Access tokens refreshed\n- Error logs captured",
                "tags": ["SAP", "Auth"]
            },
            {
                "ticket_id": "STORY-102",
                "title": "Data Mapping for Invoice Sync",
                "type": "Story",
                "status": "In Progress",
                "priority": "Medium",
                "epic_id": epic_id,
                "backlog": "Sprint",
                "sprint_id": "Sprint 7",
                "acceptance_criteria": "- Field mapping defined\n- Transformation logic implemented\n- Unit tests pass",
                "tags": ["SAP", "Data"]
            },
            {
                "ticket_id": "STORY-103",
                "title": "Error Handling & Retry Logic",
                "type": "Story",
                "status": "To Do",
                "priority": "Low",
                "epic_id": epic_id,
                "backlog": "Product",
                "acceptance_criteria": "- Exponential backoff implemented\n- 3 retries maximum\n- Alert sent on final failure",
                "tags": ["SAP", "Resilience"]
            },
            {
                "ticket_id": "STORY-104",
                "title": "End-to-End Integration Test",
                "type": "Story",
                "status": "Blocked",
                "priority": "High",
                "epic_id": epic_id,
                "backlog": "Sprint",
                "sprint_id": "Sprint 7",
                "acceptance_criteria": "- Full flow from SAP to Backend\n- Data integrity verified\n- Cleanup after tests",
                "tags": ["SAP", "Testing"]
            }
        ]

        for story in stories:
            self.fc.add_ticket(str(telegram_id), story)

        # 4. User Profile
        self.fc.create_user(telegram_id, user_name, onboarded=True)
        
        return True
