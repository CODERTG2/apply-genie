"""
User Profiling Module — Zero LLM calls.

Walks the question tree defined in attribute_schema.json and collects
structured user answers. Questions are presented in order, with branching
based on depends_on conditions.
"""

import sys
from pathlib import Path

# Ensure src root is in sys.path
_SRC_ROOT = Path(__file__).resolve().parent.parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import json
from core.schemas import load_schema, load_entity_db


def check_dependency(depends_on, user_profile):
    """
    Check if a question's dependency is met.
    
    depends_on format: {"attr_name": ["value1", "value2"]} or {"attr_name": "*"}
    "*" means any non-null answer to the dependency attribute.
    
    Returns True if the dependency is met (question should be shown).
    """
    if not depends_on:
        return True

    for dep_attr, dep_values in depends_on.items():
        user_answer = user_profile.get(dep_attr)

        # If the dependency attribute hasn't been answered, dependency not met
        if user_answer is None:
            return False

        # "*" means any answer is fine
        if dep_values == "*":
            continue

        # Check if user's answer matches any of the allowed dependency values
        if isinstance(user_answer, list):
            # Multi-select: at least one value must match
            if not any(v in dep_values for v in user_answer):
                return False
        elif isinstance(user_answer, bool):
            if user_answer not in dep_values:
                return False
        else:
            if user_answer not in dep_values:
                return False

    return True


def get_next_questions(schema, user_profile):
    """
    Return the list of questions the user should answer next.
    
    Filters out:
    - Already answered questions
    - Questions whose dependencies are not met
    
    Returns list of (attr_name, attr_definition) tuples, sorted by order.
    """
    questions = []
    for attr_name, attr_def in schema.items():
        # Skip if already answered
        if attr_name in user_profile:
            continue

        # Check dependencies
        depends_on = attr_def.get("depends_on")
        if depends_on and not check_dependency(depends_on, user_profile):
            continue

        questions.append((attr_name, attr_def))

    # Sort by order
    questions.sort(key=lambda x: x[1].get("order", 999))
    return questions


def format_question_for_cli(attr_name, attr_def, entity_db):
    """Format a question for CLI display, showing options."""
    q = attr_def["question"]
    attr_type = attr_def["type"]
    lines = [f"\n  {q}"]

    if attr_type in ("single_select", "multi_select"):
        options = attr_def.get("pre_seeded", [])
        if attr_type == "multi_select":
            lines.append("  (Select all that apply, comma-separated)")
        for i, opt in enumerate(options, 1):
            lines.append(f"    {i}. {opt}")

    elif attr_type in ("entity_lookup", "entity_lookup_multi"):
        db_key = attr_def.get("db_key", "")
        known = entity_db.get(db_key, [])
        if known:
            lines.append(f"  (Type to search. {len(known)} known entries. Examples: {', '.join(known[:5])}...)")
        else:
            lines.append("  (Type your answer)")
        if attr_type == "entity_lookup_multi":
            lines.append("  (Comma-separated for multiple)")

    elif attr_type == "numeric":
        na_label = attr_def.get("na_label", "N/A")
        lines.append(f"  (Enter a number, or type 'na' for {na_label})")

    elif attr_type == "boolean":
        lines.append("  (yes/no)")

    elif attr_type == "text":
        if attr_def.get("optional"):
            lines.append("  (Press Enter to skip)")

    elif attr_type == "numeric_entity_map":
        db_key = attr_def.get("db_key", "")
        known = entity_db.get(db_key, [])
        lines.append(f"  (Known tests: {', '.join(known)})")
        lines.append("  (Format: TEST_NAME:SCORE, comma-separated. Press Enter to skip)")

    return "\n".join(lines)


def parse_answer(raw_input, attr_def, entity_db):
    """
    Parse user's raw input into the appropriate data type.
    Returns the parsed value or None if skipped.
    """
    raw = raw_input.strip()
    attr_type = attr_def["type"]

    if not raw:
        if attr_def.get("optional") or attr_def.get("optional_na"):
            return None
        return None  # Will be caught by caller as "please answer"

    if attr_type == "single_select":
        options = attr_def.get("pre_seeded", [])
        # Try by number
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        # Try by exact match (case-insensitive)
        for opt in options:
            if opt.lower() == raw.lower():
                return opt
        # Fuzzy: check if input starts with any option
        for opt in options:
            if opt.lower().startswith(raw.lower()):
                return opt
        return raw  # Let it through, validation can catch later

    elif attr_type == "multi_select":
        options = attr_def.get("pre_seeded", [])
        parts = [p.strip() for p in raw.split(",")]
        results = []
        for part in parts:
            # Try by number
            try:
                idx = int(part) - 1
                if 0 <= idx < len(options):
                    results.append(options[idx])
                    continue
            except ValueError:
                pass
            # Try by match
            matched = False
            for opt in options:
                if opt.lower() == part.lower() or opt.lower().startswith(part.lower()):
                    results.append(opt)
                    matched = True
                    break
            if not matched:
                results.append(part)
        return results

    elif attr_type == "numeric":
        if raw.lower() in ("na", "n/a", "none", "skip"):
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    elif attr_type == "boolean":
        if raw.lower() in ("yes", "y", "true", "1"):
            return True
        elif raw.lower() in ("no", "n", "false", "0"):
            return False
        return None

    elif attr_type in ("entity_lookup", "entity_lookup_multi"):
        if attr_type == "entity_lookup_multi":
            parts = [p.strip() for p in raw.split(",")]
            return [p for p in parts if p]
        return raw

    elif attr_type == "text":
        return raw

    elif attr_type == "numeric_entity_map":
        # Format: "LSAT:175, MCAT:510"
        if raw.lower() in ("na", "n/a", "none", "skip", ""):
            return None
        result = {}
        parts = [p.strip() for p in raw.split(",")]
        for part in parts:
            if ":" in part:
                test_name, score = part.split(":", 1)
                try:
                    result[test_name.strip().upper()] = float(score.strip())
                except ValueError:
                    pass
        return result if result else None

    return raw


def run_profiling_cli():
    """
    Run the profiling questionnaire in the terminal.
    Returns a structured user_profile dict.
    """
    schema = load_schema()
    entity_db = load_entity_db()
    user_profile = {}

    print("=" * 60)
    print("  Scholarship Eligibility Profile")
    print("  Answer the following questions to find matching scholarships.")
    print("=" * 60)

    while True:
        questions = get_next_questions(schema, user_profile)
        if not questions:
            break

        # Present the next question
        attr_name, attr_def = questions[0]
        prompt = format_question_for_cli(attr_name, attr_def, entity_db)
        print(prompt)

        raw = input("  > ").strip()

        # Handle skip for optional questions
        if not raw and (attr_def.get("optional") or attr_def.get("optional_na")):
            user_profile[attr_name] = None
            continue

        if not raw:
            print("  ⚠ Please provide an answer.")
            continue

        answer = parse_answer(raw, attr_def, entity_db)
        if answer is not None:
            user_profile[attr_name] = answer
        else:
            user_profile[attr_name] = None  # Mark as answered but N/A

    # Clean up None values
    user_profile = {k: v for k, v in user_profile.items() if v is not None}

    print("\n" + "=" * 60)
    print("  Profile Complete!")
    print("=" * 60)
    print(json.dumps(user_profile, indent=2))

    return user_profile


def save_profile(user_profile, filename="user_profile.json"):
    """Save the user profile to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(user_profile, f, indent=2)
    print(f"Profile saved to {filename}")


if __name__ == "__main__":
    profile = run_profiling_cli()
    save_profile(profile)
