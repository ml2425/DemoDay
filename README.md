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

## 🧩 Configuration Snapshot

```yaml
ncbi:
  email: "your@example.com"
  api_key: "${NCBI_API_KEY}"
  rate_limit_rps: 6       # >3 rps requires API key
llm:
  canonicalizer_model: "gpt-4o-mini"
  verifier_model: "gpt-4o-mini"
  mcq_generator_model: "gpt-4o"
features:
  extract_microbe: false
  dry_run: false

---

## Data Invariants
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

---

## Reference

All technical details and design rationale are defined in plan_v2.1.txt
 — the authoritative architecture guide for DemoDay.