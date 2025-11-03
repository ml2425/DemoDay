PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- Documents
CREATE TABLE IF NOT EXISTS docs (
  doc_id      INTEGER PRIMARY KEY,
  source_kind TEXT CHECK(source_kind IN ('PUBMED_ABSTRACT','PMC_FULLTEXT','LOCAL_PDF')),
  pmid        TEXT,
  doi         TEXT,
  url         TEXT,
  sha256      TEXT UNIQUE NOT NULL,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Canonical concepts
CREATE TABLE IF NOT EXISTS concepts (
  canonical_id      INTEGER PRIMARY KEY,
  canonical_name    TEXT NOT NULL,
  semantic_category TEXT NOT NULL,
  llm_conf          REAL
);

-- Entity mentions
CREATE TABLE IF NOT EXISTS entities (
  entity_id    INTEGER PRIMARY KEY,
  canonical_id INTEGER REFERENCES concepts(canonical_id),
  doc_id       INTEGER REFERENCES docs(doc_id),
  page         INTEGER,
  sent_idx     INTEGER,
  char_start   INTEGER,
  char_end     INTEGER,
  span_text    TEXT
);

-- Relation catalogue
CREATE TABLE IF NOT EXISTS relations (
  rel_id      TEXT PRIMARY KEY,
  name        TEXT,
  domain_type TEXT,
  range_type  TEXT
);

-- Triples
CREATE TABLE IF NOT EXISTS triples (
  triple_id      INTEGER PRIMARY KEY,
  head_entity    INTEGER REFERENCES entities(entity_id),
  rel_id         TEXT    REFERENCES relations(rel_id),
  tail_entity    INTEGER REFERENCES entities(entity_id),
  confidence     REAL,
  verifier_model TEXT,
  prompt_id      INTEGER,
  created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Evidence (multi-sentence window)
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id   INTEGER PRIMARY KEY,
  triple_id     INTEGER REFERENCES triples(triple_id) ON DELETE CASCADE,
  doc_id        INTEGER REFERENCES docs(doc_id),
  section       TEXT,
  sent_start    INTEGER,
  sent_end      INTEGER,
  sentence_text TEXT NOT NULL,
  CHECK (sent_end - sent_start < 3)
);

-- Negation log
CREATE TABLE IF NOT EXISTS negations (
  doc_id           INTEGER,
  sent_idx         INTEGER,
  span_text        TEXT,
  cue_text         TEXT,
  context_sentence TEXT
);

-- Prompts
CREATE TABLE IF NOT EXISTS prompts (
  prompt_id  INTEGER PRIMARY KEY,
  role       TEXT,
  content    TEXT,
  sha256     TEXT UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MCQs
CREATE TABLE IF NOT EXISTS mcqs (
  mcq_id         INTEGER PRIMARY KEY,
  triple_id      INTEGER REFERENCES triples(triple_id) ON DELETE CASCADE,
  stem           TEXT,
  options_json   TEXT,
  explanation    TEXT,
  citations_json TEXT,
  topic          TEXT,
  difficulty     TEXT,
  status         TEXT DEFAULT 'pending',
  human_feedback TEXT
);

-- Cache
CREATE TABLE IF NOT EXISTS cache (
  cache_key   TEXT PRIMARY KEY,
  cache_value TEXT,
  cache_type  TEXT,
  hit_count   INTEGER DEFAULT 0
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_entities_doc_sent ON entities(doc_id, sent_idx);
CREATE INDEX IF NOT EXISTS idx_evidence_triple  ON evidence(triple_id);
CREATE INDEX IF NOT EXISTS idx_triples_hrt      ON triples(head_entity, rel_id, tail_entity);

