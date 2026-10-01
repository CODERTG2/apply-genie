import os
import sys
import json

from pathlib import Path

# Add src root to sys.path
_SRC_ROOT = Path(__file__).resolve().parent.parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from core.db import get_db_connection, update_scholarship_classification
from core.config import CLASSIFICATIONS_PATH

def apply_dry_run(file_path=None):
    if file_path is None:
        file_path = str(CLASSIFICATIONS_PATH if CLASSIFICATIONS_PATH.exists() else _PROJECT_ROOT / "dry_run_classifications.json")

    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    print(f"Loading {file_path}...")
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("Error: Could not parse JSON file.")
            return

    if not data:
        print("File is empty. Nothing to apply.")
        return

    print(f"Found {len(data)} classifications to apply.")
    
    conn = db.get_db_connection()
    
    count = 0
    for result in data:
        title = result.get("Title")
        org = result.get("Organization")
        
        attributes = result.get("Attributes")
        specific_requirements = result.get("SpecificRequirements")
        criteria = result.get("Criteria_Extracted")
        submission_requirements = result.get("SubmissionRequirements")
        errors = result.get("Errors")
        
        # Try to match by title and org if they exist, otherwise fallback to ID
        s_id = None
        if title and org:
            existing = conn.execute(
                "SELECT id FROM scholarships WHERE title = ? AND organization = ?",
                (title, org)
            ).fetchone()
            if existing:
                s_id = existing[0]
        
        if not s_id:
            try:
                s_id = int(result.get("id"))
            except (ValueError, TypeError):
                print(f"Skipping entry without valid ID and no match found for title '{title}'")
                continue
        
        try:
            update_scholarship_classification(
                scholarship_id=s_id,
                attributes=attributes,
                specific_requirements=specific_requirements,
                criteria=criteria,
                submission_requirements=submission_requirements,
                errors=errors
            )
            count += 1
            if count % 10 == 0:
                print(f"Applied {count}/{len(data)}...")
        except Exception as e:
            print(f"Failed to update scholarship ID {s_id}: {e}")

    print(f"Successfully applied {count} classifications to the database!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Apply dry run classifications to the database")
    parser.add_argument("--file", default="dry_run_classifications.json", help="Path to the dry run JSON file")
    args = parser.parse_args()
    
    apply_dry_run(args.file)
