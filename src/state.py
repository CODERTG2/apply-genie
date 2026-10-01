"""
State management for crash recovery.
Tracks which scholarships have been fully processed for each pipeline step.
"""

import json
from core.config import PIPELINE_STATE_PATH

class PipelineState:
    def __init__(self):
        self.state = {
            "processed_ids": {
                "scrape": [],
                "filter": [],
                "classify": [],
                "dates": [],
                "rephrase": [],
                "upload": []
            }
        }
        self.load()

    # load the JSON
    def load(self):
        if PIPELINE_STATE_PATH.exists():
            try:
                with open(PIPELINE_STATE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge loaded state with defaults
                    for step in self.state["processed_ids"].keys():
                        if step in data.get("processed_ids", {}):
                            self.state["processed_ids"][step] = data["processed_ids"][step]
            except json.JSONDecodeError:
                pass

    # writes to JSON file 
    def save(self):
        with open(PIPELINE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    # returns a unique key for a scholarship based on a string concatenation of the title and organization of the scholarship
    def _get_key(self, scholarship: dict) -> str:
        title = scholarship.get("Title", "")
        org = scholarship.get("Organization", "")
        return f"{title}::{org}"

    # checks if scholarship has been processed in the given step
    def is_done(self, step: str, scholarship: dict) -> bool:
        key = self._get_key(scholarship)
        return key in self.state["processed_ids"].get(step, [])

    # takes singular scholarship info but DOESN'T save to JSON.
    def mark_done(self, step: str, scholarship: dict):
        key = self._get_key(scholarship)
        if step in self.state["processed_ids"]:
            if key not in self.state["processed_ids"][step]:
                self.state["processed_ids"][step].append(key)

    # saves all the info from the step and writes it onto the JSON
    def mark_batch_done(self, step: str, scholarships: list):
        for s in scholarships:
            self.mark_done(step, s)
        self.save()
