#!/usr/bin/env python3
"""
Delete expired scholarships that haven't been saved by any user.

Criteria for deletion:
  - deadline_date is not null AND the earliest parseable date within it is before today
  - title is NOT referenced in saved_scholarships.scholarship_title (no user has saved it)

Usage:
    python src/scripts/delete_expired_scholarships.py          # dry-run (preview only)
    python src/scripts/delete_expired_scholarships.py --delete  # actually delete

Notes:
    - Uses the TURSO_DATABASE_URL and TURSO_AUTH_TOKEN from .env
    - deadline_date values are LLM-extracted human-readable strings (e.g. "August 31, 2026").
      Some contain multiple dates or LLM noise — we extract the earliest parseable date.
    - Scholarships without any parseable deadline_date are never deleted.
    - Scholarships saved by any user are preserved even if expired.
"""

import sys
import re
import argparse
from pathlib import Path
from datetime import date, datetime

# Ensure src root is in sys.path
_SRC_ROOT = Path(__file__).resolve().parent.parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from core.db import get_db_connection


# ── Date Parsing ─────────────────────────────────────────────────────────────

# Common formats the LLM produces
_DATE_FORMATS = [
    "%B %d, %Y",   # August 31, 2026
    "%B %d %Y",    # August 31 2026
    "%b %d, %Y",   # Aug 31, 2026
    "%b %d %Y",    # Aug 31 2026
    "%m/%d/%Y",    # 08/31/2026
    "%Y-%m-%d",    # 2026-08-31
]

# Regex to pull date-like tokens from noisy LLM output
_DATE_PATTERN = re.compile(
    r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|'
    r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    r'\s+\d{1,2},?\s+\d{4}\b',
    re.IGNORECASE
)


def parse_earliest_date(deadline_date_str: str) -> date | None:
    """
    Extract the earliest parseable date from a potentially noisy LLM deadline string.
    Returns None if no valid date can be found.
    """
    if not deadline_date_str:
        return None

    candidates = _DATE_PATTERN.findall(deadline_date_str)
    # Also try the whole string in case it's a clean single date
    candidates.append(deadline_date_str.strip().split("\n")[0].strip())

    parsed = []
    for token in candidates:
        token = token.strip().rstrip(",")
        for fmt in _DATE_FORMATS:
            try:
                parsed.append(datetime.strptime(token, fmt).date())
                break
            except ValueError:
                continue

    return min(parsed) if parsed else None


# ── DB Queries ────────────────────────────────────────────────────────────────

def fetch_all_candidates(conn) -> list[dict]:
    """
    Fetch scholarships that:
      1. Have a non-null deadline_date
      2. Are NOT saved by any user
    Returns all of them; date filtering is done in Python (since dates are freeform text).
    """
    query = """
    SELECT s.id, s.title, s.organization, s.deadline_date
    FROM scholarships s
    WHERE s.deadline_date IS NOT NULL
      AND s.title NOT IN (
          SELECT DISTINCT scholarship_title FROM saved_scholarships
      )
    ORDER BY s.id
    """
    rows = conn.execute(query).fetchall()
    return [
        {"id": row[0], "title": row[1], "organization": row[2], "deadline_date": row[3]}
        for row in rows
    ]


def find_expired(candidates: list[dict], today: date) -> list[dict]:
    """Filter candidates to those whose earliest parseable date is before today."""
    expired = []
    for s in candidates:
        earliest = parse_earliest_date(s["deadline_date"])
        if earliest is not None and earliest < today:
            s["_parsed_date"] = earliest
            expired.append(s)
    return expired


def delete_by_ids(conn, ids: list[int]) -> None:
    """Delete scholarships by a list of IDs."""
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM scholarships WHERE id IN ({placeholders})", tuple(ids))
    conn.commit()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Delete expired scholarships not saved by any user."
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete the records. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()

    today = date.today()
    print(f"Today: {today.isoformat()}")
    print(f"Mode:  {'🗑  DELETE' if args.delete else '🔍 DRY RUN (pass --delete to execute)'}")
    print("-" * 70)

    conn = get_db_connection()

    # 1. Fetch all unsaved scholarships with a deadline_date
    candidates = fetch_all_candidates(conn)
    print(f"Unsaved scholarships with a deadline_date: {len(candidates)}")

    # 2. Filter to those that have actually expired
    expired = find_expired(candidates, today)

    if not expired:
        print("✅ No expired, unsaved scholarships found. Nothing to delete.")
        return

    print(f"Expired (deadline before {today}): {len(expired)}\n")
    for s in expired:
        title_short = s["title"][:55].ljust(55)
        print(f"  [{s['id']:>5}] {title_short}  deadline: {s['_parsed_date']}  (raw: {s['deadline_date'][:40]!r})")

    if not args.delete:
        print(
            f"\n⚠️  Dry-run complete. Run with --delete to permanently remove "
            f"these {len(expired)} scholarship(s)."
        )
        return

    # 3. Delete
    ids_to_delete = [s["id"] for s in expired]
    print(f"\n⚠️  Deleting {len(ids_to_delete)} scholarship(s)...")
    delete_by_ids(conn, ids_to_delete)
    print(f"✅ Successfully deleted {len(ids_to_delete)} expired, unsaved scholarship(s).")


if __name__ == "__main__":
    main()
