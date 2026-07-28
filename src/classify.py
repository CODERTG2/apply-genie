import json
import re
import os
from tqdm import tqdm
from google import genai
from google.genai import types


def load_schema():
    with open("attribute_schema.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_entity_db():
    with open("entity_db.json", "r", encoding="utf-8") as f:
        return json.load(f)


def save_entity_db(entity_db):
    with open("entity_db.json", "w", encoding="utf-8") as f:
        json.dump(entity_db, f, indent=2)


def build_classification_prompt(scholarship_text, schema, entity_db):
    """Build the prompt that asks the LLM to classify a scholarship."""

    # Build the allowed-values reference from the schema
    schema_ref_lines = []
    for attr_name, attr in sorted(schema.items(), key=lambda x: x[1]["order"]):
        if attr["type"] in ("single_select", "multi_select"):
            values = ", ".join(attr["pre_seeded"])
            schema_ref_lines.append(f'  {attr_name} ({attr["type"]}): [{values}]')
        elif attr["type"] in ("entity_lookup", "entity_lookup_multi"):
            db_key = attr.get("db_key", "")
            examples = entity_db.get(db_key, [])[:15]
            schema_ref_lines.append(f'  {attr_name} (pick from known or add new): [{", ".join(examples)}, ...]')
        elif attr["type"] == "numeric":
            comp = attr.get("comparison", ">=")
            schema_ref_lines.append(f'  {attr_name} (numeric, comparison: {comp}): extract the number')
        elif attr["type"] == "boolean":
            schema_ref_lines.append(f'  {attr_name} (boolean): true or false')
        elif attr["type"] == "text":
            schema_ref_lines.append(f'  {attr_name} (text): free text value')
        elif attr["type"] == "numeric_entity_map":
            db_key = attr.get("db_key", "")
            examples = entity_db.get(db_key, [])[:10]
            schema_ref_lines.append(f'  {attr_name} (test_name: score): known tests: [{", ".join(examples)}]')

    schema_ref = "\n".join(schema_ref_lines)

    prompt = f"""You are classifying a scholarship's eligibility requirements into structured attributes.

SCHOLARSHIP TEXT:
{scholarship_text}

ATTRIBUTES (use ONLY these values for selectable fields):
{schema_ref}

CRITICAL RULES:
1. DECOMPOSE compound requirements into separate attributes.
   "High School Senior" → education_type: ["High School"], year_of_study: ["High School Senior"]
   "Full-time undergraduate" → enrollment_status: "Full-Time", education_type: ["Undergraduate"]
   "Junior or Senior with 3.0 GPA" → year_of_study: ["College Junior", "College Senior"], gpa: {{"min": 3.0}}
   "Associate Degree, Bachelor's Degree, or Graduate Degree" → education_type: ["Undergraduate", "Graduate"], degree_pursuing: ["Associate's", "Bachelor's", "Master's", "Doctoral"]
   "Bachelor's or Graduate program" → education_type: ["Undergraduate", "Graduate"], degree_pursuing: ["Bachelor's", "Master's", "Doctoral"]

2. education_type, degree_pursuing, and year_of_study are MULTI-SELECT. Always output them as a JSON array, even if only one value.
   Correct:   "education_type": ["Undergraduate"]
   Incorrect: "education_type": "Undergraduate"

2b. The following attributes are single-select for the USER (a user has one country, one citizenship, etc.), but a SCHOLARSHIP can accept multiple valid values (e.g. "US or Canadian residents").
    ALWAYS output these as a JSON array on the scholarship side, even if only one value applies:
      country_of_residence, citizenship_status, enrollment_status, disability, financial_need, lgbtq, gender
    Correct:   "country_of_residence": ["United States", "Canada"]
    Correct:   "country_of_residence": ["United States"]   ← still an array even if only one
    Incorrect: "country_of_residence": "United States"

    Example decompositions:
      "US or Canadian residents" → country_of_residence: ["United States", "Canada"]
      "US citizen or permanent resident" → citizenship_status: ["US Citizen", "US Permanent Resident"]
      "Full-time or part-time students" → enrollment_status: ["Full-Time", "Part-Time"]
      "Open to all genders" → omit gender (no restriction)
      "Women only" → gender: ["Female"]

3. For selectable attributes (single_select, multi_select), ONLY use values from the provided list.
   If none fit, leave as null (do NOT invent values).

4. For numeric attributes, extract the NUMBER and use this format:
   "GPA of 3.0 or higher" → gpa: {{"min": 3.0}}
   "Under 25 years old" → age: {{"max": 25}}
   "Between 17 and 30" → age: {{"min": 17, "max": 30}}
   "30+ credit hours" → credit_hours_completed: {{"min": 30}}

5. For requirements that don't fit ANY attribute, add them to "specific_requirements" with:
   - "type": "include" or "exclude"
   - "description": short human-readable description
   - "category_hint": a short category label for grouping similar requirements
   - "source_text": the original text from the scholarship

5. For any new entities discovered (organizations, schools, test types, medical conditions, fields),
   add them to "new_entities" grouped by entity type.

5b. `visa_type` is a DEPENDENT field — only set it when the scholarship explicitly names a specific visa type
    (e.g., "F-1", "J-1", "H-4"). If the scholarship only says "valid student visa" or "hold a visa" without
    naming the type, omit `visa_type` entirely. The `citizenship_status: ["US Visa Holder"]` is sufficient.
    Correct:   scholarship says "F-1 student visa" → visa_type: "F-1 (Student)"
    Correct:   scholarship says "valid student visa" → omit visa_type
    Incorrect: scholarship says "valid student visa" → visa_type: "Other"

6. If the scholarship does not specify a requirement for an attribute, omit it (don't set to null).

Return ONLY valid JSON with this structure (no markdown, no explanation):
{{
  "attributes": {{
    "attribute_name": value_or_object,
    ...
  }},
  "specific_requirements": [
    {{
      "type": "include",
      "description": "...",
      "category_hint": "...",
      "source_text": "..."
    }}
  ],
  "new_entities": {{
    "memberships": [],
    "schools": [],
    "fields_of_study": [],
    "test_types": [],
    "medical_conditions": [],
    "career_fields": []
  }}
}}"""

    return prompt


# --- Deterministic Validation ---

# Note: these are matched with word boundaries to avoid false positives (e.g. 'degree' containing 'gre')
KEYWORD_ATTR_MAP = {
    "gpa": "gpa",
    "grade point": "gpa",
    "full-time": "enrollment_status",
    "full time": "enrollment_status",
    "part-time": "enrollment_status",
    "part time": "enrollment_status",
    "freshman": "year_of_study",
    "sophomore": "year_of_study",
    "junior": "year_of_study",
    "senior": "year_of_study",
    "u.s. citizen": "citizenship_status",
    "us citizen": "citizenship_status",
    "united states citizen": "citizenship_status",
    "permanent resident": "citizenship_status",
    "canadian citizen": "citizenship_status",
    "female": "gender",
    "women": "gender",
    "male": "gender",
    "veteran": "military",
    "active duty": "military",
    "military": "military",
    "african american": "race",
    "hispanic": "ethnicity",
    "latino": "ethnicity",
    "native american": "race",
    "pacific islander": "race",
    "financial need": "financial_need",
    "fafsa": "financial_need",
    "sat ": "sat_score",
    "act ": "act_score",
    "lsat": "other_test_scores",
    "mcat": "other_test_scores",
    r"\bgre\b": "other_test_scores",   # word boundary to avoid matching 'degree'
    "first-generation": "first_generation",
    "first generation": "first_generation",
    "foster care": "foster_care",
    "disability": "disability",
    "lgbtq": "lgbtq",
    "community service": "community_service",
    "volunteer": "community_service",
}


def validate_classification(result, schema, scholarship_text):
    """
    Deterministic validation of LLM classification output.
    Returns a list of error strings. Empty list = valid.
    """
    errors = []
    attributes = result.get("attributes", {})

    # 1. Value-in-set check for selectable attributes
    for attr_name, value in attributes.items():
        if attr_name not in schema:
            continue
        attr_def = schema[attr_name]

        if attr_def["type"] == "single_select" and attr_def.get("allow_new") is False:
            allowed = attr_def["pre_seeded"]
            # On the scholarship side, single_select fields are output as arrays
            # (a scholarship can accept multiple valid values, e.g. "US or Canadian residents")
            if isinstance(value, list):
                for v in value:
                    if v not in allowed:
                        errors.append(f"Invalid value '{v}' for {attr_name}. Allowed: {allowed}")
            elif isinstance(value, str):
                # Tolerate a bare string but flag it as a formatting issue (not a hard error)
                if value not in allowed:
                    errors.append(f"Invalid value '{value}' for {attr_name}. Allowed: {allowed}")
                else:
                    errors.append(
                        f"{attr_name} should be a JSON array even for single values, got bare string '{value}'. "
                        f"Use [\"{value}\"] instead."
                    )

        elif attr_def["type"] == "multi_select" and attr_def.get("allow_new") is False:
            allowed = attr_def["pre_seeded"]
            if isinstance(value, list):
                for v in value:
                    if v not in allowed:
                        errors.append(f"Invalid value '{v}' for {attr_name}. Allowed: {allowed}")
            elif isinstance(value, str) and value not in allowed:
                errors.append(f"Invalid value '{value}' for {attr_name}. Should be a list from: {allowed}")

    # 2. Type check for numeric fields
    for attr_name in ["gpa", "age", "credit_hours_completed", "sat_score", "act_score"]:
        val = attributes.get(attr_name)
        if val is not None:
            if isinstance(val, dict):
                for k, v in val.items():
                    if k not in ("min", "max"):
                        errors.append(f"{attr_name} has invalid key '{k}'. Use 'min' and/or 'max'.")
                    elif not isinstance(v, (int, float)):
                        errors.append(f"{attr_name}.{k} should be numeric, got '{v}'")
            elif not isinstance(val, (int, float)):
                errors.append(f"{attr_name} should be numeric or {{min/max}}, got '{val}'")

    # 3. Keyword cross-reference: check for mentions in text not captured
    text_lower = scholarship_text.lower()
    for keyword, expected_attr in KEYWORD_ATTR_MAP.items():
        # Support regex patterns (prefixed with r"\b")
        if keyword.startswith(r"\b"):
            match = re.search(keyword, text_lower)
        else:
            match = keyword in text_lower
        
        if match:
            # Check if the expected attribute was extracted OR if it's in specific_requirements
            if expected_attr not in attributes:
                specific_texts = " ".join(
                    sr.get("source_text", "") + " " + sr.get("description", "")
                    for sr in result.get("specific_requirements", [])
                ).lower()
                plain_keyword = re.sub(r'\\b', '', keyword)
                if plain_keyword not in specific_texts:
                    errors.append(
                        f"Text mentions '{plain_keyword}' but '{expected_attr}' not in attributes or specific_requirements"
                    )

    # 4. Boolean fields should be bool
    for attr_name in ["first_generation", "foster_care", "community_service"]:
        val = attributes.get(attr_name)
        if val is not None and not isinstance(val, bool):
            errors.append(f"{attr_name} should be boolean, got '{val}'")

    return errors


def extract_json(text):
    """Extract JSON from LLM output, handling markdown code blocks."""
    # Try to find JSON in code blocks first
    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        clean = json_match.group(1).strip()
    else:
        clean = text.strip()

    # Try to find the outermost { } block
    start = clean.find('{')
    end = clean.rfind('}')
    if start != -1 and end != -1:
        clean = clean[start:end+1]

    return json.loads(clean)


def build_scholarship_text(scholarship):
    """Extract relevant text fields from a scholarship for classification."""
    parts = []
    if "Qualifications" in scholarship:
        parts.append(f"Qualifications: {scholarship['Qualifications']}")
    if "Level of Study" in scholarship:
        parts.append(f"Level of Study: {scholarship['Level of Study']}")
    if "Criteria" in scholarship:
        parts.append(f"Criteria: {scholarship['Criteria']}")
    if "Purpose" in scholarship:
        parts.append(f"Purpose: {scholarship['Purpose']}")
    if "Focus" in scholarship:
        parts.append(f"Focus: {scholarship['Focus']}")
    return "\n".join(parts)


def update_entity_db(entity_db, new_entities):
    """Merge new entities discovered by the LLM into the entity DB."""
    if not new_entities:
        return
    for key in ["memberships", "schools", "fields_of_study", "test_types", "medical_conditions", "career_fields"]:
        new_items = new_entities.get(key, [])
        if new_items and key in entity_db:
            existing = set(entity_db[key])
            for item in new_items:
                if isinstance(item, str) and item not in existing:
                    entity_db[key].append(item)
                    existing.add(item)


def classify_scholarship(scholarship_text, schema, entity_db, model="gemini-3.6-flash", api_key=None, max_retries=2):
    """
    Classify a single scholarship using the LLM.
    Returns (classification_dict, errors_list).
    """
    if not scholarship_text.strip():
        return None, ["No qualification text found"]

    prompt = build_classification_prompt(scholarship_text, schema, entity_db)
    last_result = None
    errors = []

    # Initialize the genai Client
    client = genai.Client(api_key=api_key) if api_key else genai.Client()

    for attempt in range(max_retries + 1):
        prompt_with_feedback = prompt
        if errors and last_result is not None:
            # Anchored retry: show the LLM its previous output so it patches
            # specific errors rather than regenerating the whole thing blind.
            # This prevents regressions where fixing one field drops another.
            prompt_with_feedback += (
                f"\n\nYour previous attempt produced this output:\n{json.dumps(last_result, indent=2)}"
                f"\n\nHowever it failed validation with these errors:\n{json.dumps(errors)}"
                f"\n\nFix ONLY the listed errors. Keep every other field exactly as-is. "
                f"Output the complete corrected JSON."
            )
        elif errors:
            prompt_with_feedback += (
                f"\n\nWARNING: Your previous attempt failed validation with these errors:\n{json.dumps(errors)}"
                f"\nPlease correct them and output strictly valid JSON."
            )
            
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt_with_feedback,
                config=types.GenerateContentConfig(
                    system_instruction="You are a scholarship eligibility classifier. Return ONLY valid JSON, no other text.",
                    temperature=0.1
                )
            )

            output = response.text
            print(f"\n--- LLM OUTPUT START ---\n{output[:500]}...\n--- LLM OUTPUT END ---")
            result = extract_json(output)

            # Validate
            validation_errors = validate_classification(result, schema, scholarship_text)

            # Regression check: on retries, flag any field from the previous
            # valid-ish output that silently disappeared (unless it had an error).
            if last_result is not None and validation_errors == []:
                prev_attrs = last_result.get("attributes", {})
                curr_attrs = result.get("attributes", {})
                errored_fields = {e.split("'")[1] for e in errors if "'" in e}
                for field, prev_val in prev_attrs.items():
                    if field not in curr_attrs and field not in errored_fields:
                        validation_errors.append(
                            f"Regression: field '{field}' was present in previous attempt but is now missing. "
                            f"Restore it unless the scholarship text doesn't require it."
                        )

            if not validation_errors:
                return result, []
            else:
                errors = validation_errors
                last_result = result
                print(f"Validation failed on attempt {attempt+1}: {validation_errors}")

        except json.JSONDecodeError:
            errors = [f"Failed to parse JSON from LLM output"]
        except Exception as e:
            errors = [f"LLM call failed: {str(e)}"]
            print(f"Attempt {attempt+1} failed: {e}")

    # Return the last result even with errors (better than nothing)
    try:
        return result, errors
    except NameError:
        return None, errors

def classify_batch(scholarships_file="scholarships.json", model="gemini-3.6-flash", api_key=None, evolution_interval=50):
    schema = load_schema()
    entity_db = load_entity_db()
    
    with open(scholarships_file, "r", encoding="utf-8") as f:
        scholarships = json.load(f)

    from schema_evolver import analyze_and_propose_evolution

    processed_since_evolution = 0
    total_processed = 0

    for n, scholarship in enumerate(tqdm(scholarships, desc="Classifying")):
        # Skip already classified
        if "Attributes" in scholarship:
            continue
            
        # Skip scholarships with no useful text
        text = build_scholarship_text(scholarship)
        if not text.strip():
            continue

        result, errors = classify_scholarship(text, schema, entity_db, model=model, api_key=api_key)

        if result:
            scholarship["Attributes"] = result.get("attributes", {})
            scholarship["SpecificRequirements"] = result.get("specific_requirements", [])
            
            # Merge new entities
            for new_ent in result.get("new_entities", []):
                if new_ent not in entity_db["fields_of_study"]:
                    entity_db["fields_of_study"].append(new_ent)
                    
            if errors:
                scholarship["ClassificationErrors"] = errors

        total_processed += 1
        processed_since_evolution += 1

        # Save progress every 10 scholarships
        if processed_since_evolution % 10 == 0:
            with open(scholarships_file, "w", encoding="utf-8") as f:
                json.dump(scholarships, f, indent=3)
            save_entity_db(entity_db)
            
        # Schema evolution check
        if processed_since_evolution >= evolution_interval:
            print(f"\n[{total_processed}] Running Schema Evolution Check...")
            analyze_and_propose_evolution(scholarships_file, schema, entity_db, api_key=api_key)
            processed_since_evolution = 0

    # Final save
    with open(scholarships_file, "w", encoding="utf-8") as f:
        json.dump(scholarships, f, indent=3)
    save_entity_db(entity_db)
    print(f"\nDone! Classified {total_processed} scholarships.")

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(description="Classify scholarships into structured attributes")
    parser.add_argument("--file", default="current_scholarships.json", help="Scholarships JSON file")
    parser.add_argument("--model", default="gemini-3.5-flash-lite", help="LLM model name")
    parser.add_argument("--api-key", default=os.getenv("GEMINI", ""), help="API key")
    parser.add_argument("--evolution-interval", type=int, default=50, help="Schema evolution interval")
    args = parser.parse_args()

    classify_batch(
        args.file,
        model=args.model,
        api_key=args.api_key,
        evolution_interval=args.evolution_interval
    )
