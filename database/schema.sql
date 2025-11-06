-- Provenance-First MCQ Generation Database Schema
-- Based on PLAN v3.0 + v3.2 specifications

-- Sources table: stores PDFs and PubMed abstracts
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,           -- "PMID:12345678" or "UUID:abc12345"
    source_type TEXT NOT NULL,            -- "PUBMED" or "LOCAL_PDF"
    full_text TEXT NOT NULL,              -- Full abstract or PDF text
    metadata_json TEXT,                   -- JSON: title, authors, doi, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Triples table: stores extracted relationships with evidence snippets
CREATE TABLE IF NOT EXISTS triples (
    triple_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    head_entity TEXT NOT NULL,            -- Canonical head entity
    relation TEXT NOT NULL,               -- Normalized relation (from schema)
    relation_raw TEXT,                    -- Original LLM relation (for research)
    tail_entity TEXT NOT NULL,            -- Canonical tail entity
    evidence_snippet TEXT NOT NULL,        -- 2-4 sentence evidence snippet
    location_paragraph INTEGER,
    location_sentence_start INTEGER,
    location_sentence_end INTEGER,
    location_char_start INTEGER,
    location_char_end INTEGER,
    confidence REAL DEFAULT 0.75,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, head_entity, relation, tail_entity)
);

-- MCQs table: stores generated questions with v3.2 format
CREATE TABLE IF NOT EXISTS mcqs (
    mcq_id INTEGER PRIMARY KEY AUTOINCREMENT,
    triple_id INTEGER NOT NULL REFERENCES triples(triple_id),
    stem_scenario TEXT NOT NULL,          -- Clinical vignette (2-4 lines)
    question TEXT NOT NULL,                -- Direct question line
    choices_json TEXT NOT NULL,            -- JSON array of 5 options
    correct_index INTEGER NOT NULL,        -- 0-4 index of correct answer
    explanation TEXT NOT NULL,             -- 2-4 sentence explanation
    triple_used_json TEXT NOT NULL,        -- JSON: {head, relation, tail} for verification
    verification_status TEXT,              -- "verified", "warning", "failed"
    verification_confidence REAL,
    status TEXT DEFAULT 'pending',         -- pending/approved/rejected/refining
    user_feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Decisions table: audit trail for human review actions
CREATE TABLE IF NOT EXISTS decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mcq_id INTEGER NOT NULL REFERENCES mcqs(mcq_id),
    action TEXT NOT NULL,                  -- "approve", "reject", "improve"
    feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_triples_source ON triples(source_id);
CREATE INDEX IF NOT EXISTS idx_triples_relation ON triples(relation);
CREATE INDEX IF NOT EXISTS idx_mcqs_triple ON mcqs(triple_id);
CREATE INDEX IF NOT EXISTS idx_mcqs_status ON mcqs(status);
CREATE INDEX IF NOT EXISTS idx_decisions_mcq ON decisions(mcq_id);

