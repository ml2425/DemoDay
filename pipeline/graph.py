"""
LangGraph workflow module.
Orchestrates the pipeline with human review interrupts.
"""

from typing import Dict, Any, List, TypedDict


class PipelineState(TypedDict):
    """Pipeline state for LangGraph workflow."""
    doc_id: str
    sentences: List[Dict[str, Any]]
    entities: List[Dict[str, Any]]
    concepts: List[Dict[str, Any]]
    verified_triples: List[Dict[str, Any]]
    mcqs: List[Dict[str, Any]]
    review_queue: List[Dict[str, Any]]
    logs: List[Dict[str, Any]]


def create_workflow():
    """
    Create and compile LangGraph workflow with interrupt points.
    
    Returns:
        Compiled workflow application
    """
    # Stub: return None for now
    # Will be implemented with actual LangGraph StateGraph
    return None


def run_node(state: PipelineState, node_name: str) -> PipelineState:
    """
    Run a single pipeline node.
    
    Args:
        state: Current pipeline state
        node_name: Name of the node to run
        
    Returns:
        Updated pipeline state
    """
    # Stub: return state unchanged
    return state

