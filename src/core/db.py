"""
Database connection and query helpers for Turso.
"""

import json
import libsql_experimental as libsql
from core.config import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN


def get_db_connection():
    """Get a connection to the Turso database."""
    return libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)


def get_existing_classified_keys():
    """Return a set of (title, organization) tuples for scholarships that are already classified in Turso."""
    try:
        conn = get_db_connection()
        # A scholarship is considered classified if attributes is not null/empty
        query = """
        SELECT title, organization
        FROM scholarships 
        WHERE attributes IS NOT NULL AND attributes != '{}' AND attributes != 'null'
        """
        rows = conn.execute(query).fetchall()
        return {(row[0].strip().lower(), row[1].strip().lower()) for row in rows if row[0] and row[1]}
    except Exception as e:
        print(f"Warning: Could not fetch existing keys from Turso: {e}")
        return set()


def get_existing_scholarship_keys():
    """Return a set of (title, organization) tuples for all scholarships currently in Turso."""
    try:
        conn = get_db_connection()
        query = "SELECT title, organization FROM scholarships"
        rows = conn.execute(query).fetchall()
        return {(row[0].strip().lower(), row[1].strip().lower()) for row in rows if row[0] and row[1]}
    except Exception as e:
        print(f"Warning: Could not fetch existing scholarship keys from Turso: {e}")
        return set()


def get_unclassified_scholarships(limit=10, force_all=False):
    """Fetch scholarships that haven't been classified yet."""
    conn = get_db_connection()

    if force_all:
        query = """
        SELECT id, title, organization, qualifications, level_of_study, criteria, purpose, focus
        FROM scholarships 
        LIMIT ?
        """
    else:
        query = """
        SELECT id, title, organization, qualifications, level_of_study, criteria, purpose, focus
        FROM scholarships 
        WHERE attributes IS NULL OR attributes = '{}' OR attributes = 'null'
        LIMIT ?
        """

    rows = conn.execute(query, (limit,)).fetchall()

    scholarships = []
    for row in rows:
        scholarship = {
            "id": row[0],
            "Title": row[1],
            "Organization": row[2],
            "Qualifications": row[3],
            "Level of Study": row[4],
            "Criteria": row[5],
            "Purpose": row[6],
            "Focus": row[7]
        }
        # Filter out None values to match existing behavior
        scholarships.append({k: v for k, v in scholarship.items() if v is not None})

    return scholarships


def update_scholarship_classification(scholarship_id, attributes, specific_requirements, criteria=None, submission_requirements=None, errors=None):
    """Write classification results back to Turso."""
    conn = get_db_connection()

    query = """
    UPDATE scholarships 
    SET attributes = ?, specific_requirements = ?, criteria_extracted = ?, submission_requirements = ?
    WHERE id = ?
    """

    attr_json = json.dumps(attributes) if attributes else None
    reqs_json = json.dumps(specific_requirements) if specific_requirements else None
    criteria_json = json.dumps(criteria) if criteria else None
    sub_reqs_json = json.dumps(submission_requirements) if submission_requirements else None

    conn.execute(query, (attr_json, reqs_json, criteria_json, sub_reqs_json, scholarship_id))
    conn.commit()
