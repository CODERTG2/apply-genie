"""
Step 3: Classify scholarships into structured attributes using Gemini.

Refactored from src/classify_3.py (the 3-step classification).
Wraps the core logic in an async batch processor for concurrent execution.
"""

import json
import enum
import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field, create_model
from google import genai
from google.genai import types

from core.config import GEMINI_API_KEY, GEMINI_CLASSIFY_MODEL
from core.schemas import load_schema, load_entity_db


# ── Shared Models ────────────────────────────────────────────────

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
        elif attr["type"] == "entity_lookup_multi_with_status":
            statuses = attr.get("statuses", [])
            class EntityWithStatus(BaseModel):
                organization: str = Field(description="The proper noun name of the organization")
                status: str = Field(description=f"One of: {', '.join(statuses)}")
            fields[attr_name] = (Optional[List[EntityWithStatus]], None)
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

    class SubmissionRequirement(BaseModel):
        item: str = Field(description="e.g., 'Essay', 'Transcript', 'Resume'")
        details: str = Field(description="e.g., '500 to 1,000-words, typed and single-spaced'")
        source_text: str = Field(description="original text")

    class SelectionCriterion(BaseModel):
        description: str = Field(description="e.g., 'Judged on content, style, and creativity'")
        source_text: str = Field(description="original text")

    class ClassificationOutput(BaseModel):
        attributes: AttributesModel
        raw_specific_requirements: List[SpecificRequirement]
        criteria: Optional[List[SelectionCriterion]] = Field(default=None, description="Criteria on how the scholarship decides who wins. Omit if not specified.")
        submission_requirements: Optional[List[SubmissionRequirement]] = Field(default=None, description="What documents/materials the applicant must submit. Omit if not specified.")
        new_entities: NewEntities

    return ClassificationOutput, AttributesModel


# ── Prompt Builders ──────────────────────────────────────────────

def build_classification_prompt(scholarship_text, schema, entity_db):
    """Build the prompt for Step 1: Raw Extraction."""
    schema_ref_lines = []
    for attr_name, attr in sorted(schema.items(), key=lambda x: x[1]["order"]):
        if attr["type"] in ("single_select", "multi_select"):
            values = ", ".join(attr["pre_seeded"])
            if attr.get("allow_new", False):
                schema_ref_lines.append(f'  {attr_name} (pick exact match from list if applicable, else add new): [{values}, ...]')
            else:
                schema_ref_lines.append(f'  {attr_name} ({attr["type"]}): [{values}]')
        elif attr["type"] in ("entity_lookup", "entity_lookup_multi"):
            db_key = attr.get("db_key", "")
            examples = entity_db.get(db_key, [])[:15]
            schema_ref_lines.append(f'  {attr_name} (pick from known or add new): [{", ".join(examples)}, ...]')
        elif attr["type"] == "entity_lookup_multi_with_status":
            db_key = attr.get("db_key", "")
            examples = entity_db.get(db_key, [])[:15]
            schema_ref_lines.append(f'  {attr_name} (pick organization from known or add new, plus status): known: [{", ".join(examples)}, ...]')
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
1. DECOMPOSE compound requirements into separate attributes or categories. For example, if a single sentence contains both a submission requirement and a selection criteria, split them up and place them in `submission_requirements` and `criteria` respectively.
2. ALWAYS output selectable fields as a JSON array (list), even if only one value applies.
3. For numeric attributes, output an object with 'min' and/or 'max' keys.
4. If an ELIGIBILITY requirement doesn't fit ANY attribute, add it to 'raw_specific_requirements'.
5. Extracted Selection CRITERIA (how the scholarship decides who wins) must go into the 'criteria' array. Do not put them in attributes or specific_requirements.
6. Extracted SUBMISSION requirements (essays, transcripts, letters of recommendation, portfolios, completing an application profile) must go into the 'submission_requirements' array. CRITICAL: If the text says the applicant *must* submit or present specific material (e.g., 'must submit at least 50% content on Canada'), this is a `submission_requirements`. `criteria` should ONLY be used for how judges evaluate or grade the applicant.
7. DO NOT rely purely on text headers like "Criteria:". A sentence under a "Criteria" header might actually be a submission requirement or an eligibility attribute. Read the actual meaning of the text.
8. When an attribute allows new values, always prefer the exact pre-seeded values over adding a synonym (e.g. prefer "US Citizen" over "U.S. Citizen").
9. Be precise with degrees and acronyms (e.g. Phar.D. is Pharmacy, NOT "Professional (JD)"). If uncertain, use a broader category.
10. Populate 'new_entities' if you encounter schools, memberships, or fields of study not in the known examples. When creating new entities, extract ONLY the proper noun name of the organization or field. Do not include conditions like 'active member' or sentence fragments.
11. Only output valid JSON matching the schema.
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
   - "must have a 3.5 GPA or higher" -> map to `gpa` {{min: 3.5}}
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
    if "To Apply" in scholarship:
        parts.append(f"Apply: {scholarship['To Apply']}")
    return "\n".join(parts)


# ── Core Classification Logic (Async) ───────────────────────────

async def classify_scholarship_3step_async(client_async, scholarship_text, schema, entity_db, ClassificationOutput, AttributesModel):
    if not scholarship_text.strip():
        return None, ["No qualification text found"]

    # STEP 1: Raw Extraction
    prompt_1 = build_classification_prompt(scholarship_text, schema, entity_db)
    
    try:
        response_1 = await client_async.aio.models.generate_content(
            model=GEMINI_CLASSIFY_MODEL,
            contents=prompt_1,
            config=types.GenerateContentConfig(
                system_instruction="You are a strict data extractor. Return JSON matching the schema perfectly.",
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=ClassificationOutput,
            )
        )
        
        res_1_json = json.loads(response_1.text)
        
        attributes = res_1_json.get("attributes", {})
        raw_reqs = res_1_json.get("raw_specific_requirements", [])
        criteria = res_1_json.get("criteria", []) or []
        submission_requirements = res_1_json.get("submission_requirements", []) or []
        new_entities = res_1_json.get("new_entities", {})
        
    except Exception as e:
        return None, [f"Step 1 Failed: {str(e)}"]

    # STEP 2: Normalization
    if not raw_reqs:
        return {
            "attributes": attributes,
            "specific_requirements": [],
            "criteria": criteria,
            "submission_requirements": submission_requirements,
            "new_entities": new_entities
        }, []

    prompt_2, NormalizationOutput = build_normalization_prompt(raw_reqs, schema, AttributesModel)
    
    try:
        response_2 = await client_async.aio.models.generate_content(
            model=GEMINI_CLASSIFY_MODEL,
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
            if v is not None and v != []:
                if k not in attributes or attributes[k] is None or attributes[k] == []:
                    attributes[k] = v
                elif isinstance(attributes[k], list) and isinstance(v, list):
                    attributes[k] = list(set(attributes[k] + v))
                elif isinstance(attributes[k], dict) and isinstance(v, dict):
                    attributes[k].update(v)
                    
    except Exception as e:
        return {
            "attributes": attributes,
            "specific_requirements": raw_reqs,
            "criteria": criteria,
            "submission_requirements": submission_requirements,
            "new_entities": new_entities
        }, [f"Step 2 Failed, fell back to Step 1: {str(e)}"]

    return {
        "attributes": attributes,
        "specific_requirements": norm_reqs,
        "criteria": criteria,
        "submission_requirements": submission_requirements,
        "new_entities": new_entities
    }, []


# ── Concurrent Runner ───────────────────────────────────────────

async def _classify_worker(sem, client_async, scholarship, schema, entity_db, ClassificationOutput, AttributesModel):
    """Worker function to process a single scholarship with concurrency limits."""
    async with sem:
        text = build_scholarship_text(scholarship)
        if not text.strip():
            return scholarship, ["No text to classify"]
            
        result, errors = await classify_scholarship_3step_async(
            client_async, text, schema, entity_db, ClassificationOutput, AttributesModel
        )
        
        return scholarship, result, errors


async def classify_batch_async(scholarships: list, concurrency: int = 5) -> list:
    """Classify a batch of scholarships concurrently.
    Updates the scholarship dicts in-place and returns the list.
    """
    if not scholarships:
        return []

    schema = load_schema()
    entity_db = load_entity_db()
    
    # We use the async client for concurrent requests
    client_async = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version':'v1alpha'}) # Async requires v1alpha in some sdk versions, or standard genai
    
    # Pydantic schema builder
    ClassificationOutput, AttributesModel = build_pydantic_schema(schema)
    
    sem = asyncio.Semaphore(concurrency)
    tasks = []
    
    for scholarship in scholarships:
        tasks.append(_classify_worker(sem, client_async, scholarship, schema, entity_db, ClassificationOutput, AttributesModel))
        
    print(f"Classifying {len(scholarships)} items (concurrency={concurrency})...")
    
    # Use tqdm if available for progress
    try:
        from tqdm.asyncio import tqdm_asyncio
        results = await tqdm_asyncio.gather(*tasks)
    except ImportError:
        results = await asyncio.gather(*tasks)
        
    # Apply results
    for scholarship, result, errors in results:
        if result:
            scholarship["Attributes"] = result.get("attributes", {})
            scholarship["SpecificRequirements"] = result.get("specific_requirements", [])
            scholarship["Criteria_Extracted"] = result.get("criteria", [])
            scholarship["SubmissionRequirements"] = result.get("submission_requirements", [])
            scholarship["NewEntities"] = result.get("new_entities", {})
            if errors:
                scholarship["Errors"] = errors
                
    return scholarships
