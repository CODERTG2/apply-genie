'''
Legacy Experiment: compare.py

Purpose:
A utility script used to compare the outputs of different classification strategy versions (v1 vs v2 vs v3).

Capabilities:
- Runs multiple classification functions against the same set of scholarships and saves the side-by-side results to `comparison_results.json` for human review.

What it lacked:
- Only useful during the active development phase of the LLM prompt engineering; not used in the final production pipeline.
'''
import json
import os
import sys
from tqdm import tqdm
from dotenv import load_dotenv

# Ensure imports work from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.classify import classify_scholarship, load_schema as load_schema_og, load_entity_db as load_entity_db_og, build_scholarship_text
from src.classify_2step import classify_scholarship_2step, load_schema as load_schema_2step, load_entity_db as load_entity_db_2step
from src.classify_3 import classify_scholarship_3step


def compare_batch(filepath="current_scholarships.json", limit=20, model="gemini-3.5-flash-lite", output_file="comparison_results.json"):
    load_dotenv()
    api_key = os.getenv("GEMINI", "")
    
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        scholarships = json.load(f)

    scholarships = scholarships[:limit]
    schema = load_schema_og()
    entity_db = load_entity_db_og()

    print(f"Comparing OG vs 2-Step vs 3-Step Classifier on first {len(scholarships)} scholarships...")
    print(f"Model: {model}\n")

    results = []

    for i, s in enumerate(tqdm(scholarships, desc="Running Comparison")):
        text = build_scholarship_text(s)
        title = s.get("Title", f"Scholarship #{i+1}")

        if not text.strip():
            continue

        # 1. Run OG Classifier
        og_res, og_err = classify_scholarship(text, schema, entity_db, model=model, api_key=api_key)

        # 2. Run 2-Step Classifier
        step2_res, step2_err = classify_scholarship_2step(text, schema, entity_db, model=model, api_key=api_key)

        # 3. Run 3-Step Classifier
        step3_res, step3_err = classify_scholarship_3step(text, schema, entity_db, model=model, api_key=api_key)

        item_comparison = {
            "index": i,
            "title": title,
            "text": text,
            "og_classifier": {
                "attributes": og_res.get("attributes", {}) if og_res else {},
                "specific_requirements": og_res.get("specific_requirements", []) if og_res else [],
                "errors": og_err
            },
            "step2_classifier": {
                "attributes": step2_res.get("attributes", {}) if step2_res else {},
                "specific_requirements": step2_res.get("specific_requirements", []) if step2_res else [],
                "errors": step2_err
            },
            "step3_classifier": {
                "attributes": step3_res.get("attributes", {}) if step3_res else {},
                "specific_requirements": step3_res.get("specific_requirements", []) if step3_res else [],
                "criteria": step3_res.get("criteria", []) if step3_res else [],
                "submission_requirements": step3_res.get("submission_requirements", []) if step3_res else [],
                "errors": step3_err
            }
        }
        results.append(item_comparison)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nComparison complete! Results saved to '{output_file}'.")
    print("\n--- Summary of First 3 Scholarships ---\n")
    for item in results[:3]:
        print(f"Title: {item['title']}")
        print("  OG Attributes:   ", list(item['og_classifier']['attributes'].keys()))
        print("  2Step Attributes:", list(item['step2_classifier']['attributes'].keys()))
        print("  3Step Attributes:", list(item['step3_classifier']['attributes'].keys()))
        print("  OG Req Count:   ", len(item['og_classifier']['specific_requirements']))
        print("  2Step Req Count:", len(item['step2_classifier']['specific_requirements']))
        print("  3Step Req Count:", len(item['step3_classifier']['specific_requirements']))
        print("  3Step Criteria Count:", len(item['step3_classifier']['criteria']))
        print("  3Step Submission Req Count:", len(item['step3_classifier']['submission_requirements']))
        print("-" * 50)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Compare OG classify vs 2-Step classify on scholarships")
    parser.add_argument("--file", default="current_scholarships.json", help="JSON file containing scholarships")
    parser.add_argument("--limit", type=int, default=20, help="Number of scholarships to compare")
    parser.add_argument("--model", default="gemini-3.5-flash-lite", help="LLM model name")
    parser.add_argument("--out", default="comparison_results.json", help="Output comparison JSON file")
    args = parser.parse_args()

    compare_batch(
        filepath=args.file,
        limit=args.limit,
        model=args.model,
        output_file=args.out
    )
