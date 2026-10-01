import os
import libsql_experimental as libsql
from dotenv import load_dotenv

def migrate():
    load_dotenv()
    env = os.getenv("APP_ENV", "development")
    
    if env == "production":
        url = os.getenv("TURSO_PROD_DATABASE_URL")
        token = os.getenv("TURSO_PROD_AUTH_TOKEN")
    else:
        url = os.getenv("TURSO_DEV_DATABASE_URL")
        token = os.getenv("TURSO_DEV_AUTH_TOKEN")
        
    # Fallback for backward compatibility
    if not url or not token:
        url = os.getenv("TURSO_DATABASE_URL")
        token = os.getenv("TURSO_AUTH_TOKEN")
        
    if not url or not token:
        print(f"Turso credentials missing from .env for environment: {env}")
        return
        
    conn = libsql.connect(f"{url}?authToken={token}")
    
    print("Adding criteria_extracted column...")
    try:
        conn.execute("ALTER TABLE scholarships ADD COLUMN criteria_extracted TEXT;")
        print("Success.")
    except Exception as e:
        print(f"Skipped (may already exist): {e}")

    print("Adding submission_requirements column...")
    try:
        conn.execute("ALTER TABLE scholarships ADD COLUMN submission_requirements TEXT;")
        print("Success.")
    except Exception as e:
        print(f"Skipped (may already exist): {e}")

    conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
