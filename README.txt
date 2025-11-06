#  Verifiable Medical MCQ Generator (VM2Q)

> **A provenance-first AI pipeline for generating and validating medical multiple-choice questions**

VM2Q is an open-source system that transforms verified biomedical literature (e.g., PubMed abstracts or PDFs) into **fact-checked educational multiple-choice questions (MCQs)** for medical specialist training.  
Each generated MCQ is fully traceable to its **evidence source**, **knowledge-graph relations**, and **AI reasoning chain**.

---

##  Objective

The goal of VM2Q is to develop a **multi-agent, provenance-first knowledge graph system** that can autonomously generate clinically accurate and verifiable MCQs.  
This pipeline combines symbolic and LLM-driven reasoning to:
- Prevent hallucinations through **source-grounded relation extraction**  
- Maintain **end-to-end provenance** for every AI decision  
- Enable **human-in-loop validation** before educational deployment  

The system achieves these aims through a modular, 12-phase architecture and reproducible SQLite knowledge graph.

---

## ️ 1. System Architecture & File Structure

VM2Q follows a **12-phase modular pipeline**, implemented under a LangGraph-compatible orchestration layer.  
All data, including evidence and model calls, are stored in an auditable SQLite knowledge graph (`kg.sqlite`).

VM2Q/
├── configs/ # YAML config and validation schema
├── database/ # SQLite schema + utility layers
│ ├── schema.sql
│ ├── db_utils.py
│ ├── triple_utils.py
│ ├── mcq_utils.py
│ └── provenance_utils.py
├── pipeline/ # Core AI + LangGraph flow
│ ├── ingest.py # Phase 4: PDF / PubMed ingestion
│ ├── negation.py # Phase 5: Negation filtering
│ ├── canonicaliser.py # Phase 6: Concept mapping
│ ├── relations.py # Phase 7: Relation extraction
│ ├── verifier.py # Phase 7: Relation verification
│ ├── mcq_generator.py # Phase 9: MCQ generation
│ ├── ui_gradio.py # Phase 10: Human-in-loop review
│ ├── graph.py # Phase 11: Orchestrator
│ └── spans.py # Heuristic entity span finder
├── scripts/ # Utility entrypoints
│ ├── init_db.py # Create fresh kg.sqlite
│ ├── review_cli.py # CLI reviewer
│ └── report_summary.py # Phase 12: Reporting summary
├── setup/ # Environment + config setup
│ ├── setup_env.py
│ └── setup_config.py
└── tests/ # 11+ automated pytest modules

### 🧩 Architecture Overview
             ┌──────────────────────┐
             │   Ingest (PDF/PubMed)│
             └─────────┬────────────┘
                       ▼
             ┌──────────────────────┐
             │   Negation Filter     │
             └─────────┬────────────┘
                       ▼
             ┌──────────────────────┐
             │  Canonicaliser (LLM) │
             └─────────┬────────────┘
                       ▼
             ┌──────────────────────┐
             │  Relation Extractor  │
             └─────────┬────────────┘
                       ▼
             ┌──────────────────────┐
             │  Verifier (LLM/Rule) │
             └─────────┬────────────┘
                       ▼
    ┌──────────────────────────────────────────┐
    │  Triples + Evidence → Knowledge Graph     │
    └──────────────────────────────────────────┘
                       ▼
             ┌──────────────────────┐
             │  MCQ Generator       │
             └─────────┬────────────┘
                       ▼
             ┌──────────────────────┐
             │  Human Review (UI)   │
             └─────────┬────────────┘
                       ▼
             ┌──────────────────────┐
             │  Reports & Metrics   │
             └──────────────────────┘

Each phase can be executed independently or as a full pipeline via the **LangGraph-lite Orchestrator**.

**Key AI components**
- **LLMAdapter** — abstraction layer for GPT-4, Claude, or local models  
- **LangSmith tracing** — records prompt–response provenance  
- **Heuristic fallbacks** — allow offline use without network access  
- **SQLite knowledge graph** — persistent record of documents, entities, relations, MCQs, and provenance

---

##  2. How to Use VM2Q (Windows PowerShell)

### Step 1 — Setup environment
```powershell
python setup/setup_env.py
python setup/setup_config.py
python scripts/init_db.py

### Step 2 — Ingest document
# From PDF
python -c "from pipeline.ingest import Ingest; Ingest().from_pdf(['samples/Meningioma_clinical_molecular_.pdf'])" 

# From PubMed
python -c "from pipeline.ingest import Ingest; Ingest().from_pubmed(\"glioblastoma AND controlled trial\", max_results=2)"

### Step 3 — Run the orchestrator (auto-pipeline)
python -c "from pipeline.graph import Orchestrator; o = Orchestrator(\"kg.sqlite\"); print(o.run_doc(doc_id=1, text=\"Metformin is first-line therapy for type 2 diabetes.\"))"

### Step 4 — Review generated MCQs
# CLI
python scripts/review_cli.py --list
python scripts/review_cli.py --approve 1 --feedback "Good question."

# Gradio UI
python -c "from pipeline.ui_gradio import launch_review_ui; launch_review_ui(\"kg.sqlite\").launch(server_port=7860)"

### Step 5 — Generate reports
# Output includes counts of docs, entities, triples, MCQs, and provenance completeness (% of triples with evidence).
python scripts/report_summary.py --db kg.sqlite
python scripts/report_summary.py --json  # structured output

## 3. Narrative Walkthrough: From Paper to Question

VM2Q transforms medical text into verifiable educational questions through **twelve traceable phases**:

---

### Phases 1–3: Foundation

* **Defines the SQLite schema and environment**, creating a knowledge graph for documents, entities, relations, and MCQs.

### Phases 4–12: Pipeline

* **Phase 4: Ingestion**
    * Parses **PDFs or PubMed abstracts**, normalizes text, and registers each source with **unique SHA-256 identifiers**.
* **Phase 5: Negation Filtering**
    * Removes sentences with **negation** (**“no evidence of…”**) to retain only factual statements.
* **Phase 6: Canonicalisation**
    * Maps detected spans to **canonical medical concepts** (e.g., Metformin → DRUG), creating reusable entity references.
* **Phase 7: Relation Extraction & Verification**
    * Finds relational patterns such as **drug TREATS disease** or **disease HAS finding** and verifies entailment using LLM + rules.
* **Phase 8: Provenance Logging**
    * Records each model prompt and evidence sentence, ensuring every triple can be **audited back to its source**.
* **Phase 9: MCQ Generation**
    * Turns verified triples into **five-option questions** with one correct answer and full citation in the explanation.
* **Phase 10: Human-in-Loop Review**
    * Reviewers **approve or reject questions** through the Gradio dashboard or CLI, adding educational feedback.
* **Phase 11: LangGraph Orchestration**
    * Runs the entire **document-to-MCQ pipeline automatically**, linking all phases into one reproducible flow.
* **Phase 12: Evaluation & Reporting**
    * Aggregates counts and metrics—documents processed, triples created, evidence completeness, and review outcomes.

---

## Summary

Under **plan v2.1**:

* **Provenance-first knowledge graph architecture** linking every MCQ to its evidence
* Complete **12-phase pipeline** with modular nodes and offline heuristics
* **LangGraph-compatible orchestration** for reproducible AI workflows
* **Human-in-loop review interface** and automated reporting for verifiability metrics

VM2Q demonstrates that AI-assisted question generation can remain **transparent, explainable, and auditable**—a foundation for reliable medical education tools.


---

Markdown

## VM2Q Demo Run Examples

These examples show how to run the pipeline using either **local PDF files** or articles from **PubMed**.

---

### 1. Ingesting from Local PDFs

Use the `--pdf` flag to specify one or more paths to your documents. Note the use of **backticks** (`` ` ``) for line continuation in a shell environment (like PowerShell or Bash, though this syntax is shell-dependent).

python demo_run.py --source pdf --pdf `
  "samples/Meningioma_clinical_molecular_.pdf" `
  "samples/Stupp's - paradigm shift 05.pdf" `
  "samples/glioma bx vs resection 2017_cohort jokola.pdf"
  
### 2. Ingesting from PubMed
Use the --source pubmed flag along with a search query and a limit on the number of results.

python demo_run.py --source pubmed --query "glioblastoma AND randomized controlled trial" --max-results 2

### 3. Optional Flags
These flags modify the execution or output of the main run command.

### Launch Review UI
Automatically launch the Gradio review dashboard in your browser after the pipeline completes.

python demo_run.py --source pdf --pdf "samples/Meningioma_clinical_molecular_.pdf" --ui

### Output JSON Report
Generate a detailed JSON report of the run results (e.g., for integrating with custom dashboards).

python demo_run.py --source pdf --pdf "samples/Meningioma_clinical_molecular_.pdf" --json

-----------------------------------------------------------------

12 PHASES AND 2 LLM PLACEHOLDERS
Phase breakdown
Phase	Module	File	Status	LLM?
1-3	Foundation	setup/, database/schema.sql	✅ Complete	No
4	Ingestion	pipeline/ingest.py	✅ Complete	No
5	Negation Filter	pipeline/negation.py	✅ Complete (regex only)	No
6	Canonicalisation	pipeline/canonicaliser.py → providers/llm_adapter.py	⚠️ PLACEHOLDER #1	Yes
7a	Relation Extraction	pipeline/relations.py	✅ Complete (regex)	No
7b	Relation Verification	pipeline/verifier.py	⚠️ PLACEHOLDER #2	Yes
8	Provenance Logging	database/provenance_utils.py	✅ Complete	No
9	MCQ Generation	pipeline/mcq_generator.py	✅ Complete (heuristic templates)	No*
10	Human Review	pipeline/ui_gradio.py	✅ Complete	No
11	Orchestration	pipeline/graph.py	✅ Complete	No
12	Reporting	scripts/report_summary.py	✅ Complete	No
Note: MCQ Generator has an adapter parameter but it's unused (line 87: self.adapter = adapter). It uses heuristic templates, not LLM.
PLACEHOLDER #1: Phase 6 - Canonicalisation
Location:
providers/llm_adapter.py, lines 108-110
Method: LLMAdapter.canonicalize()
Current code:
# Line 108: TODO: Implement actual LLM calls (OpenAI, Anthropic, etc.)# Line 109: # For now, fall back to heuristic# Line 110: return _heuristic_canonicalize(span, sentence)
Issue:
Always returns heuristic, even when self.has_keys == True
Should call OpenAI API when API key is available
Called from:
pipeline/canonicaliser.py line 51: result = self.adapter.canonicalize(span_text, sentence)
PLACEHOLDER #2: Phase 7b - Relation Verification
Location:
pipeline/verifier.py, lines 29, 52-91
Method: RelationVerifierNode.verify()
Current code:
# Line 29: self.verifier_model = "heuristic"  # Will be LLM model name when implemented# Lines 52-91: Only heuristic logic (regex keyword matching)# No LLM call implementation
Issue:
Uses regex-based heuristic only
Comment indicates LLM should be implemented
Has self.adapter = adapter or LLMAdapter() but never calls it
Called from:
pipeline/graph.py line 163: result = self.verifier.verify(sent_text, triple)
Summary
Placeholder #1 (Canonicalisation):
File: providers/llm_adapter.py
Method: LLMAdapter.canonicalize() lines 108-110
Status: TODO comment, always falls back to heuristic
Placeholder #2 (Relation Verification):
File: pipeline/verifier.py
Method: RelationVerifierNode.verify() lines 52-91
Status: Only heuristic implementation, comment indicates LLM needed