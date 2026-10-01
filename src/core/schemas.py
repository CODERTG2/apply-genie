"""
Shared schema and entity_db loading/saving utilities.
Eliminates the duplicated load_schema() / load_entity_db() across modules.
"""

import json
from core.config import SCHEMA_PATH, ENTITY_DB_PATH


def load_schema():
    """Load the attribute schema from data/attribute_schema.json."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_entity_db():
    """Load the entity database from data/entity_db.json."""
    with open(ENTITY_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_entity_db(entity_db):
    """Save the entity database back to data/entity_db.json."""
    with open(ENTITY_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(entity_db, f, indent=2)


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
