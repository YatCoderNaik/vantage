import sys
import os
from storage.oracle_client import OracleClient

def main():
    print("--- Starting Oracle DB Connection Test (v2) ---")
    
    try:
        # Initialize OracleClient
        client = OracleClient()
        print("[1] Connection Initialized via OracleClient.")
        
        # Test Query
        conn = client._get_connection()
        c = conn.cursor()
        c.execute("SELECT 'Connection Successful!', sysdate FROM DUAL")
        result = c.fetchone()
        
        print(f"[2] SUCCESS: {result[0]}")
        print(f"[3] Current Sysdate: {result[1]}")
        print(f"[4] Server Version: {conn.version}")
        
        # Check Tables
        print("\n--- Checking Table Access ---")
        tables = ["USERS", "TICKETS", "DECISIONS"]
        for t in tables:
            try:
                c.execute(f"SELECT count(*) FROM {t}")
                count = c.fetchone()[0]
                print(f"- Table '{t}' exists and is accessible. Rows: {count}")
            except Exception as e:
                print(f"- ERROR: Table '{t}' is NOT accessible. Error: {e}")

        conn.close()
        print("\nTest completed successfully!")
        
    except Exception as e:
        print("\n--- CRITICAL ERROR: Connection Failed ---")
        print(f"Error Message: {e}")
        print("\nPlease check your .env file or Google Cloud Secrets for:")
        print("1. DB_USER, DB_PASSWORD, DB_DSN")
        print("2. WALLET_PASSWORD and LOCAL_WALLET_DIR")
        sys.exit(1)

if __name__ == "__main__":
    # Ensure ROOT is in path for imports
    ROOT = os.path.dirname(os.path.abspath(__file__))
    if ROOT not in sys.path:
        sys.path.append(ROOT)
    main()
