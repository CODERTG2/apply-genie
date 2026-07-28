# Apply Genie Backend
A data extraction and classification backend that scrapes scholarships and uses LLMs to categorize their eligibility requirements.

![Apply Genie Architecture / Demo Placeholder](https://via.placeholder.com/800x400?text=Apply+Genie+Hero+Image+Here)
*(Note: Replace the placeholder image above with a real screenshot, GIF, or architecture diagram of the backend in action!)*

**[🔗 View the Frontend Repository](https://github.com/tanmaygarg/apply-genie-website)**

## Quick Start

```bash
# Set up dependencies with uv
uv sync

# Install Playwright browsers (only needed once)
uv run playwright install webkit

# Run the scholarship scraper
uv run src/careerstop.py
```

## Features
* **Automated Scholarship Scraping**: Uses Playwright to navigate and extract scholarship data from CareerOneStop.
* **LLM-Powered Classification**: Leverages Google GenAI to parse raw scholarship text into structured, actionable JSON attributes.
* **Dynamic Schema Evolution**: Automatically tracks and updates known entities (schools, majors, organizations) in a local database without manual intervention.
* **Smart Filtering & Deduplication**: Avoids duplicate entries and ensures only relevant time-range scholarships are processed.

## How to run it locally

### Requirements
* Python 3.14 or higher
* [uv](https://github.com/astral-sh/uv) (for dependency management)

### Environment Variables
Create a `.env` file in the root directory and add your Google API key:
```env
GEMINI_API_KEY=your_api_key_here
```

### Execution Steps
1. **Install dependencies:**
   ```bash
   uv sync
   uv run playwright install webkit
   ```
2. **Scrape Scholarships:**
   ```bash
   uv run src/careerstop.py
   ```
3. **Classify Extracted Data:**
   ```bash
   uv run src/classify.py
   ```

## How it works
The backend is split into two primary phases: extraction and classification.
* **Extraction (`careerstop.py`)**: Uses Playwright in headless WebKit mode to scrape dynamic pages. We chose Playwright over simple requests because the source portal heavily relies on client-side rendering and pagination.
* **Classification (`classify.py`)**: Raw text is sent to an LLM with a strictly defined JSON schema (`attribute_schema.json`). The LLM acts as a reasoning engine to decompose compound requirements (e.g., "Junior or Senior with 3.0 GPA") into structured arrays. We maintain a local `entity_db.json` which the LLM uses to map free-form text to known entities, significantly improving the accuracy of downstream filtering on the frontend.

## Credits
* **[uv](https://github.com/astral-sh/uv)** - For blazingly fast Python package management.
* **[Playwright](https://playwright.dev/)** - For reliable browser automation.
* **[Google GenAI](https://ai.google.dev/)** - For the underlying classification engine.
* Built to power the frontend at **apply-genie-website**.