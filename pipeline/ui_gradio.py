"""
Gradio UI module for human review.
Provides interface for doctor approval/editing of MCQs.
"""

from typing import Dict, Any, List, Optional

try:
    import gradio as gr
except ImportError:
    gr = None  # Allow module to be imported without gradio installed

from database.db_utils import connect
from database.mcq_utils import list_mcqs, get_mcq, update_mcq_status


def launch_review_ui(db_path: str = "kg.sqlite", page_size: int = 10):
    """
    Launch Gradio review UI for pending MCQs.
    
    Args:
        db_path: Path to SQLite database
        page_size: Number of MCQs to load per page
    """
    if gr is None:
        raise ImportError("Gradio is not installed. Install with: pip install gradio")
    
    def load_mcqs():
        """Load pending MCQs from database."""
        conn = connect(db_path)
        try:
            return list_mcqs(conn, status="pending", limit=page_size)
        finally:
            conn.close()
    
    def format_mcq_display(mcq: Optional[Dict]) -> tuple:
        """Format MCQ for display."""
        if not mcq:
            return (
                "No MCQs available.",
                "",
                "",
                "",
                None
            )
        
        # Format stem
        stem_text = mcq.get("stem", "")
        
        # Format options (mark correct answer)
        options = mcq.get("options", [])
        options_text = "\n".join([
            f"{'✓' if opt.get('correct') else ' '} {i+1}. {opt.get('text', '')}"
            for i, opt in enumerate(options)
        ])
        
        # Format explanation
        explanation = mcq.get("explanation", "")
        
        # Format citations
        citations = mcq.get("citations", [])
        citations_text = "\n".join([
            f"{cit.get('type', '').upper()}: {cit.get('value', '')}"
            for cit in citations
        ])
        
        return (
            stem_text,
            options_text,
            explanation,
            citations_text,
            mcq.get("mcq_id")
        )
    
    def get_next_mcq(current_idx: int, mcqs_list: List[Dict]) -> tuple:
        """Get next MCQ in list."""
        if not mcqs_list:
            return format_mcq_display(None) + (0,)
        
        next_idx = (current_idx + 1) % len(mcqs_list)
        return format_mcq_display(mcqs_list[next_idx]) + (next_idx,)
    
    def refresh_mcqs() -> tuple:
        """Refresh MCQ list from database."""
        mcqs = load_mcqs()
        if not mcqs:
            formatted = format_mcq_display(None)
            return formatted[0], formatted[1], formatted[2], formatted[3], formatted[4], 0, []
        
        formatted = format_mcq_display(mcqs[0])
        return formatted[0], formatted[1], formatted[2], formatted[3], formatted[4], 0, mcqs
    
    def approve_mcq(mcq_id: Optional[int], feedback: str) -> tuple:
        """Approve current MCQ."""
        if not mcq_id:
            return "No MCQ selected.", None
        
        conn = connect(db_path)
        try:
            update_mcq_status(conn, mcq_id, "approved", feedback)
            return f"MCQ {mcq_id} approved.", None
        finally:
            conn.close()
    
    def reject_mcq(mcq_id: Optional[int], feedback: str) -> tuple:
        """Reject current MCQ."""
        if not mcq_id:
            return "No MCQ selected.", None
        
        conn = connect(db_path)
        try:
            update_mcq_status(conn, mcq_id, "rejected", feedback)
            return f"MCQ {mcq_id} rejected.", None
        finally:
            conn.close()
    
    # Build Gradio interface
    with gr.Blocks(title="MCQ Review Interface") as interface:
        gr.Markdown("# MCQ Review Interface")
        
        with gr.Row():
            with gr.Column():
                stem = gr.Textbox(label="Question Stem", lines=2, interactive=False)
                options = gr.Textbox(label="Options", lines=5, interactive=False)
                explanation = gr.Textbox(label="Explanation", lines=3, interactive=False)
                citations = gr.Textbox(label="Citations", lines=2, interactive=False)
                
                # Hidden state
                current_mcq_id = gr.State(value=None)
                current_idx = gr.State(value=0)
                mcqs_list = gr.State(value=[])
            
            with gr.Column():
                feedback = gr.Textbox(label="Review Feedback", lines=3, placeholder="Enter feedback...")
                status_msg = gr.Textbox(label="Status", interactive=False)
                
                with gr.Row():
                    approve_btn = gr.Button("Approve", variant="primary")
                    reject_btn = gr.Button("Reject", variant="stop")
                
                with gr.Row():
                    next_btn = gr.Button("Next")
                    refresh_btn = gr.Button("Refresh")
        
        # Button handlers
        def on_approve(mcq_id, feedback_text, idx, mcqs):
            msg, new_mcq_id = approve_mcq(mcq_id, feedback_text)
            # Advance to next
            if mcqs:
                next_idx = (idx + 1) % len(mcqs)
                formatted = format_mcq_display(mcqs[next_idx] if mcqs else None)
                return msg, formatted[0], formatted[1], formatted[2], formatted[3], formatted[4], next_idx, mcqs
            return msg, "", "", "", "", None, idx, mcqs
        
        def on_reject(mcq_id, feedback_text, idx, mcqs):
            msg, new_mcq_id = reject_mcq(mcq_id, feedback_text)
            # Advance to next
            if mcqs:
                next_idx = (idx + 1) % len(mcqs)
                formatted = format_mcq_display(mcqs[next_idx] if mcqs else None)
                return msg, formatted[0], formatted[1], formatted[2], formatted[3], formatted[4], next_idx, mcqs
            return msg, "", "", "", "", None, idx, mcqs
        
        def on_next(idx, mcqs):
            formatted = get_next_mcq(idx, mcqs)
            return formatted[0], formatted[1], formatted[2], formatted[3], formatted[4], formatted[5], mcqs
        
        def on_refresh():
            result = refresh_mcqs()
            return result[0], result[1], result[2], result[3], result[4], result[5], result[6], "Refreshed."
        
        approve_btn.click(
            on_approve,
            inputs=[current_mcq_id, feedback, current_idx, mcqs_list],
            outputs=[status_msg, stem, options, explanation, citations, current_mcq_id, current_idx, mcqs_list]
        )
        
        reject_btn.click(
            on_reject,
            inputs=[current_mcq_id, feedback, current_idx, mcqs_list],
            outputs=[status_msg, stem, options, explanation, citations, current_mcq_id, current_idx, mcqs_list]
        )
        
        next_btn.click(
            on_next,
            inputs=[current_idx, mcqs_list],
            outputs=[stem, options, explanation, citations, current_mcq_id, current_idx, mcqs_list]
        )
        
        refresh_btn.click(
            on_refresh,
            outputs=[stem, options, explanation, citations, current_mcq_id, current_idx, mcqs_list, status_msg]
        )
        
        # Load initial MCQs
        interface.load(
            on_refresh,
            outputs=[stem, options, explanation, citations, current_mcq_id, current_idx, mcqs_list, status_msg]
        )
    
    return interface


def load_pending_mcqs(db_path: str) -> List[Dict[str, Any]]:
    """
    Load pending MCQs from database for review.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        List of MCQ dictionaries with status='pending'
    """
    conn = connect(db_path)
    try:
        return list_mcqs(conn, status="pending", limit=20)
    finally:
        conn.close()

