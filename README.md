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
| Phase   | Focus                                             | Output                                              | Purpose                                 |
| ------- | ------------------------------------------------- | --------------------------------------------------- | --------------------------------------- |
| ✅ 1–3   | Repo, env, DB schema, skeleton, tests             | ✅ All passing                                       | Foundation                              |
| ✅ 4a–4b | Ingestion (PDF + PubMed)                          | ✅ Working                                           | Data acquisition                        |
| ✅ 5     | Negation detection                                | ✅ Working                                           | Filter false/negated text               |
| ✅ 6     | Canonicaliser (LLM+cache)                         | ✅ Working                                           | Entity normalization                    |
| ✅ 7     | Relation extraction + verifier                    | ✅ Working                                           | Core triple generation                  |
| **8**   | Provenance & audit trail (prompts, evidence join) | Adds `prompt_id` links, evidence summarizer         | Trace LLM and document origin           |
| **9**   | MCQ generator (LLM-assisted + validation)         | Uses triples + evidence to create 5-option MCQs     | Educational output stage                |
| **10**  | Human-in-loop review UI (Gradio or Streamlit)     | Launches review dashboard with LangGraph interrupts | Enable manual curation                  |
| **11**  | LangGraph orchestration (Supervisor + Nodes)      | `graph.py` workflow                                 | End-to-end run from document → MCQ      |
| **12**  | Evaluation & reporting                            | Test coverage, DB metrics, citation completeness    | Provenance assurance and output summary |

---

## Reference

All technical details and design rationale are defined in plan_v2.1.txt
 — the authoritative architecture guide for DemoDay.