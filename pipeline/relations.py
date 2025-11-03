"""
Relation extraction module.
Extracts candidate triples from sentences with entities using pattern matching.
"""

import re
from typing import List, Tuple, Dict


class RelationExtractor:
    """
    Extracts candidate relation triples from sentences using deterministic patterns.
    """
    
    def candidates(self, sentence: str, entities: List[Dict]) -> List[Tuple[str, str, str]]:
        """
        Extract candidate relation triples from a sentence.
        
        Args:
            sentence: Sentence text
            entities: List of entity dicts with keys: entity_id, name, type, span_text
            
        Returns:
            List of tuples: (head_name, rel_id, tail_name)
        """
        candidates = []
        sentence_lower = sentence.lower()
        
        # Get entities by type
        drugs = [e for e in entities if e.get("type") == "DRUG"]
        disorders = [e for e in entities if e.get("type") == "DISORDER"]
        findings = [e for e in entities if e.get("type") == "FINDING"]
        investigations = [e for e in entities if e.get("type") == "INVESTIGATION"]
        microbes = [e for e in entities if e.get("type") == "MICROBE"]
        
        # Pattern 1: TREATS (DRUG/PROCEDURE → DISORDER)
        if drugs and disorders:
            treat_keywords = r'\b(?:treat|therapy|therapeutic|first-line|manages?|managing)\b'
            if re.search(treat_keywords, sentence_lower):
                for drug in drugs:
                    for disorder in disorders:
                        candidates.append((drug["name"], "TREATS", disorder["name"]))
        
        # Pattern 2: HAS_FINDING (DISORDER → FINDING)
        if disorders and findings:
            has_keywords = r'\b(?:has|with|presents?|exhibits?|shows?)\b'
            if re.search(has_keywords, sentence_lower):
                for disorder in disorders:
                    for finding in findings:
                        candidates.append((disorder["name"], "HAS_FINDING", finding["name"]))
        
        # Pattern 3: INVESTIGATED_BY (DISORDER → INVESTIGATION)
        if disorders and investigations:
            inv_keywords = r'\b(?:ct|mri|angiography|ultrasound|scan|imaging)\b'
            if re.search(inv_keywords, sentence_lower):
                for disorder in disorders:
                    for inv in investigations:
                        candidates.append((disorder["name"], "INVESTIGATED_BY", inv["name"]))
        
        # Pattern 4: CAUSES (MICROBE/DRUG/DISORDER → DISORDER/FINDING)
        cause_keywords = r'\b(?:cause|causes|caused\s+by|leading\s+to|resulting\s+in)\b'
        if re.search(cause_keywords, sentence_lower):
            # MICROBE/DRUG/DISORDER → DISORDER/FINDING
            causes = microbes + drugs + disorders
            effects = disorders + findings
            
            for cause_ent in causes:
                for effect_ent in effects:
                    if cause_ent["name"] != effect_ent["name"]:
                        candidates.append((cause_ent["name"], "CAUSES", effect_ent["name"]))
        
        return candidates

