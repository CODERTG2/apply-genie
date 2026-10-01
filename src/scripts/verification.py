import json
import os
import sys
from pathlib import Path

# Add src root to sys.path
_SRC_ROOT = Path(__file__).resolve().parent.parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from openai import OpenAI
from core.config import SCHOLARSHIPS_PATH, LM_STUDIO_BASE_URL, PROJECT_ROOT

DATA_FILE = str(SCHOLARSHIPS_PATH if SCHOLARSHIPS_PATH.exists() else PROJECT_ROOT / "current_scholarships.json")
MODEL_NAME = "meta-llama-3.1-8b-instruct"
LM_STUDIO_URL = LM_STUDIO_BASE_URL


def get_mode():
    print("=" * 60)
    print("Scholarship Requirements Verification Tool")
    print("=" * 60)
    print("1. Manual verification (terminal prompts per requirement)")
    print("2. LLM verification (using local Llama via OpenAI client)")
    print("=" * 60)
    while True:
        choice = input("Select mode (1/manual or 2/llm): ").strip().lower()
        if choice in ["1", "manual", "m"]:
            return "manual"
        elif choice in ["2", "llm", "l"]:
            return "llm"
        print("Invalid option. Please enter 1 or 2.")


def save_scholarships(filepath, scholarships):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(scholarships, f, ensure_ascii=False, indent=4)


def check_requirement_llm(client, req, title):
    desc = req.get("description", "") if isinstance(req, dict) else str(req)
    cat = req.get("category_hint", "") if isinstance(req, dict) else ""
    src = req.get("source_text", "") if isinstance(req, dict) else ""
    req_type = req.get("type", "") if isinstance(req, dict) else ""

    prompt = f"""You evaluate scholarship requirements.
Task: Determine if the requirement below is an ELIGIBILITY requirement or an APPLICATION/SUBMISSION requirement.

- ELIGIBILITY requirements: Factors that determine if a person qualifies to apply (e.g. age, GPA, major, citizenship, location, military status, financial need, academic level).
- APPLICATION/SUBMISSION requirements & selection criteria: Materials or tasks needed to apply or how winners are selected (e.g. submit essay, complete profile/application form, provide recommendation letters, transcripts, portfolio, demonstrate commitment, criteria judged on style).

Output MUST be ONLY 'True' or 'False'.
- Say True if it is an ELIGIBILITY requirement (should be KEPT).
- Say False if it is an APPLICATION/SUBMISSION requirement or selection process detail (should be REMOVED).

Scholarship Title: {title}
Requirement Details:
Description: {desc}
Category Hint: {cat}
Source Text: {src}
Type: {req_type}

Is this an ELIGIBILITY requirement? Answer True or False:"""

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a scholarship eligibility requirement validator. Respond ONLY with True or False.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        ans = completion.choices[0].message.content.strip().lower()
        return "false" not in ans
    except Exception as e:
        print(f"Error communicating with LLM: {e}")
        return True


def run_verification():
    mode = get_mode()

    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} not found.")
        sys.exit(1)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        scholarships = json.load(f)

    client = None
    if mode == "llm":
        client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")
        print(f"Connected to LM Studio at {LM_STUDIO_URL} using model '{MODEL_NAME}'.\n")

    total_scholarships = len(scholarships)
    processed_count = 0
    removed_req_count = 0
    kept_req_count = 0

    print(f"Starting verification over {total_scholarships} scholarships...\n")

    for idx, scholarship in enumerate(scholarships, 1):
        title = scholarship.get("Title", "Untitled")
        reqs = scholarship.get("SpecificRequirements", [])

        if not reqs:
            continue

        processed_count += 1
        kept_reqs = []
        modified = False

        print(f"[{idx}/{total_scholarships}] {title} ({len(reqs)} requirements)")

        for req_idx, req in enumerate(reqs, 1):
            if isinstance(req, dict):
                desc = req.get("description", "")
                cat = req.get("category_hint", "")
                src = req.get("source_text", "")
                details = f"[{cat}] {desc} (Source: '{src}')" if cat else f"{desc} (Source: '{src}')"
            else:
                details = str(req)

            if mode == "manual":
                print(f"  Req #{req_idx}: {details}")
                while True:
                    ans = input("    Keep requirement? (y/n): ").strip().lower()
                    if ans in ["y", "yes"]:
                        kept_reqs.append(req)
                        kept_req_count += 1
                        break
                    elif ans in ["n", "no"]:
                        modified = True
                        removed_req_count += 1
                        print("    -> REMOVED")
                        break
                    print("    Please enter 'y' to keep or 'n' to remove.")

            elif mode == "llm":
                is_eligibility = check_requirement_llm(client, req, title)
                if is_eligibility:
                    kept_reqs.append(req)
                    kept_req_count += 1
                    print(f"  Req #{req_idx}: {details} => [KEEP]")
                else:
                    modified = True
                    removed_req_count += 1
                    print(f"  Req #{req_idx}: {details} => [REMOVE]")

        scholarship["SpecificRequirements"] = kept_reqs
        save_scholarships(DATA_FILE, scholarships)

    print("\n" + "=" * 60)
    print("Verification Completed!")
    print(f"Processed Scholarships with Requirements: {processed_count}")
    print(f"Total Requirements Kept: {kept_req_count}")
    print(f"Total Requirements Removed: {removed_req_count}")
    print(f"Saved updated dataset to {DATA_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()