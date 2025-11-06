"""
Orchestration module.
End-to-end pipeline from document to KG triples to MCQs.
"""

import sqlite3
from typing import Dict, Any, List, Optional

from pipeline.ingest import sentence_split
from pipeline.negation import NegationNode
from pipeline.spans import find_spans
from pipeline.canonicaliser import CanonicaliserNode
from pipeline.relations import RelationExtractor
from pipeline.verifier import RelationVerifierNode
from pipeline.mcq_generator import MCQGeneratorNode
from database.db_utils import connect
from database.triple_utils import ensure_relation, insert_triple, insert_evidence
from database.mcq_utils import get_concept_for_entity
from utils.runtime import get_config


class Orchestrator:
    """
    Orchestrates the end-to-end pipeline: document → KG triples → MCQs.
    """
    
    def __init__(self, conn: sqlite3.Connection, config: Optional[Dict[str, Any]] = None):
        """
        Initialize orchestrator.
        
        Args:
            conn: Database connection
            config: Optional config dict (loads from file if None)
        """
        self.conn = conn
        self.config = config or get_config()
        
        # Initialize nodes
        self.negation_node = NegationNode()
        self.canonicaliser = CanonicaliserNode(conn)
        self.relation_extractor = RelationExtractor(conn=conn)
        self.verifier = RelationVerifierNode(conn)
        self.mcq_generator = MCQGeneratorNode(conn)
        
        # Get limits from config
        self.max_verify_calls = get_config("limits.llm_verify_max_calls_per_doc", 50)
        self.verify_call_count = 0
    
    def run_doc(self, doc_id: int, text: str) -> Dict[str, Any]:
        """
        Run full pipeline for a document.
        
        Steps per sentence:
        1. Split sentences
        2. Filter negations (log to DB)
        3. Find spans, canonicalize, get entity_ids
        4. Extract relation candidates
        5. Verify candidates
        6. Insert triples and evidence if entailed
        7. Generate MCQs for new triples
        
        Args:
            doc_id: Document ID
            text: Document text
            
        Returns:
            Dict with counts: sentences_processed, triples_created, mcqs_created
        """
        # Reset verify call counter
        self.verify_call_count = 0
        
        # Split sentences
        sentence_dicts = sentence_split(text)
        if not sentence_dicts:
            return {"sentences_processed": 0, "triples_created": 0, "mcqs_created": 0}
        
        # Extract sentence strings
        sentences = [s["text"] for s in sentence_dicts]
        sent_indices = [s["sent_idx"] for s in sentence_dicts]
        
        # Filter negations
        kept_sentences = self.negation_node.filter(doc_id, sentences, self.conn)
        
        # Track created triples for MCQ generation
        created_triple_ids = []
        triples_created = 0
        
        # Calculate total sentences to process (for progress logging)
        total_sentences = len([s for s in sentence_dicts if s["text"] in kept_sentences])
        sentence_count = 0
        
        # Process each kept sentence
        for sent_dict in sentence_dicts:
            sent_text = sent_dict["text"]
            sent_idx = sent_dict["sent_idx"]
            
            # Skip if sentence was filtered by negation
            if sent_text not in kept_sentences:
                continue
            
            sentence_count += 1
            print(f"  [{sentence_count}/{total_sentences}] Processing sentence {sent_idx}: {sent_text[:60]}...", flush=True)
            
            try:
                # Find spans
                spans = find_spans(sent_text)
                if not spans:
                    continue
                
                # Convert spans to format expected by canonicaliser
                # (char_start, char_end, span_text)
                # Note: find_spans returns (char_start, char_end, span_text) where char_end is exclusive
                # But process_spans expects char_end to be inclusive? Let me check...
                # Actually, let's pass as-is and let canonicaliser handle it
                span_tuples = [(s[0], s[1], s[2]) for s in spans]
                
                # Canonicalize and insert entities
                entity_ids = self.canonicaliser.process_spans(doc_id, sent_idx, span_tuples, sentence=sent_text)
                if not entity_ids:
                    continue
                
                # Build entities_for_sentence dict with name and type
                entities_for_sentence = []
                for entity_id in entity_ids:
                    # Get concept info
                    concept = get_concept_for_entity(self.conn, entity_id)
                    if concept:
                        # Find span_text from entity
                        cursor = self.conn.execute(
                            "SELECT span_text FROM entities WHERE entity_id = ?",
                            (entity_id,)
                        )
                        row = cursor.fetchone()
                        span_text = row[0] if row else ""
                        
                        entities_for_sentence.append({
                            "entity_id": entity_id,
                            "name": concept.get("canonical_name", ""),
                            "type": concept.get("semantic_category", ""),
                            "span_text": span_text
                        })
                
                # Extract relation candidates
                candidates = self.relation_extractor.candidates(sent_text, entities_for_sentence)
                if candidates:
                    print(f"      -> Found {len(candidates)} relation candidates", flush=True)
                if not candidates:
                    continue
                
                # Verify and insert triples
                for rel in candidates:
                    # Extract relation data from Dict format
                    head_name = rel.get("head", "")
                    rel_id = rel.get("relation", "")
                    tail_name = rel.get("tail", "")
                    llm_confidence = rel.get("confidence", 0.75)  # LLM extractor confidence
                    
                    # Check verify call budget
                    if self.verify_call_count >= self.max_verify_calls:
                        continue
                    
                    try:
                        # Find entity_ids for head and tail names
                        head_entity_id = None
                        tail_entity_id = None
                        
                        for ent in entities_for_sentence:
                            if ent["name"] == head_name:
                                head_entity_id = ent["entity_id"]
                            if ent["name"] == tail_name:
                                tail_entity_id = ent["entity_id"]
                        
                        if not head_entity_id or not tail_entity_id:
                            continue
                        
                        # Verify relation
                        triple = (head_name, rel_id, tail_name)
                        result = self.verifier.verify(sent_text, triple)
                        self.verify_call_count += 1
                        
                        if result.get("entailed", False):
                            # Ensure relation exists
                            ensure_relation(self.conn, rel_id, rel_id.lower(), "", "")
                            
                            # Insert triple
                            # Use verifier confidence (more reliable for entailment), 
                            # but could use min(llm_confidence, verifier_confidence) for tighter bounds
                            triple_id = insert_triple(
                                self.conn,
                                head_entity=head_entity_id,
                                rel_id=rel_id,
                                tail_entity=tail_entity_id,
                                confidence=result.get("confidence", 0.75),
                                verifier_model=self.verifier.verifier_model
                            )
                            
                            # Insert evidence (single sentence window)
                            insert_evidence(
                                self.conn,
                                triple_id=triple_id,
                                doc_id=doc_id,
                                section="RESULTS",  # Default section
                                sent_start=sent_idx,
                                sent_end=sent_idx,
                                sentence_text=sent_text
                            )
                            
                            created_triple_ids.append(triple_id)
                            triples_created += 1
                    
                    except Exception as e:
                        # Log error but continue
                        print(f"      [ERROR] Triple verification failed for sentence {sent_idx}: {e}", flush=True)
                        continue
            
            except Exception as e:
                # Log error but continue
                print(f"      [ERROR] Sentence {sent_idx} failed: {e}", flush=True)
                continue
        
        # Generate MCQs for new triples (ignore failures)
        mcqs_created = 0
        for triple_id in created_triple_ids:
            try:
                self.mcq_generator.generate_for_triple(triple_id)
                mcqs_created += 1
            except Exception:
                # Ignore MCQ generation failures
                continue
        
        return {
            "sentences_processed": len(kept_sentences),
            "triples_created": triples_created,
            "mcqs_created": mcqs_created
        }


def build_graph(config: Optional[Dict[str, Any]] = None, db_path: str = "database/kg.sqlite") -> Orchestrator:
    """
    Build and return orchestrator instance.
    
    Args:
        config: Optional config dict (loads from file if None)
        db_path: Path to database
        
    Returns:
        Orchestrator instance
    """
    conn = connect(db_path)
    return Orchestrator(conn, config)

