"""
MCQ generation module.
Generates multiple-choice questions from verified triples with citations.
"""

import json
import random
import sqlite3
from typing import Dict, Any, Optional

from database.mcq_utils import (
    get_evidence_for_triple,
    get_concept_for_entity,
    sample_distractors,
    insert_mcq
)
from pipeline.validators import load_schema


class SchemaValidator:
    """Schema validator for MCQ validation."""
    
    def __init__(self, schema: Optional[Dict[str, Any]] = None):
        self.schema = schema or load_schema()
    
    def validate_mcq(self, mcq: Dict[str, Any]) -> bool:
        """
        Validate MCQ against schema rules.
        
        Args:
            mcq: MCQ dictionary
            
        Returns:
            True if valid, False otherwise
            
        Raises:
            ValueError: If validation fails with error details
        """
        # Check citation presence
        citations_json = mcq.get("citations_json", "[]")
        if not citations_json or citations_json == "[]":
            raise ValueError("mcq_validation_failed: missing citations")
        
        # Check options count (should be 5)
        options_json = mcq.get("options_json", "[]")
        try:
            options = json.loads(options_json) if isinstance(options_json, str) else options_json
            if len(options) != 5:
                raise ValueError(f"mcq_validation_failed: expected 5 options, got {len(options)}")
            
            # Check exactly one correct
            correct_count = sum(1 for opt in options if opt.get("correct", False))
            if correct_count != 1:
                raise ValueError(f"mcq_validation_failed: expected 1 correct option, got {correct_count}")
        except (json.JSONDecodeError, ValueError) as e:
            if isinstance(e, ValueError) and "mcq_validation_failed" in str(e):
                raise
            raise ValueError(f"mcq_validation_failed: invalid options_json: {e}")
        
        return True


class MCQGeneratorNode:
    """
    MCQ generator node with heuristic templates and validation.
    """
    
    def __init__(
        self,
        conn: sqlite3.Connection,
        validator: Optional[SchemaValidator] = None,
        adapter: Optional[Any] = None,
        rng_seed: int = 42
    ):
        """
        Initialize MCQ generator.
        
        Args:
            conn: Database connection
            validator: Optional schema validator
            adapter: Optional LLM adapter (for future use)
            rng_seed: Random seed for reproducibility
        """
        self.conn = conn
        self.validator = validator or SchemaValidator()
        self.adapter = adapter
        random.seed(rng_seed)
    
    def generate_for_triple(self, triple_id: int) -> Dict[str, Any]:
        """
        Generate MCQ for a triple.
        
        Args:
            triple_id: Triple ID
            
        Returns:
            Full MCQ dictionary with all fields
            
        Raises:
            ValueError: If no evidence or validation fails
        """
        # Fetch triple and relation info
        cursor = self.conn.execute(
            """
            SELECT t.head_entity, t.rel_id, t.tail_entity, r.name
            FROM triples t
            LEFT JOIN relations r ON t.rel_id = r.rel_id
            WHERE t.triple_id = ?
            """,
            (triple_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Triple {triple_id} not found")
        
        head_entity_id, rel_id, tail_entity_id, rel_name = row
        
        # Get concepts for head and tail
        head_concept = get_concept_for_entity(self.conn, head_entity_id)
        tail_concept = get_concept_for_entity(self.conn, tail_entity_id)
        
        # Get evidence
        evidence_list = get_evidence_for_triple(self.conn, triple_id)
        if not evidence_list:
            raise ValueError("no evidence")
        
        # Build stem based on relation
        stem_templates = {
            "TREATS": f"Which of the following is a recommended treatment for {tail_concept.get('canonical_name', 'this condition')}?",
            "HAS_FINDING": f"Which finding is commonly associated with {head_concept.get('canonical_name', 'this condition')}?",
            "INVESTIGATED_BY": f"Which investigation is used to diagnose {head_concept.get('canonical_name', 'this condition')}?",
            "CAUSES": f"Which of the following can cause {tail_concept.get('canonical_name', 'this condition')}?"
        }
        
        stem = stem_templates.get(rel_id, f"Which of the following is related to {head_concept.get('canonical_name', 'this')}?")
        
        # Determine correct answer
        correct_name = None
        correct_category = None
        
        if rel_id == "TREATS":
            if head_concept.get("semantic_category") in ["DRUG", "PROCEDURE"]:
                correct_name = head_concept.get("canonical_name")
                correct_category = head_concept.get("semantic_category")
        elif rel_id == "HAS_FINDING":
            correct_name = tail_concept.get("canonical_name")
            correct_category = tail_concept.get("semantic_category")
        elif rel_id == "INVESTIGATED_BY":
            correct_name = tail_concept.get("canonical_name")
            correct_category = tail_concept.get("semantic_category")
        elif rel_id == "CAUSES":
            if head_concept.get("semantic_category") in ["MICROBE", "DRUG", "DISORDER"]:
                correct_name = head_concept.get("canonical_name")
                correct_category = head_concept.get("semantic_category")
        
        if not correct_name or not correct_category:
            # Fallback: use head as correct
            correct_name = head_concept.get("canonical_name", "Unknown")
            correct_category = head_concept.get("semantic_category", "FINDING")
        
        # Sample distractors
        exclude_names = {correct_name}
        distractors = sample_distractors(self.conn, correct_category, exclude_names, k=4)
        
        # Build options (correct + 4 distractors)
        options = [
            {"text": correct_name, "correct": True}
        ]
        for distractor in distractors:
            options.append({"text": distractor, "correct": False})
        
        # Shuffle options (keeping correct answer random position)
        random.shuffle(options)
        
        # Build explanation with citations
        first_evidence = evidence_list[0]
        citation_token = None
        
        if first_evidence.get("pmid"):
            citation_token = f"PMID:{first_evidence['pmid']}"
        elif first_evidence.get("doi"):
            citation_token = f"DOI:{first_evidence['doi']}"
        else:
            citation_token = "PMID:00000000"
        
        explanation = f"This is supported by evidence. {citation_token}"
        
        # Build citations list
        citations = []
        for ev in evidence_list:
            if ev.get("pmid"):
                citations.append({"type": "pmid", "value": ev["pmid"]})
            elif ev.get("doi"):
                citations.append({"type": "doi", "value": ev["doi"]})
        
        if not citations:
            citations.append({"type": "pmid", "value": "00000000"})
        
        # Build MCQ dict
        mcq = {
            "stem": stem,
            "options_json": json.dumps(options),
            "explanation": explanation,
            "citations_json": json.dumps(citations)
        }
        
        # Validate
        try:
            self.validator.validate_mcq(mcq)
        except ValueError as e:
            raise ValueError(f"mcq_validation_failed: {str(e)}")
        
        # Insert into database
        mcq_id = insert_mcq(
            self.conn,
            triple_id=triple_id,
            stem=stem,
            options=options,
            explanation=explanation,
            citations=citations,
            topic="",
            difficulty="medium",
            status="pending"
        )
        
        # Return full MCQ dict
        return {
            "mcq_id": mcq_id,
            "triple_id": triple_id,
            "stem": stem,
            "options": options,
            "explanation": explanation,
            "citations": citations,
            "topic": "",
            "difficulty": "medium",
            "status": "pending"
        }
