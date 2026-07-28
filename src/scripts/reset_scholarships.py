#!/usr/bin/env python3
"""
Reset scholarship JSON files by stripping classification output fields.
Usage:
    python execution/reset_scholarships.py                        # resets scholarships_test.json
    python execution/reset_scholarships.py scholarships.json      # resets the full dataset
    python execution/reset_scholarships.py scholarships_test.json scholarships.json  # resets multiple
"""

import json
import sys
from pathlib import Path

FIELDS_TO_STRIP = ["Attributes", "SpecificRequirements", "ClassificationErrors"]

def reset_file(filepath: str):
    path = Path(filepath)
    if not path.exists():
        print(f"ERROR: {filepath} not found")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    stripped = 0
    for scholarship in data:
        for field in FIELDS_TO_STRIP:
            if field in scholarship:
                del scholarship[field]
                stripped += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=3)

    print(f"✓ {filepath}: reset {len(data)} scholarships (removed {stripped} fields)")

if __name__ == "__main__":
    files = sys.argv[1:] if len(sys.argv) > 1 else ["scholarships_test.json"]
    for f in files:
        reset_file(f)
