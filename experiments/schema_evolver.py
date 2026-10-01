'''
Legacy Experiment: schema_evolver.py

Purpose:
An experimental script designed to dynamically evolve the data schema by analyzing edge cases.

Capabilities:
- Iterates over the "SpecificRequirements" catch-all bucket of processed scholarships.
- Uses Gemini to find common patterns and propose new structured attributes (e.g., discovering a recurring need for a "sports_team" attribute).

What it lacked:
- Schema changes currently require manual review and migration logic; this script was an exploratory proof-of-concept for automating that process.
'''
import json
from collections import Counter
from google import genai
from google.genai import types

def analyze_and_propose_evolution(scholarships_file="scholarships.json", schema=None, entity_db=None, api_key=None, model="gemini-3.5-flash"):
    """
    Analyzes the specific_requirements bucket from processed scholarships,
    finds common patterns, and uses the LLM to propose new schema attributes.
    """
    if schema is None:
        with open("attribute_schema.json", "r", encoding="utf-8") as f:
            schema = json.load(f)
            
    with open(scholarships_file, "r", encoding="utf-8") as f:
        scholarships = json.load(f)

    # Collect all specific requirements
    all_niche_reqs = []
    for s in scholarships:
        if "SpecificRequirements" in s:
            all_niche_reqs.extend(s["SpecificRequirements"])

    # Count by category hint
    category_counts = Counter()
    for req in all_niche_reqs:
        cat = req.get("category_hint", "Unknown")
        category_counts[cat] += 1

    # Find categories with > 5 occurrences that aren't already in the schema
    promising_categories = []
    for cat, count in category_counts.items():
        if count >= 5:
            # Get examples
            examples = [r.get("description", str(r)) for r in all_niche_reqs if r.get("category_hint") == cat][:5]
            promising_categories.append({
                "category": cat,
                "count": count,
                "examples": examples
            })

    if not promising_categories:
        print("No dominant new patterns found for schema evolution.")
        return

    print(f"Found {len(promising_categories)} potential new schema attributes.")
    
    # Initialize GenAI Client
    client = genai.Client(api_key=api_key) if api_key else genai.Client()

    for cat_data in promising_categories:
        print(f"\\nAnalyzing category: '{cat_data['category']}' ({cat_data['count']} occurrences)")
        
        prompt = f"""
We have seen this requirement {cat_data['count']} times. 
Category Hint: {cat_data['category']}
Examples:
{json.dumps(cat_data['examples'], indent=2)}

Propose a new formal attribute for our scholarship JSON schema to handle this.

CRITICAL RULES:
1. A valid attribute MUST represent a demographic trait, status, or identity that a student possesses BEFORE they apply (e.g., Employment Industry, State of Residence).
2. DO NOT propose Application Tasks (e.g., Essay formats, required materials, steps to apply).
3. DO NOT propose Subjective Criteria (e.g., Leadership, Character).
4. DO NOT propose Legal Boilerplate (e.g., Not an employee of the sponsor).
5. If the examples fall into rules 2, 3, or 4, you MUST decline to propose an attribute.

Return ONLY valid JSON.
If proposing an attribute, use this format:
{{
  "attribute_name": "snake_case_name",
  "definition": {{
    "question": "What is the question to ask the user?",
    "type": "single_select | multi_select | boolean",
    "pre_seeded": ["Option 1", "Option 2"] // Only if select type
  }}
}}

If declining based on the rules, use this format:
{{
  "skip": true,
  "reason": "Explanation of why this violates the rules."
}}
"""
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction="You are a JSON schema architect. Return ONLY valid JSON.",
                    temperature=0.1
                )
            )

            output = response.text
            
            # Clean JSON
            if output.startswith("```json"):
                output = output[7:]
            elif output.startswith("```"):
                output = output[3:]
            if output.endswith("```"):
                output = output[:-3]
                
            output_json = json.loads(output)
            
            if output_json.get("skip"):
                print(f"Skipped: {output_json.get('reason')}")
            else:
                print("\n--- NEW SCHEMA ATTRIBUTE PROPOSED ---")
                print(json.dumps(output_json, indent=2))
            
        except Exception as e:
            print(f"Failed to generate proposal for {cat_data['category']}: {e}")

if __name__ == "__main__":
    analyze_and_propose_evolution()
