"""
Matching Engine.

Calculates a match percentage based on how many of the scholarship's
requirements are met by the user's profile.
No strict disqualification — higher percentage = better match.
"""

import json

def load_scholarships(filename="scholarships.json"):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def match_selectable(user_value, scholarship_value):
    if scholarship_value is None:
        return True
    if user_value is None:
        return False

    u_vals = [user_value] if isinstance(user_value, str) else user_value
    s_vals = [scholarship_value] if isinstance(scholarship_value, str) else scholarship_value

    if "Any" in s_vals:
        return True

    return bool(set(v.lower() for v in u_vals) & set(v.lower() for v in s_vals))

def match_numeric(user_value, scholarship_value):
    if scholarship_value is None:
        return True
    if user_value is None:
        return False

    try:
        user_num = float(user_value)
    except (ValueError, TypeError):
        return False

    if isinstance(scholarship_value, (int, float)):
        return user_num >= scholarship_value

    if isinstance(scholarship_value, dict):
        min_val = scholarship_value.get("min")
        max_val = scholarship_value.get("max")
        if min_val is not None and user_num < min_val:
            return False
        if max_val is not None and user_num > max_val:
            return False
        return True
    return False

def match_boolean(user_value, scholarship_value):
    if scholarship_value is None:
        return True
    if user_value is None:
        return False
    return scholarship_value == user_value

def match_entity(user_value, scholarship_value):
    if scholarship_value is None:
        return True
    if user_value is None:
        return False
        
    u_vals = [user_value.lower()] if isinstance(user_value, str) else [v.lower() for v in user_value]
    s_vals = [scholarship_value.lower()] if isinstance(scholarship_value, str) else [v.lower() for v in scholarship_value]
    
    return bool(set(u_vals) & set(s_vals))

# Group attributes by match logic
SELECTABLE_ATTRS = ["gender", "race", "ethnicity", "lgbtq", "country_of_residence", "us_state", "canadian_province", "citizenship_status", "visa_type", "education_type", "degree_pursuing", "year_of_study", "enrollment_status", "institution_type", "financial_need", "military", "disability"]
NUMERIC_ATTRS = ["age", "gpa", "credit_hours_completed", "sat_score", "act_score"]
BOOLEAN_ATTRS = ["first_generation", "foster_care", "community_service"]
ENTITY_ATTRS = ["us_county_city", "field_of_study", "minor", "institution_name", "memberships", "medical_condition_detail", "career_goals"]

def match_scholarship(user_profile, scholarship):
    attrs = scholarship.get("Attributes", {})
    if not attrs:
        return {"match_score": 0, "matched": [], "missed": [], "specific_requirements": scholarship.get("SpecificRequirements", [])}

    matched = []
    missed = []

    for attr in SELECTABLE_ATTRS:
        if attr in attrs:
            if match_selectable(user_profile.get(attr), attrs[attr]):
                matched.append(attr)
            else:
                missed.append(attr)

    for attr in NUMERIC_ATTRS:
        if attr in attrs:
            if match_numeric(user_profile.get(attr), attrs[attr]):
                matched.append(attr)
            else:
                missed.append(attr)

    for attr in BOOLEAN_ATTRS:
        if attr in attrs:
            if match_boolean(user_profile.get(attr), attrs[attr]):
                matched.append(attr)
            else:
                missed.append(attr)

    for attr in ENTITY_ATTRS:
        if attr in attrs:
            if match_entity(user_profile.get(attr), attrs[attr]):
                matched.append(attr)
            else:
                missed.append(attr)
                
    # other_test_scores handling
    if "other_test_scores" in attrs:
        s_tests = attrs["other_test_scores"]
        u_tests = user_profile.get("other_test_scores", {})
        if isinstance(s_tests, dict):
            for test_name, req in s_tests.items():
                attr_name = f"test_{test_name}"
                if test_name in u_tests and match_numeric(u_tests[test_name], req):
                    matched.append(attr_name)
                else:
                    missed.append(attr_name)

    total = len(matched) + len(missed)
    score = len(matched) / total if total > 0 else 1.0

    return {
        "match_score": score,
        "matched": matched,
        "missed": missed,
        "specific_requirements": scholarship.get("SpecificRequirements", [])
    }

def find_matching_scholarships(user_profile, scholarships):
    results = []
    for i, s in enumerate(scholarships):
        if "Attributes" not in s: continue
        res = match_scholarship(user_profile, s)
        res["title"] = s.get("Title", "Unknown")
        res["index"] = i
        results.append(res)
    
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="user_profile.json")
    parser.add_argument("--scholarships", default="scholarships_test.json")
    args = parser.parse_args()

    with open(args.profile, "r") as f:
        user_profile = json.load(f)

    scholarships = load_scholarships(args.scholarships)
    results = find_matching_scholarships(user_profile, scholarships)
    
    for r in results[:10]:
        print(f"[{r['match_score']:.0%}] {r['title']}")
        if r['missed']: print(f"  Missed: {', '.join(r['missed'])}")
