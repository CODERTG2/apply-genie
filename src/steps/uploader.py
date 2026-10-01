"""
Step 6: Upload scholarships to Turso database.

Combines logic from upload_to_turso.py (base insert) 
and apply_dry_run.py (classification update).
"""

import json
from core.db import get_db_connection

def upload_scholarship(scholarship: dict, conn) -> None:
    """Upsert a single scholarship to Turso."""
    
    title = scholarship.get("Title")
    org = scholarship.get("Organization")
    
    if not title or not org:
        return

    # Check if already exists by title and organization
    existing = conn.execute(
        "SELECT id FROM scholarships WHERE title = ? AND organization = ?",
        (title, org)
    ).fetchone()
    
    if existing:
        scholarship_id = existing[0]
    else:
        # 1. Base Insert if it doesn't exist yet
        insert_query = """
        INSERT INTO scholarships (
            title, organization, link, emails, phone_number,
            level_of_study, award_type, purpose, focus, qualifications, criteria,
            funds, duration, number_of_awards, to_apply, deadline, contact,
            for_more_information, month
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """
        
        emails = scholarship.get("Emails")
        emails_json = json.dumps(emails) if emails else None
        
        more_info = scholarship.get("For more information") or scholarship.get("for_more_information")
        more_info_json = json.dumps(more_info) if more_info else None
        
        cursor = conn.execute(insert_query, (
            title,
            org,
            scholarship.get("Link"),
            emails_json,
            scholarship.get("Phone Number"),
            scholarship.get("Level of Study"),
            scholarship.get("Award Type"),
            scholarship.get("Purpose"),
            scholarship.get("Focus"),
            scholarship.get("Qualifications"),
            scholarship.get("Criteria"),
            scholarship.get("Funds"),
            scholarship.get("Duration"),
            scholarship.get("Number of Awards"),
            scholarship.get("To Apply"),
            scholarship.get("Deadline"),
            scholarship.get("Contact"),
            more_info_json,
            scholarship.get("Month")
        ))
        
        # Get newly inserted ID
        id_row = conn.execute("SELECT id FROM scholarships WHERE title = ? AND organization = ?", (title, org)).fetchone()
        scholarship_id = id_row[0] if id_row else None

    if not scholarship_id:
        return

    # 2. Update Classifications (Attributes, Requirements, Criteria, Deadline_Date)
    update_query = """
    UPDATE scholarships 
    SET attributes = ?, 
        specific_requirements = ?, 
        criteria_extracted = ?, 
        submission_requirements = ?,
        deadline_date = ?
    WHERE id = ?
    """
    
    attributes = scholarship.get("Attributes")
    reqs = scholarship.get("SpecificRequirements")
    criteria = scholarship.get("Criteria_Extracted")
    sub_reqs = scholarship.get("SubmissionRequirements")
    deadline_date = scholarship.get("Deadline_Date")
    
    # Only update if we actually ran the classification/dates steps
    if any([attributes, reqs, criteria, sub_reqs, deadline_date]):
        conn.execute(update_query, (
            json.dumps(attributes) if attributes else None,
            json.dumps(reqs) if reqs else None,
            json.dumps(criteria) if criteria else None,
            json.dumps(sub_reqs) if sub_reqs else None,
            deadline_date,
            scholarship_id
        ))
        
    conn.commit()

def upload_batch(scholarships: list) -> None:
    """Upload a batch of scholarships."""
    conn = get_db_connection()
    from tqdm import tqdm
    for scholarship in tqdm(scholarships, desc="Uploading to Turso"):
        upload_scholarship(scholarship, conn)
