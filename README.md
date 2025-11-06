# Evidence-Based MCQ Generator

A provenance-first medical MCQ generation system that validates LLM outputs against source evidence.

## Overview

The Evidence-Based MCQ Generator is designed to create medical multiple-choice questions from scientific literature (PDFs or PubMed abstracts) while maintaining full provenance and evidence traceability. The system takes **PDF uploads or PubMed search keywords** as input, extracts medical relationships using LLM-based relation extraction, and generates MCQs as output. Throughout the pipeline, we **monitor and validate evidence** to ensure that every LLM claim can be traced back to verifiable source material. While we cannot guarantee that facts are medically accurate, we confirm that **cited evidence exists in the source** and that **LLM claims reference actual source material**, providing transparency and accountability in AI-generated educational content.

## Features

- **Evidence-based MCQ generation** from medical literature
- **PubMed integration** via NCBI E-utilities API
- **PDF processing** with UUID-based citation system
- **Schema-constrained relation extraction** (currently configured for neurosurgery domain)
- **Hybrid evidence verification** (exact → fuzzy → semantic matching)
- **Human-in-the-loop review interface** with iterative refinement
- **Full provenance tracking** - every MCQ linked to source evidence

## Setup & Installation

### Prerequisites

- Python 3.12 or higher
- `uv` package manager (recommended) or `pip`

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd DemoDay
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   # OR
   pip install -r requirements.txt
   ```

3. **Initialize the database:**
   ```bash
   python scripts/init_db.py
   ```

## Configuration

### Environment Variables (.env)

Create a `.env` file in the project root with the following API keys:

```bash
# Required: OpenAI API key for LLM calls
OPENAI_API_KEY=your_openai_api_key_here

# Optional: NCBI API key for PubMed rate limits
NCBI_API_KEY=your_ncbi_api_key_here

# Optional: Email for NCBI E-utilities etiquette
NCBI_TOOL_EMAIL=your_email@example.com
```

**How to create `.env`:**
1. Copy `.env.example` to `.env` (if available), or create a new `.env` file
2. Add your API keys as shown above
3. Never commit `.env` to version control (already in `.gitignore`)

**Where to get API keys:**
- **OpenAI API Key**: Sign up at https://platform.openai.com/api-keys
- **NCBI API Key**: Register at https://www.ncbi.nlm.nih.gov/account/settings/ (optional, improves rate limits)

## Usage Guide

### Starting the Application

1. **Run the main application:**
   ```bash
   python main.py
   ```

2. **Access the UI:**
   - Open your browser to `http://localhost:7860`
   - The Gradio interface will load with two tabs: "Input" and "Review"

### Input Options

#### PDF Upload
1. Go to the **"Input"** tab
2. Select **"PDF Upload"** as source type
3. Click **"Upload PDF"** and select your medical PDF file
4. Click **"Process"** to start the pipeline
5. The system will:
   - Extract text from PDF
   - Generate UUID prefix for citation
   - Copy PDF to `samples/` folder with UUID prefix
   - Extract relations and generate MCQs

#### PubMed Search
1. Go to the **"Input"** tab
2. Select **"PubMed Search"** as source type
3. Enter search keywords (e.g., "temozolomide glioblastoma")
4. Set maximum results (1-10, default: 5)
5. Click **"Process"** to search and process abstracts
6. The system will:
   - Search PubMed using NCBI E-utilities
   - Fetch abstracts for matching PMIDs
   - Extract relations and generate MCQs

### Reviewing MCQs

1. Go to the **"Review"** tab
2. Click **"📋 List Pending MCQs"** to see all generated MCQs
3. Copy an MCQ ID from the list
4. Paste the MCQ ID into the **"MCQ ID"** field
5. Click **"Load MCQ"** to view:
   - MCQ question, choices, and explanation
   - Underlying triple (head, relation, tail)
   - Evidence snippet (2-4 sentences from source)
   - Source citation (PMID or filename)
   - Verification status and confidence score

### Modifying MCQs

#### Approve MCQ
- Click **"✓ Approve"** to mark MCQ as approved
- Approved MCQs are ready for use

#### Reject MCQ
- Enter feedback in the **"Feedback"** field (optional)
- Click **"✗ Reject"** to mark MCQ as rejected
- Rejected MCQs are removed from pending list

#### Request Improvement
- Enter specific feedback (e.g., "remove word 'pediatric' from all answers")
- Click **"🔄 Request Better Question"**
- The system will:
  - Regenerate the MCQ incorporating your feedback
  - Keep the same underlying triple (medical relationship unchanged)
  - Update the MCQ content based on your suggestions
- Reload the MCQ to see the improved version

## Understanding Confidence Scores

### What is Confidence?

The confidence score (0.0-1.0) indicates how well the evidence snippet matches the source text. It is calculated using a **hybrid verification system** that tries multiple matching methods in order of efficiency.

### Verification Methods

| Scenario | Old Confidence | New Confidence | Method |
|----------|----------------|----------------|--------|
| Exact copy | 0.20 | 1.00 | exact |
| Slight variation | 0.20 | 0.85-0.95 | fuzzy |
| Paraphrased | 0.20 | 0.75-0.90 | semantic |
| Not found | 0.20 | 0.20-0.50 | failed |

### Method Explanations

- **Exact (1.00)**: Evidence snippet found exactly in source text. Highest confidence - LLM copied text verbatim.
- **Fuzzy (0.85-0.95)**: Near-exact match with minor variations (punctuation, spacing, capitalization). Uses sliding window with SequenceMatcher algorithm.
- **Semantic (0.75-0.90)**: Paraphrased but semantically equivalent text. Uses OpenAI embeddings with cosine similarity to find meaning-equivalent passages.
- **Failed (<0.70)**: Evidence not found or very low similarity. MCQ marked as "warning" status - requires human review.

### Status Indicators

- **Verified**: Confidence ≥ 0.70 - Evidence found and validated
- **Warning**: Confidence < 0.70 - Evidence verification failed, human review recommended

## Examples

### PubMed Search Examples

#### Example 1: Hydrocephalus and Shunt Management
**Keywords:** `hydrocephalus shunt infection`
**Expected Results:**
- MCQs about shunt complications
- Relations: `SHUNT_COMPLICATION` → infection
- Evidence snippets from abstracts discussing shunt-related infections

#### Example 2: Glioblastoma Treatment
**Keywords:** `temozolomide glioblastoma multiforme high risk prognostication marker`
**Expected Results:**
- MCQs about treatment protocols
- Relations: `TREATS` (Temozolomide → Glioblastoma)
- Evidence from treatment studies

#### Example 3: Neurosurgical Procedures
**Keywords:** `craniotomy brain tumor resection`
**Expected Results:**
- MCQs about surgical techniques
- Relations: `INDICATED_FOR`, `TREATS`
- Evidence from surgical outcome studies

### PDF Upload Example

1. Upload a neurosurgery PDF (e.g., "Stupp Protocol Guidelines.pdf")
2. System generates UUID prefix (e.g., `a1b2c3d4_Stupp Protocol Guidelines.pdf`)
3. MCQs cite: `LOCAL_PDF: samples/a1b2c3d4_Stupp Protocol Guidelines.pdf`
4. Original filename preserved in citation display

## Architecture

The system uses a **LangGraph workflow** to orchestrate a 6-stage pipeline:

1. **Text Extraction**: Extract text from PDF or PubMed abstract
2. **Relation Extraction**: LLM extracts medical relationships with evidence snippets (2-4 sentences)
3. **Schema Validation**: Validate relations against domain schema (neurosurgery.yaml)
4. **Triple Storage**: Store validated triples in SQLite database
5. **MCQ Generation**: LLM generates MCQs from triples (with triple enforcement)
6. **Evidence Verification**: Hybrid verification (exact → fuzzy → semantic) validates evidence exists

### Database Schema

- **sources**: PDFs and PubMed abstracts with metadata
- **triples**: Extracted relationships with evidence snippets and location
- **mcqs**: Generated questions with verification status
- **decisions**: Audit trail of human review actions

## Project Structure

```
├── database/          # SQLite schema and utilities
│   ├── schema.sql    # Database schema definition
│   └── db_utils.py   # Database operations
├── pipeline/         # LangGraph workflow and nodes
│   ├── nodes/       # Processing steps
│   │   ├── extract_text.py
│   │   ├── extract_relations.py
│   │   ├── validate_schema.py
│   │   ├── store_triples.py
│   │   ├── generate_mcq.py
│   │   └── verify_evidence.py
│   ├── relations/   # Schema-based relation extraction
│   │   └── schema_loader.py
│   └── workflow.py  # LangGraph orchestration
├── services/        # External API clients
│   └── pubmed_client.py  # NCBI E-utilities client
├── sources/         # PDF handling
│   └── pdf_handler.py
├── ui/             # Gradio interface
│   └── gradio_app.py
├── configs/        # YAML configuration files
│   ├── config.yaml
│   └── relations/
│       ├── neurosurgery.yaml
│       └── _base.yml
└── scripts/       # Utility scripts
    └── init_db.py
```

## Technology Stack

- **Python 3.12+**: Core language
- **LangGraph**: Workflow orchestration
- **OpenAI API**: LLM calls (GPT-4o, GPT-4o-mini)
- **NCBI E-utilities**: PubMed search and abstract retrieval
- **Gradio**: Web-based UI
- **SQLite**: Local database storage
- **NumPy**: Numerical operations for cosine similarity
- **PyYAML**: Configuration file parsing

## Limitations & Disclaimers

### Medical Accuracy

⚠️ **Important**: This system validates **evidence existence**, not medical correctness. All MCQs require **human review** before use in educational or clinical settings.

### Domain Scope

- Currently configured for **neurosurgery** domain
- Relation schemas can be extended via `configs/relations/` YAML files
- Other medical domains can be added by creating new schema files

### Evidence Verification

- Verification confirms evidence **exists in source**, not that it's medically accurate
- Low confidence scores indicate evidence not found, not necessarily incorrect facts
- Human review is essential for all MCQs, especially those with "warning" status

### LLM Limitations

- LLM outputs may contain errors or hallucinations
- Triple enforcement prevents MCQ from changing the underlying relationship
- Evidence verification provides transparency but doesn't guarantee correctness

---

**For questions or issues, please refer to the project documentation or open an issue on GitHub.**
