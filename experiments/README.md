# Experiments Archive

This directory preserves the historical experimentation code for the apply-genie pipeline, specifically around the LLM classification steps.

## Classifiers

*   **`classify_v1.py`** (originally `classify.py`): The first version. Single-shot classification with regex validation and retry loops if the LLM output didn't match the schema.
*   **`classify_v2_2step.py`** (originally `classify_2step.py`): A two-step process that separated the extraction of raw requirements from the normalization into the structured schema. Used Pydantic for structured output.
*   **`classify_v3_3step.py`** (originally `classify_3.py`): The current production choice (refactored into `src/steps/classifier.py`). Added a 3rd conceptual split to separate Selection Criteria and Submission Requirements from general Eligibility attributes.

## Tools

*   **`compare.py`**: A utility script used to run the different classifier versions side-by-side and benchmark their outputs.
*   **`schema_evolver.py`**: An experimental script to automatically propose updates to the `attribute_schema.json` based on new entities discovered by the LLMs.

## Pipeline Steps (Legacy)

The following scripts were early, monolithic iterations of what eventually became the modular pipeline in `src/steps/`:

*   **`careerstop.py`**: An early, slow synchronous Playwright scraper for CareerOneStop.
*   **`dates.py`**: An initial attempt at deadline date extraction that modified a massive JSON file directly.
*   **`filter.py`**: An early, slow filter that tried to verify every URL using an LLM on the fly.
*   **`rephraser.py`**: An initial attempt to rephrase requirements into Yes/No questions.
*   **`llmverifier.py`**: A helper script used by the early `filter.py` to fetch HTML and prompt an LLM to check if it was a valid scholarship page.

## Other

*   **`Questions.md` & `instructions.md`**: Initial brainstorming and instruction documents for the AI agents.
*   **`models.txt`**: A list of models tested during development.
