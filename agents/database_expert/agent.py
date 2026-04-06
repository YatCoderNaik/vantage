import os
import sys
from google.adk import Agent
from google.adk.tools import McpToolset
from mcp.client.stdio import StdioServerParameters
from dotenv import load_dotenv
from google.cloud import secretmanager

# Define Root
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT, ".env"), override=True)

# Project and Secret Management
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
sm_client = secretmanager.SecretManagerServiceClient() if PROJECT_ID else None

def get_db_secret(key, default=None):
    if PROJECT_ID:
        try:
            name = f"projects/{PROJECT_ID}/secrets/{key}/versions/latest"
            response = sm_client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except:
            return os.getenv(key, default)
    return os.getenv(key, default)

# Prepare environment for toolbox.exe
env = os.environ.copy()
env["DB_USER"] = get_db_secret("DB_USER")
env["DB_PASSWORD"] = get_db_secret("DB_PASSWORD")
env["LOCAL_WALLET_DIR"] = get_db_secret("LOCAL_WALLET_DIR", os.path.join(ROOT, "wallet"))

# Path to toolbox executable (vantage/toolbox.exe)
TOOLBOX_PATH = os.path.join(ROOT, "toolbox.exe")

# MCP Toolset Configuration
# This launches toolbox.exe as an MCP server with tools.yaml
oracle_mcp_toolset = McpToolset(
    connection_params=StdioServerParameters(
        command=TOOLBOX_PATH,
        args=["mcp", "--tools-file", os.path.join(ROOT, "tools.yaml")],
        env=env
    )
)

# Database Expert Agent
database_expert = Agent(
    name="database_expert",
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
