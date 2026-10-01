import os
import sys
import json
from pathlib import Path
import libsql_experimental as libsql
from dotenv import load_dotenv

# Add src root to sys.path
_SRC_ROOT = Path(__file__).resolve().parent.parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from core.db import get_db_connection
from core.config import SCHOLARSHIPS_PATH

def main():
    json_path = SCHOLARSHIPS_PATH if SCHOLARSHIPS_PATH.exists() else _PROJECT_ROOT / "current_scholarships.json"
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    print("Loading JSON data...")
    with open(json_path, "r", encoding="utf-8") as f:
        scholarships = json.load(f)

    conn = get_db_connection()

    print("Starting upload to Turso...")
    count = 0
    for s in scholarships:
        # Check if already exists by title and organization
        title = s.get("Title", "")
        org = s.get("Organization", "")
        
        existing = conn.execute(
            "SELECT id FROM scholarships WHERE title = ? AND organization = ?",
            (title, org)
        ).fetchone()

        if existing:
            # We skip duplicates for now or we could update them
            continue

        query = """
        INSERT INTO scholarships (
            title, link, organization, phone_number, emails, level_of_study, award_type, 
            purpose, focus, qualifications, criteria, funds, duration, number_of_awards, 
            to_apply, deadline, contact, for_more_information, attributes, specific_requirements, 
            month, deadline_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        values = (
            s.get("Title"),
            s.get("Link"),
            s.get("Organization"),
            s.get("Phone Number"),
            json.dumps(s.get("Emails")) if s.get("Emails") else None,
            s.get("Level of Study"),
            s.get("Award Type"),
            s.get("Purpose"),
            s.get("Focus"),
            s.get("Qualifications"),
            s.get("Criteria"),
            s.get("Funds"),
            s.get("Duration"),
            s.get("Number of Awards"),
            s.get("To Apply"),
            s.get("Deadline"),
            s.get("Contact"),
            json.dumps(s.get("For more information")) if s.get("For more information") else None,
            json.dumps(s.get("Attributes_2Step") or s.get("Attributes")) if s.get("Attributes_2Step") or s.get("Attributes") else None,
            json.dumps(s.get("SpecificRequirements_2Step") or s.get("SpecificRequirements")) if s.get("SpecificRequirements_2Step") or s.get("SpecificRequirements") else None,
            s.get("Month"),
            s.get("Deadline_Date")
        )
        
        try:
            conn.execute(query, values)
            count += 1
        except Exception as e:
            print(f"Failed to insert {title}: {e}")

    conn.commit()
    print(f"Successfully uploaded {count} new scholarships to Turso!")

if __name__ == "__main__":
    main()
