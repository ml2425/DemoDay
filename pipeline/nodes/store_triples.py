"""Node 4: Store triples in database."""

from typing import Dict, Any, List
from database.db_utils import connect, insert_triple


def store_triples_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store validated triples in database.
    
    Expected state keys:
        - source_id: Source identifier
        - validated_relations: List of validated relation dicts
    
    Updates state with:
        - stored_triples: List of triple_ids
    """
    source_id = state.get("source_id", "")
    validated = state.get("validated_relations", [])
    
    if not source_id:
        raise ValueError("source_id is required")
    
    conn = connect()
    stored_triple_ids = []
    
    for rel in validated:
        try:
            location = rel.get("location", {})
            triple_id = insert_triple(
                conn=conn,
                source_id=source_id,
                head_entity=rel["head"],
                relation=rel["relation"],
                tail_entity=rel["tail"],
                evidence_snippet=rel["evidence_snippet"],
                relation_raw=rel.get("relation_raw"),
                location_paragraph=location.get("paragraph"),
                location_sentence_start=location.get("sentence_start"),
                location_sentence_end=location.get("sentence_end"),
                location_char_start=location.get("char_start"),
                location_char_end=location.get("char_end"),
                confidence=rel.get("confidence", 0.75)
            )
            
            if triple_id:
                stored_triple_ids.append(triple_id)
        except Exception as e:
            print(f"[ERROR] Failed to store triple: {e}")
            continue
    
    conn.close()
    
    state["stored_triples"] = stored_triple_ids
    print(f"[OK] Stored {len(stored_triple_ids)} triples")
    
    return state

