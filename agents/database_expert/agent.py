import os
import sys
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import McpToolset
from mcp.client.stdio import StdioServerParameters
from dotenv import load_dotenv
from google.cloud import secretmanager
from google.genai import types
from logic.retries import po_retry_policy

# Define Root
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT, ".env"), override=True)

class DatabaseExpert:
    def __init__(self, project_id=None):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        os.environ["GOOGLE_CLOUD_PROJECT"] = self.project_id
        os.environ["GOOGLE_CLOUD_LOCATION"] = self.location
        self.sm_client = secretmanager.SecretManagerServiceClient() if self.project_id else None

        # Prepare environment for toolbox.exe
        env = os.environ.copy()
        env["DB_USER"] = self._get_db_secret("DB_USER")
        env["DB_PASSWORD"] = self._get_db_secret("DB_PASSWORD")
        env["LOCAL_WALLET_DIR"] = self._get_db_secret("LOCAL_WALLET_DIR", os.path.join(ROOT, "wallet"))

        # MCP Toolset Configuration
        TOOLBOX_PATH = os.path.join(ROOT, "toolbox.exe")
        TOOLS_FILE = os.path.join(ROOT, "tools.yaml")
        
        oracle_mcp_toolset = McpToolset(
            connection_params=StdioServerParameters(
                command=TOOLBOX_PATH,
                args=["--tools-file", TOOLS_FILE, "--stdio"],
                env=env
            )
        )

        # Database Expert Agent
        self.agent = Agent(
            name="database_expert",
            model="gemini-1.5-flash",
            description="I am an Oracle Database Expert that can execute SQL queries to manage Vantage assistant data.",
            instruction="""
            You are an Oracle SQL Expert. Your role is to help other agents query and manage data in the Vantage database.
            You have a tool called 'oracle_execute_sql' that can execute any SQL statement.
            
            ### Data Schema Reference:
            - **USERS Table**: (TELEGRAM_ID VARCHAR2(50) PRIMARY KEY, USER_DATA CLOB) -- stores user profile JSON.
            - **TICKETS Table**: (TICKET_ID VARCHAR2(50) PRIMARY KEY, TELEGRAM_ID VARCHAR2(50), TITLE VARCHAR2(255), STATUS VARCHAR2(50), TYPE VARCHAR2(50), EPIC_ID VARCHAR2(50), BACKLOG VARCHAR2(50), SPRINT_ID VARCHAR2(50), DATA CLOB)
            - **DECISIONS Table**: (DECISION_ID VARCHAR2(50) PRIMARY KEY, TELEGRAM_ID VARCHAR2(50), DECISION_TEXT CLOB, CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
            
            ### Guidelines:
            - ALWAYS use well-formed Oracle SQL.
            - When fetching data, return the results clearly.
            - If asked to search, use LIKE for simple keyword matches.
            - For JSON data in CLOB columns, assume they store relevant metadata.
            """,
            tools=[oracle_mcp_toolset]
        )
        
        self.runner = Runner(
            app_name="vantage", 
            agent=self.agent, 
            session_service=InMemorySessionService()
        )

    def _get_db_secret(self, key, default=None):
        if self.project_id:
            try:
                name = f"projects/{self.project_id}/secrets/{key}/versions/latest"
                response = self.sm_client.access_secret_version(request={"name": name})
                return response.payload.data.decode("UTF-8")
            except:
                return os.getenv(key, default)
        return os.getenv(key, default)

    @po_retry_policy
    async def run_query(self, telegram_id, message):
        """Executes a query using the ADK Runner with MCP tools."""
        user_id_str = str(telegram_id)
        session_id = f"db_{telegram_id}"
        
        # Ensure session exists in the InMemorySessionService
        existing_session = await self.runner.session_service.get_session(
            app_name=self.runner.app_name, 
            user_id=user_id_str, 
            session_id=session_id
        )
        if not existing_session:
            await self.runner.session_service.create_session(
                app_name=self.runner.app_name, 
                user_id=user_id_str, 
                session_id=session_id
            )

        new_message = types.Content(parts=[types.Part(text=message)])
        response_text = ""
        
        async for event in self.runner.run_async(
            user_id=user_id_str, 
            session_id=session_id,
            new_message=new_message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
        
        return response_text or "I processed your request but have no text response."
