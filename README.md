# 🧠 DemoDay — Provenance-First Medical MCQ Generation System

**Goal:**  
Build a multi-agent AI pipeline that extracts verifiable medical knowledge from PubMed or local PDFs and generates **evidence-grounded multiple-choice questions (MCQs)** for FRACS neurosurgery training.

---

## 🚀 Overview

The DemoDay system constructs a **provenance-first Knowledge Graph (KG)** where each factual triple (`⟨head, relation, tail⟩`) is linked to **verbatim evidence** (sentence + PMID/DOI).  
MCQs are generated only from verified triples and include citations in their explanations.

### High-Level Flow

PDF / PubMed → Negation Detect → NER → Canonicaliser (LLM)
→ Relation Extract → Relation Verify (LLM) → Schema Validate
→ SQLite (KG) → MCQ Generator → Human Review (Gradio UI)


**Key guarantees:**
- Every triple has ≥1 evidence row.
- Negated mentions excluded from KG.
- Multi-sentence evidence window (≤3 sentences).
- Hard FK constraints to enforce data integrity.
- LangGraph interrupt for human review.

---

## ⚙️ Architecture Highlights

| Component | Purpose |
|------------|----------|
| **PubMed Node** | Fetch abstracts/full texts via NCBI E-utilities (6 rps with API key). |
| **Negation Node** | Filters out false mentions like “no evidence of tumour.” |
| **Canonicaliser** | Maps variable medical expressions to unified canonical concepts. |
| **Verifier** | LLM validates relation entailment (≥0.6 confidence). |
| **SQLite (WAL mode)** | Stores docs, entities, triples, evidence, and MCQs with FKs. |
| **MCQ Generator** | Creates 5-option (1 correct + 4 distractors) questions with citation. |
| **Gradio Review UI** | Allows doctor approval, edit, and feedback loop. |

---
DemoDay: Provenance-First MCQ Generation Pipeline
🎯 Objective

DemoDay is a multi-agent, provenance-first pipeline that transforms verified biomedical literature (e.g., PubMed or local PDFs) into fact-checked multiple-choice questions (MCQs) for medical specialist training.
Each generated MCQ is traceable to its evidence sentences, ensuring accuracy and reducing hallucination risk.

⚙️ End-to-End Workflow
Phase	Module	Purpose	Key Output
1–3 Environment & Schema	setup/, database/schema.sql	Configure environment, define relational schema, and scaffold test-verified code skeleton	Working repo + SQLite schema
4 Ingestion	pipeline/ingest.py	Import PDFs or PubMed abstracts, compute SHA-256 fingerprints, and register in docs table	Normalized document text
5 Negation Filter	pipeline/negation.py	Detect negated statements (“no evidence of…”) and exclude them from downstream extraction; log cues in negations	Cleaned, factual sentences
6 Canonicalisation	pipeline/canonicaliser.py, providers/llm_adapter.py	Map entity spans to canonical medical concepts (heuristic/LLM adapter) and insert into concepts + entities	Unified biomedical entities
7 Relation Extraction & Verification	pipeline/relations.py, pipeline/verifier.py	Identify candidate relations (e.g., TREATS, HAS_FINDING) and verify entailment heuristically	Verified triples → triples table
8 Provenance & Audit	database/provenance_utils.py, utils/text_window.py	Record every LLM/prompt call and attach multi-sentence evidence windows	Traceable provenance links
9 MCQ Generation	pipeline/mcq_generator.py, database/mcq_utils.py	Convert verified triples + evidence into 5-option MCQs with citations; validate format	Validated MCQs → mcqs table
10 Human Review Loop	pipeline/ui_gradio.py, scripts/review_cli.py	Review pending MCQs via Gradio dashboard or CLI; approve/reject + feedback	Curated MCQs with reviewer notes
11 LangGraph-Lite Orchestrator	pipeline/graph.py	Full document pipeline orchestration: Ingest → Negation → Canonicaliser → Relations → Verification → MCQ	Automated end-to-end run
🧠 Data Provenance Guarantee

Every triple and MCQ links back to:

Document source (docs table, pmid/doi/url)

Evidence window (evidence table → exact sentences)

Prompt trace (prompts table → hash of generation prompt)

This ensures reproducibility and auditability for every generated question.

🖥️ User Interaction

Generate MCQs

python -m pipeline.graph   # or: Orchestrator.run_doc(doc_id, text)


Review / Curate MCQs

python scripts/review_cli.py --list
python -m pipeline.ui_gradio  # Launch browser dashboard


Inspect / Export results directly from kg.sqlite.