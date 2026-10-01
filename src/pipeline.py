import argparse
import asyncio
import json
from openai import OpenAI
from tqdm import tqdm

from core.config import SCHOLARSHIPS_PATH, LM_STUDIO_BASE_URL, LM_STUDIO_API_KEY, CLASSIFY_CONCURRENCY
from state import PipelineState

from steps.scraper import scrape
from steps.filter import filter_scholarship
from steps.classifier import classify_batch_async
from steps.dates import extract_deadline
from steps.rephraser import rephrase_requirements
from steps.uploader import upload_scholarship, get_db_connection
from core.db import get_existing_scholarship_keys

def main():
    parser = argparse.ArgumentParser(description="ScholarshipHQ Sequential Pipeline Orchestrator")
    parser.add_argument("--start-month", type=str, required=True, help="Start month for scraping (exclusive)")
    parser.add_argument("--end-month", type=str, required=True, help="End month for scraping (exclusive)")
    parser.add_argument("--max-classify", type=int, default=0, help="Max items to process in downstream steps (0 for all)")
    parser.add_argument("--dry-run", action="store_true", help="Don't upload to DB")
    
    args = parser.parse_args()
    
    state = PipelineState()
    
    # --- 1. Scrape ---
    print(f"\n=== Step 1: Scraping ({args.start_month} to {args.end_month}) ===")
    scholarships = scrape(args.start_month, args.end_month)
    
    # Limit for downstream processing if requested
    if args.max_classify > 0:
        print(f"Limiting downstream processing to {args.max_classify} items.")
        process_list = scholarships[:args.max_classify]
    else:
        process_list = scholarships
        
    # --- Skip Already Existing Items in Turso ---
    if not args.dry_run:
        print("\nChecking Turso for existing scholarships...")
        existing_keys = get_existing_scholarship_keys()
        
        def _key(s):
            return (s.get("Title", "").strip().lower(), s.get("Organization", "").strip().lower())
            
        initial_count = len(process_list)
        process_list = [s for s in process_list if _key(s) not in existing_keys]
        skipped_count = initial_count - len(process_list)
        if skipped_count > 0:
            print(f"Skipped {skipped_count} scholarships that are already in the DB.")
            
    if not process_list:
        print("\nNo new scholarships to process. Exiting.")
        return

    local_llm_client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)
    
    # For DB upload
    db_conn = None if args.dry_run else get_db_connection()
    
    print("\n=== Step 2: Filter ===")
    filtered_list = []
    for s in tqdm(process_list, desc="Filtering"):
        if state.is_done("filter", s):
            filtered_list.append(s)
            continue
            
        if filter_scholarship(s):
            filtered_list.append(s)
            state.mark_done("filter", s)
    state.save()
    
    print(f"Kept {len(filtered_list)} out of {len(process_list)} after filtering.")
    
    print(f"\n=== Step 3: Classify (Concurrency: {CLASSIFY_CONCURRENCY}) ===")
    to_classify = [s for s in filtered_list if not state.is_done("classify", s)] # checks if scholarship isn't already classified.
    if to_classify:
        classified = asyncio.run(classify_batch_async(to_classify, concurrency=CLASSIFY_CONCURRENCY))
        state.mark_batch_done("classify", classified)
        
        # Save intermediate JSON
        with open(SCHOLARSHIPS_PATH, "w", encoding="utf-8") as f:
            json.dump(scholarships, f, indent=4, ensure_ascii=False)
    else:
        print("All items already classified.")
        
    print("\n=== Step 4: Structuring (Date & Rephrase) ===")
    for s in tqdm(filtered_list, desc="Local LLM Steps"):
        if not state.is_done("dates", s):
            extract_deadline(s, local_llm_client)
            state.mark_done("dates", s)
            
        if not state.is_done("rephrase", s):
            rephrase_requirements(s, local_llm_client)
            state.mark_done("rephrase", s)
            
        # Incremental save
        state.save()
        
    # Save intermediate JSON again
    with open(SCHOLARSHIPS_PATH, "w", encoding="utf-8") as f:
        json.dump(scholarships, f, indent=4, ensure_ascii=False)
        
    print("\n=== Step 5: Upload ===")
    if args.dry_run:
        print("Dry run enabled. Skipping upload.")
    else:
        for s in tqdm(filtered_list, desc="Uploading"):
            if not state.is_done("upload", s):
                upload_scholarship(s, db_conn)
                state.mark_done("upload", s)
        state.save()
        
    print("\nPipeline complete!")

if __name__ == "__main__":
    main()
