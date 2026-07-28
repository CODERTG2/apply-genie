"""
Migration: wrap single_select scholarship attributes from bare strings to arrays.

User profiles are single-select (a user lives in ONE country), but scholarships
can accept multiple valid values ("US or Canadian residents").  The new convention
is that ALL of these fields are stored as JSON arrays on the scholarship side so
that matching logic simply checks  user_value IN scholarship_list.

Affected fields:
  country_of_residence, citizenship_status, enrollment_status,
  disability, financial_need, lgbtq, gender

Safe to re-run: already-array values are left untouched.
"""

import json
import sys
import os

# Fields that must be arrays on the scholarship side
SINGLE_SELECT_TO_ARRAY = {
    "country_of_residence",
    "citizenship_status",
    "enrollment_status",
    "disability",
    "financial_need",
    "lgbtq",
    "gender",
}


def migrate(filepath: str) -> None:
    with open(filepath, "r", encoding="utf-8") as f:
        scholarships = json.load(f)

    changed = 0
    for s in scholarships:
        attrs = s.get("Attributes", {})
        for field in SINGLE_SELECT_TO_ARRAY:
            if field in attrs:
                val = attrs[field]
                if isinstance(val, str):
                    attrs[field] = [val]
                    changed += 1
                # lists are already correct — leave them alone

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(scholarships, f, indent=3)

    print(f"Done. Converted {changed} bare-string values to arrays in '{filepath}'.")


if __name__ == "__main__":
    files = sys.argv[1:] if len(sys.argv) > 1 else ["scholarships_test.json"]
    for filepath in files:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        print(f"Migrating: {filepath}")
        migrate(filepath)
