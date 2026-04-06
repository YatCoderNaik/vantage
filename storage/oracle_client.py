import os
import oracledb
import json
from dotenv import load_dotenv
from google.cloud import secretmanager

# Define Root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"), override=True)

class OracleClient:
    def __init__(self, project_id=None):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.client = secretmanager.SecretManagerServiceClient() if self.project_id else None
        
        # Priority: Secret Manager -> Environment Variable -> Default
        self.user = self._get_secret("DB_USER")
        self.password = self._get_secret("DB_PASSWORD")
        self.dsn = self._get_secret("DB_DSN", "adb.ap-hyderabad-1.oraclecloud.com:1522/g6978cb8c6dbe06_glucotrack_high.adb.oraclecloud.com")
        self.wallet_location = self._get_secret("LOCAL_WALLET_DIR", os.path.join(ROOT, "wallet"))
        self.wallet_password = self._get_secret("WALLET_PASSWORD")
        
        # Use thin mode if wallet is not provided or if specified
        self.connection = None
        self._ensure_tables()

    def _get_secret(self, key, default=None):
        """Fetch secret from SM if project_id is set, otherwise use env var."""
        if self.project_id:
            try:
                name = f"projects/{self.project_id}/secrets/{key}/versions/latest"
                response = self.client.access_secret_version(request={"name": name})
                return response.payload.data.decode("UTF-8")
            except Exception:
                # Fallback to env var if secret not found or error
                return os.getenv(key, default)
        return os.getenv(key, default)

    def _get_connection(self):
        if self.connection is None:
            # Oracle Thin driver handles connection string and Cloud DBs well
            if os.path.exists(self.wallet_location):
                self.connection = oracledb.connect(
                    user=self.user,
                    password=self.password,
                    dsn=self.dsn,
                    config_dir=self.wallet_location,
                    wallet_location=self.wallet_location,
                    wallet_password=self.wallet_password
                )
            else:
                # Fallback to no wallet (requires correct connection string with TLS settings if using ADB)
                self.connection = oracledb.connect(
                    user=self.user,
                    password=self.password,
                    dsn=self.dsn
                )
        return self.connection

    def _ensure_tables(self):
        """Create tables if they do not exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        tables = {
            "USERS": "(TELEGRAM_ID VARCHAR2(50) PRIMARY KEY, USER_NAME VARCHAR2(255), ONBOARDED NUMBER(1), CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "TICKETS": "(TICKET_ID VARCHAR2(100) PRIMARY KEY, TELEGRAM_ID VARCHAR2(50), TITLE VARCHAR2(255), STATUS VARCHAR2(50), TYPE VARCHAR2(50), EPIC_ID VARCHAR2(50), BACKLOG VARCHAR2(50), SPRINT_ID VARCHAR2(50), STORY_POINTS NUMBER(4), ACCEPTANCE_CRITERIA CLOB, TAGS VARCHAR2(500), DATA CLOB)",
            "DECISIONS": "(DECISION_ID VARCHAR2(100) PRIMARY KEY, TELEGRAM_ID VARCHAR2(50), DECISION_TEXT CLOB, CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        }
        
        for name, schema in tables.items():
            try:
                # Dropping old tables to apply schema changes effectively
                if name == "TICKETS":
                    try:
                        cursor.execute("SELECT STORY_POINTS FROM TICKETS FETCH FIRST 1 ROW ONLY")
                    except:
                        cursor.execute("DROP TABLE TICKETS")
                        print("Dropped and recreated TICKETS table for new schema (Story Points).")
                    try:
                        cursor.execute("SELECT USER_DATA FROM USERS FETCH FIRST 1 ROW ONLY")
                        cursor.execute("DROP TABLE USERS")
                        print("Dropped old USERS table to apply new schema.")
                    except:
                        pass # Already new or doesn't exist
                
                cursor.execute(f"CREATE TABLE {name} {schema}")
            except oracledb.DatabaseError as e:
                error, = e.args
                if error.code == 955: # Table already exists
                    pass
                else:
                    print(f"Error creating table {name}: {e}")
        
        conn.commit()

    def get_user(self, telegram_id):
        """Fetch user profile by Telegram ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT USER_NAME, ONBOARDED, CREATED_AT FROM USERS WHERE TELEGRAM_ID = :1", [str(telegram_id)])
        row = cursor.fetchone()
        if row:
            return {
                "telegram_id": str(telegram_id),
                "user_name": row[0],
                "onboarded": bool(row[1]),
                "created_at": str(row[2])
            }
        return None

    def create_user(self, telegram_id, user_name, onboarded=True):
        """Create or update a user profile."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "MERGE INTO USERS t USING (SELECT :tid as id FROM DUAL) s ON (t.TELEGRAM_ID = s.id) "
            "WHEN MATCHED THEN UPDATE SET USER_NAME = :name, ONBOARDED = :ob "
            "WHEN NOT MATCHED THEN INSERT (TELEGRAM_ID, USER_NAME, ONBOARDED) VALUES (:tid, :name, :ob)",
            {'tid': str(telegram_id), 'name': user_name, 'ob': 1 if onboarded else 0}
        )
        conn.commit()
        return {"telegram_id": str(telegram_id), "user_name": user_name, "onboarded": onboarded}

    def get_tickets(self, telegram_id, filters=None):
        """Fetch tickets scoped to a user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT TICKET_ID, TELEGRAM_ID, TITLE, STATUS, TYPE, EPIC_ID, BACKLOG, SPRINT_ID, DATA FROM TICKETS WHERE TELEGRAM_ID = :1"
        params = [str(telegram_id)]
        
        if filters:
            for field, value in filters.items():
                query += f" AND {field.upper()} = :{len(params)+1}"
                params.append(value)
        
        cursor.execute(query, params)
        cols = [d[0].lower() for d in cursor.description]
        results = []
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            if item.get('data'):
                try:
                    meta = json.loads(item['data'])
                    item.update(meta)
                except:
                    pass
            results.append(item)
        return results

    def add_ticket(self, telegram_id, ticket_data):
        """Helper to add/update a ticket."""
        conn = self._get_connection()
        cursor = conn.cursor()
        tid = ticket_data.get('ticket_id', f"TEMP-{os.urandom(4).hex().upper()}")
        title = ticket_data.get('title')
        status = ticket_data.get('status', 'To Do')
        t_type = ticket_data.get('type', 'Story')
        epic_id = ticket_data.get('epic_id')
        backlog = ticket_data.get('backlog', 'Backlog')
        sprint_id = ticket_data.get('sprint_id')
        sp = ticket_data.get('story_points')
        ac = ticket_data.get('acceptance_criteria')
        tags = ",".join(ticket_data.get('tags', [])) if isinstance(ticket_data.get('tags'), list) else ticket_data.get('tags')
        
        # Store everything else in DATA CLOB
        meta = {k:v for k in ticket_data if k not in ['ticket_id', 'telegram_id', 'title', 'status', 'type', 'epic_id', 'backlog', 'sprint_id', 'story_points', 'acceptance_criteria', 'tags']}
        data_json = json.dumps(meta)
        
        cursor.execute(
            "MERGE INTO TICKETS t USING (SELECT :tid as id FROM DUAL) s ON (t.TICKET_ID = s.id) "
            "WHEN MATCHED THEN UPDATE SET TITLE=:title, STATUS=:status, TYPE=:type, EPIC_ID=:epic_id, BACKLOG=:backlog, SPRINT_ID=:sprint_id, STORY_POINTS=:sp, ACCEPTANCE_CRITERIA=:ac, TAGS=:tags, DATA=:data "
            "WHEN NOT MATCHED THEN INSERT (TICKET_ID, TELEGRAM_ID, TITLE, STATUS, TYPE, EPIC_ID, BACKLOG, SPRINT_ID, STORY_POINTS, ACCEPTANCE_CRITERIA, TAGS, DATA) VALUES (:tid, :tg_id, :title, :status, :type, :epic_id, :backlog, :sprint_id, :sp, :ac, :tags, :data)",
            {
                'tid': tid, 
                'tg_id': str(telegram_id), 
                'title': title, 
                'status': status, 
                'type': t_type, 
                'epic_id': epic_id, 
                'backlog': backlog, 
                'sprint_id': sprint_id, 
                'sp': sp,
                'ac': ac,
                'tags': tags,
                'data': data_json
            }
        )
        conn.commit()

    def search_tickets(self, telegram_id, keywords):
        """Search tickets using SQL LIKE."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        where_clauses = []
        for kw in keywords:
            where_clauses.append(f"LOWER(TITLE) LIKE '%{kw.lower()}%'")
        
        query = f"SELECT * FROM TICKETS WHERE TELEGRAM_ID = :1"
        if where_clauses:
            query += " AND (" + " OR ".join(where_clauses) + ")"
            
        cursor.execute(query, [str(telegram_id)])
        cols = [d[0].lower() for d in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(cols, row)))
        return results

    def get_epic_stories(self, telegram_id, epic_id):
        """Get all stories linked to an epic for a specific user."""
        return self.get_tickets(telegram_id, filters={'epic_id': epic_id})

    def log_decision(self, telegram_id, decision_data):
        """Store a decision scoped to a user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        did = f"DEC-{os.urandom(4).hex().upper()}"
        text = decision_data.get('decision', decision_data.get('decision_text', ''))
        cursor.execute(
            "INSERT INTO DECISIONS (DECISION_ID, TELEGRAM_ID, DECISION_TEXT) VALUES (:1, :2, :3)",
            [did, str(telegram_id), text]
        )
        conn.commit()

    def get_decisions(self, telegram_id, keywords=None):
        """Fetch decisions for a user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT DECISION_TEXT as decision, CREATED_AT FROM DECISIONS WHERE TELEGRAM_ID = :1"
        params = [str(telegram_id)]
        
        if keywords:
            for kw in keywords:
                query += f" AND LOWER(DECISION_TEXT) LIKE '%{kw.lower()}%'"
        
        cursor.execute(query, params)
        cols = [d[0].lower() for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
