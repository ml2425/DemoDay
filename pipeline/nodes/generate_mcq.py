"""Node 5: Generate MCQs from triples with triple enforcement."""

import os
import json
from typing import Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv
from database.db_utils import connect, get_triple, insert_mcq

load_dotenv()


def build_mcq_prompt(triple: dict, evidence_snippet: str) -> str:
    """Build MCQ generation prompt with triple enforcement."""
    
    head = triple["head_entity"]
    relation = triple["relation"]
    tail = triple["tail_entity"]
    
    return f"""Generate a medical MCQ from this VERIFIED relationship.

**VERIFIED Relationship (from database - DO NOT CHANGE):**
- Head: {head}
- Relation: {relation}
- Tail: {tail}

**Evidence Snippet:**
"{evidence_snippet}"

**CRITICAL REQUIREMENTS:**
1. MCQ MUST test understanding of EXACT relationship: {head} {relation} {tail}
2. Correct answer MUST be directly supported by evidence snippet
3. You CANNOT modify or change the relationship
4. MCQ must be accurate, educational, and medically sound
5. Use v3.2 format: stem_scenario (2-4 lines) + question (1 line) + 5 choices

**Output JSON:**
{{
    "stem_scenario": "Clinical vignette (2-4 lines of context)",
    "question": "Direct question line",
    "choices": [
        "Option A (correct answer)",
        "Option B (distractor)",
        "Option C (distractor)",
        "Option D (distractor)",
        "Option E (distractor)"
    ],
    "correct_index": 0,
    "explanation": "2-4 sentence explanation linking back to triple",
    "triple_used": {{
        "head": "{head}",
        "relation": "{relation}",
        "tail": "{tail}"
    }}
}}

**IMPORTANT:** The triple_used MUST match the relationship above exactly.
"""


def generate_mcq_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate MCQs from stored triples.
    
    Expected state keys:
        - stored_triples: List of triple_ids
    
    Updates state with:
        - generated_mcqs: List of MCQ dicts with triple_id
    """
    triple_ids = state.get("stored_triples", [])
    
    if not triple_ids:
        state["generated_mcqs"] = []
        return state
    
    conn = connect()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")
    
    client = OpenAI(api_key=api_key)
    generated_mcqs = []
    
    for triple_id in triple_ids:
        try:
            # Get triple
            triple = get_triple(conn, triple_id)
            if not triple:
                continue
            
            evidence_snippet = triple["evidence_snippet"]
            
            # Build prompt
            prompt = build_mcq_prompt(triple, evidence_snippet)
            
            # Call LLM
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a medical education expert. Generate high-quality MCQs that test understanding of verified medical relationships."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            mcq_data = json.loads(content)
            
            # Verify triple matches
            triple_used = mcq_data.get("triple_used", {})
            if (triple_used.get("head") != triple["head_entity"] or
                triple_used.get("relation") != triple["relation"] or
                triple_used.get("tail") != triple["tail_entity"]):
                print(f"[WARN] Triple mismatch for triple_id {triple_id}, skipping")
                continue
            
            # Store MCQ
            mcq_id = insert_mcq(
                conn=conn,
                triple_id=triple_id,
                stem_scenario=mcq_data["stem_scenario"],
                question=mcq_data["question"],
                choices=mcq_data["choices"],
                correct_index=mcq_data["correct_index"],
                explanation=mcq_data["explanation"],
                triple_used=triple_used
            )
            
            generated_mcqs.append({
                "mcq_id": mcq_id,
                "triple_id": triple_id,
                "mcq_data": mcq_data
            })
            
        except Exception as e:
            print(f"[ERROR] MCQ generation failed for triple_id {triple_id}: {e}")
            continue
    
    conn.close()
    
    state["generated_mcqs"] = generated_mcqs
    print(f"[OK] Generated {len(generated_mcqs)} MCQs")
    
    return state

