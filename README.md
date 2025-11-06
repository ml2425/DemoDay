# Provenance-First MCQ Generation System

## Quick Start

1. **Initialize Database:**
   ```bash
   python scripts/init_db.py
   ```

2. **Set Environment Variables:**
   Ensure `.env` has:
   ```
   OPENAI_API_KEY=your_key_here
   NCBI_API_KEY=your_key_here (optional, for rate limits)
   ```

3. **Run the Application:**
   ```bash
   python main.py
   ```

4. **Access UI:**
   - Open browser to `http://localhost:7860`
   - Use "Input" tab to upload PDF or search PubMed
   - Use "Review" tab to approve/reject MCQs

## Architecture

- **Database**: SQLite schema in `database/schema.sql`
- **Pipeline**: LangGraph workflow in `pipeline/workflow.py`
- **Nodes**: Individual processing steps in `pipeline/nodes/`
- **Services**: PubMed client (`services/pubmed_client.py`) and PDF handler (`sources/pdf_handler.py`)
- **UI**: Gradio interface in `ui/gradio_app.py`

## Testing PubMed Search

To test with PubMed search for:
- Keywords: "temozolomide glioblastoma multiforme high risk prognostication marker"
- Use the "PubMed Search" option in the Input tab

