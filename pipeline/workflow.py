"""LangGraph workflow orchestration for MCQ generation pipeline."""

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from pipeline.nodes.extract_text import extract_text_node
from pipeline.nodes.extract_relations import extract_relations_node
from pipeline.nodes.validate_schema import validate_schema_node
from pipeline.nodes.store_triples import store_triples_node
from pipeline.nodes.generate_mcq import generate_mcq_node
from pipeline.nodes.verify_evidence import verify_evidence_node


class MCQState(TypedDict):
    """State for LangGraph workflow."""
    source_type: str  # "PDF" or "PUBMED"
    pdf_path: Optional[str]  # Path to PDF (if PDF)
    keywords: Optional[str]  # Search keywords (if PubMed)
    max_results: Optional[int]  # Max PubMed results
    
    source_id: Optional[str]  # "UUID:..." or "PMID:..."
    full_text: Optional[str]  # Extracted text
    metadata: Optional[Dict[str, Any]]  # Source metadata
    
    extracted_relations: List[Dict[str, Any]]  # LLM-extracted relations
    validated_relations: List[Dict[str, Any]]  # Schema-validated relations
    stored_triples: List[int]  # triple_ids
    
    generated_mcqs: List[Dict[str, Any]]  # Generated MCQs
    verified_mcqs: List[Dict[str, Any]]  # Verified MCQs


def create_workflow() -> StateGraph:
    """Create LangGraph workflow."""
    
    workflow = StateGraph(MCQState)
    
    # Add nodes
    workflow.add_node("extract_text", extract_text_node)
    workflow.add_node("extract_relations", extract_relations_node)
    workflow.add_node("validate_schema", validate_schema_node)
    workflow.add_node("store_triples", store_triples_node)
    workflow.add_node("generate_mcq", generate_mcq_node)
    workflow.add_node("verify_evidence", verify_evidence_node)
    
    # Define flow
    workflow.set_entry_point("extract_text")
    workflow.add_edge("extract_text", "extract_relations")
    workflow.add_edge("extract_relations", "validate_schema")
    workflow.add_edge("validate_schema", "store_triples")
    workflow.add_edge("store_triples", "generate_mcq")
    workflow.add_edge("generate_mcq", "verify_evidence")
    workflow.add_edge("verify_evidence", END)
    
    return workflow.compile()


def run_pipeline(
    source_type: str,
    pdf_path: Optional[str] = None,
    keywords: Optional[str] = None,
    max_results: int = 5
) -> Dict[str, Any]:
    """
    Run the complete MCQ generation pipeline.
    
    Args:
        source_type: "PDF" or "PUBMED"
        pdf_path: Path to PDF file (if PDF)
        keywords: Search keywords (if PubMed)
        max_results: Max PubMed results (if PubMed)
        
    Returns:
        Final state dict with all results
    """
    workflow = create_workflow()
    
    initial_state: MCQState = {
        "source_type": source_type,
        "pdf_path": pdf_path,
        "keywords": keywords,
        "max_results": max_results,
        "source_id": None,
        "full_text": None,
        "metadata": None,
        "extracted_relations": [],
        "validated_relations": [],
        "stored_triples": [],
        "generated_mcqs": [],
        "verified_mcqs": []
    }
    
    # Run workflow
    final_state = workflow.invoke(initial_state)
    
    return final_state

