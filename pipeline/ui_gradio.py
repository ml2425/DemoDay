"""
Gradio UI module for human review.
Provides interface for doctor approval/editing of MCQs.
"""

from typing import Dict, Any, List, Optional

try:
    import gradio as gr
except ImportError:
    gr = None  # Allow module to be imported without gradio installed


def create_review_interface(db_path: str = "kg.sqlite"):
    """
    Create Gradio interface for MCQ review.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        Gradio Blocks interface (or None if gradio not available)
    """
    if gr is None:
        return None
    
    # Stub: return minimal Gradio interface
    with gr.Blocks() as interface:
        gr.Markdown("# MCQ Review Interface")
        # Placeholder for review UI components
        pass
    
    return interface


def load_pending_mcqs(db_path: str) -> List[Dict[str, Any]]:
    """
    Load pending MCQs from database for review.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        List of MCQ dictionaries with status='pending'
    """
    # Stub: return empty list
    return []

