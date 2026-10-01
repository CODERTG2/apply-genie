'''
Legacy Experiment: classify_v2_2step.py

Purpose:
Version 2 of the classification logic, introducing a 2-step methodology and Pydantic models.

Capabilities:
- Uses `create_model` from Pydantic to dynamically enforce output structure based on `attribute_schema.json`.

What it lacked:
- Did not separate out submission requirements and selection criteria.
'''
import json
import os
import enum
from tqdm import tqdm
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Dict

def load_schema():
    with open("attribute_schema.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_entity_db():
    with open("entity_db.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_entity_db(entity_db):
    with open("entity_db.json", "w", encoding="utf-8") as f:
        json.dump(entity_db, f, indent=2)

def build_pydantic_schema(schema_def):
    fields = {}
    for attr_name, attr in schema_def.items():
        if attr["type"] == "numeric":
            class NumericRange(BaseModel):
                min: Optional[float] = None
                max: Optional[float] = None
            fields[attr_name] = (Optional[NumericRange], None)
        elif attr["type"] in ("single_select", "multi_select"):
            if not attr.get("allow_new", False):
                # Dynamically create an Enum to restrict values
                EnumClass = enum.Enum(f"{attr_name}Enum", {v: v for v in attr["pre_seeded"]})
                fields[attr_name] = (Optional[List[EnumClass]], None)
            else:
                fields[attr_name] = (Optional[List[str]], None)
        elif attr["type"] in ("entity_lookup", "entity_lookup_multi"):
            fields[attr_name] = (Optional[List[str]], None)
        elif attr["type"] == "boolean":
            fields[attr_name] = (Optional[bool], None)
        elif attr["type"] == "text":
            fields[attr_name] = (Optional[str], None)
        elif attr["type"] == "numeric_entity_map":
            class EntityScore(BaseModel):
                entity_name: str
                score: float
            fields[attr_name] = (Optional[List[EntityScore]], None)

    AttributesModel = create_model('AttributesModel', **fields)

    class SpecificRequirement(BaseModel):
        type: str = Field(description="'include' or 'exclude'")
        description: str = Field(description="short human-readable description")
        category_hint: str = Field(description="short category label")
        source_text: str = Field(description="original text")

    class NewEntities(BaseModel):
        memberships: Optional[List[str]] = None
        schools: Optional[List[str]] = None
        fields_of_study: Optional[List[str]] = None
        test_types: Optional[List[str]] = None
        medical_conditions: Optional[List[str]] = None
        career_fields: Optional[List[str]] = None

    class ClassificationOutput(BaseModel):
        attributes: AttributesModel
        raw_specific_requirements: List[SpecificRequirement]
        new_entities: NewEntities

    return ClassificationOutput, AttributesModel


def build_classification_prompt(scholarship_text, schema, entity_db):
    """Build the prompt for Step 1: Raw Extraction."""
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

ATTRIBUTES:
{schema_ref}

CRITICAL RULES:
1. DECOMPOSE compound requirements into separate attributes.
   "High School Senior" -> education_type: ["High School"], year_of_study: ["High School Senior"]
2. ALWAYS output selectable fields as a JSON array (list), even if only one value applies.
3. For numeric attributes, output an object with 'min' and/or 'max' keys.
4. If a requirement doesn't fit ANY attribute, add it to 'raw_specific_requirements'.
5. DO NOT create attributes for SUBMISSION materials (e.g. essays) or SELECTION criteria.
6. Only output valid JSON matching the schema.
"""
    return prompt


def build_normalization_prompt(raw_requirements, schema, AttributesModel):
    """Build the prompt for Step 2: Normalization."""
    class NormalizedReq(BaseModel):
        type: str
        description: str
        category_hint: str
        source_text: str

    class NormalizationOutput(BaseModel):
        new_mapped_attributes: AttributesModel = Field(description="Any attributes mapped from the raw specific requirements")
        normalized_specific_requirements: List[NormalizedReq] = Field(description="The remaining specific requirements, standardized")

    prompt = f"""You are a Normalization Agent for scholarship requirements.
You will be given a list of 'raw_specific_requirements' extracted from a scholarship.
Your job is to:
1. Check if any of these specific requirements actually map to standard attributes. For example:
   - "good academic standing" -> map to `gpa` {{min: 2.0}}
   - "needs grant funding" -> map to `financial_need` ["Yes - Demonstrated"]
   - "SoHE major" -> map to `field_of_study` ["School of Human Ecology"]
   - "Requires FAFSA" -> map to `financial_need` ["Yes - FAFSA Filed"]
2. If a requirement maps to a standard attribute, output it in `new_mapped_attributes` and REMOVE it from the specific requirements list.
3. For the remaining specific requirements that DO NOT map to standard attributes, standardize their `description` and `category_hint` so they are consistent. (e.g. 'Must play the violin' -> 'Plays Violin').

RAW SPECIFIC REQUIREMENTS:
{json.dumps(raw_requirements, indent=2)}
"""
    return prompt, NormalizationOutput


def build_scholarship_text(scholarship):
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


def classify_scholarship_2step(scholarship_text, schema, entity_db, model="gemini-3.5-flash-lite", api_key=None):
    if not scholarship_text.strip():
        return None, ["No qualification text found"]

    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    
    # Generate the dynamic schema
    ClassificationOutput, AttributesModel = build_pydantic_schema(schema)

    # STEP 1: Raw Extraction
    prompt_1 = build_classification_prompt(scholarship_text, schema, entity_db)
    
    try:
        response_1 = client.models.generate_content(
            model=model,
            contents=prompt_1,
            config=types.GenerateContentConfig(
                system_instruction="You are a strict data extractor. Return JSON matching the schema perfectly.",
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=ClassificationOutput,
            )
        )
        
        # Parse Pydantic output
        res_1_json = json.loads(response_1.text)
        
        # Because we used Pydantic Enums, we might need to stringify them. 
        # Pydantic's BaseModel.model_validate_json gives an object, but json.loads just gives strings since response is string.
        # So res_1_json is just plain python dicts!
        attributes = res_1_json.get("attributes", {})
        raw_reqs = res_1_json.get("raw_specific_requirements", [])
        new_entities = res_1_json.get("new_entities", {})
        
    except Exception as e:
        return None, [f"Step 1 Failed: {str(e)}"]

    # STEP 2: Normalization
    if not raw_reqs:
        # No specific requirements to normalize
        return {
            "attributes": attributes,
            "specific_requirements": [],
            "new_entities": new_entities
        }, []

    prompt_2, NormalizationOutput = build_normalization_prompt(raw_reqs, schema, AttributesModel)
    
    try:
        response_2 = client.models.generate_content(
            model=model,
            contents=prompt_2,
            config=types.GenerateContentConfig(
                system_instruction="You are a requirement normalization agent. Return JSON matching the schema perfectly.",
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=NormalizationOutput,
            )
        )
        
        res_2_json = json.loads(response_2.text)
        mapped_attrs = res_2_json.get("new_mapped_attributes", {})
        norm_reqs = res_2_json.get("normalized_specific_requirements", [])
        
        # Merge mapped_attrs into attributes
        for k, v in mapped_attrs.items():
            if v: # if not null or empty list
                if k not in attributes or not attributes[k]:
                    attributes[k] = v
                elif isinstance(attributes[k], list) and isinstance(v, list):
                    # Combine lists without duplicates
                    attributes[k] = list(set(attributes[k] + v))
                elif isinstance(attributes[k], dict) and isinstance(v, dict):
                    # For things like numeric min/max, update
                    attributes[k].update(v)
                    
    except Exception as e:
        # If Step 2 fails, we just return Step 1's output
        return {
            "attributes": attributes,
            "specific_requirements": raw_reqs,
            "new_entities": new_entities
        }, [f"Step 2 Failed, fell back to Step 1: {str(e)}"]

    return {
        "attributes": attributes,
        "specific_requirements": norm_reqs,
        "new_entities": new_entities
    }, []

try:
    from src import db
except ImportError:
    import db


def classify_batch(model="gemini-3.5-flash-lite", api_key=None, max_run=10):
    schema = load_schema()
    entity_db = load_entity_db()
    
    scholarships = db.get_unclassified_scholarships(limit=max_run)

    if not scholarships:
        print("No unclassified scholarships found in Turso DB.")
        return

    total_processed = 0

    for scholarship in tqdm(scholarships, desc="Classifying (2-Step)"):
        text = build_scholarship_text(scholarship)
        if not text.strip():
            continue

        result, errors = classify_scholarship_2step(text, schema, entity_db, model=model, api_key=api_key)

        if result:
            attributes = result.get("attributes", {})
            specific_requirements = result.get("specific_requirements", [])
            
            # Save directly to Turso DB
            db.update_scholarship_classification(
                scholarship_id=scholarship["id"],
                attributes=attributes,
                specific_requirements=specific_requirements,
                errors=errors
            )

        total_processed += 1

    print(f"\nDone! Classified and saved {total_processed} scholarships directly to Turso DB.")

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(description="2-Step Classification")
    parser.add_argument("--model", default="gemini-3.5-flash-lite", help="LLM model name")
    parser.add_argument("--api-key", default=os.getenv("GEMINI", ""), help="API key")
    parser.add_argument("--max-run", type=int, default=10, help="Max items to process for testing")
    args = parser.parse_args()

    classify_batch(
        model=args.model,
        api_key=args.api_key,
        max_run=args.max_run
    )
