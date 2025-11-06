"""Gradio UI for MCQ generation and review."""

import gradio as gr
import json
from pathlib import Path
from typing import Optional, Dict, Any
from pipeline.workflow import run_pipeline
from database.db_utils import connect, get_mcqs_by_status, update_mcq_status, get_triple, get_source


def format_citation(source: dict) -> str:
    """Format source citation for display."""
    source_type = source.get("source_type", "")
    metadata = json.loads(source.get("metadata_json", "{}") or "{}")
    
    if source_type == "PUBMED":
        pmid = source["source_id"].replace("PMID:", "")
        title = metadata.get("title", "")
        authors = metadata.get("authors", "")
        
        citation = f"PMID: {pmid}"
        if title:
            citation += f"\n{title}"
        if authors:
            citation += f"\n{authors}"
        
        # Add clickable link
        citation += f"\nhttps://pubmed.ncbi.nlm.nih.gov/{pmid}"
        
        return citation
    
    elif source_type == "LOCAL_PDF":
        filename = metadata.get("filename", "")
        title = metadata.get("title", "")
        
        if title:
            return f"{title}\n{filename}"
        return filename
    
    return source["source_id"]


def process_source(
    source_type: str,
    pdf_file: Optional[gr.File],
    keywords: str,
    max_results: int
) -> tuple[str, list]:
    """
    Process source (PDF or PubMed) and generate MCQs.
    
    Returns:
        Tuple of (status_message, list_of_mcqs)
    """
    try:
        if source_type == "PDF Upload":
            if not pdf_file:
                return "Error: Please upload a PDF file", []
            
            pdf_path = pdf_file.name if isinstance(pdf_file, str) else pdf_file
            
            # Run pipeline
            result = run_pipeline(
                source_type="PDF",
                pdf_path=pdf_path
            )
            
            status = f"Processed PDF. Generated {len(result.get('verified_mcqs', []))} MCQs."
            return status, result.get("verified_mcqs", [])
        
        elif source_type == "PubMed Search":
            if not keywords.strip():
                return "Error: Please enter search keywords", []
            
            # Run pipeline
            result = run_pipeline(
                source_type="PUBMED",
                keywords=keywords,
                max_results=max_results
            )
            
            status = f"Searched PubMed for '{keywords}'. Generated {len(result.get('verified_mcqs', []))} MCQs."
            return status, result.get("verified_mcqs", [])
        
        return "Error: Invalid source type", []
    
    except Exception as e:
        return f"Error: {str(e)}", []


def load_pending_mcqs() -> list:
    """Load pending MCQs from database."""
    conn = connect()
    mcqs = get_mcqs_by_status(conn, status="pending")
    conn.close()
    return mcqs


def create_review_interface():
    """Create MCQ review interface."""
    
    def display_mcq(mcq_id: int):
        """Display MCQ details for review."""
        conn = connect()
        
        # Get MCQ
        cursor = conn.execute(
            """SELECT m.*, t.head_entity, t.relation, t.tail_entity, t.evidence_snippet,
                      s.source_id, s.source_type, s.metadata_json
               FROM mcqs m
               JOIN triples t ON m.triple_id = t.triple_id
               JOIN sources s ON t.source_id = s.source_id
               WHERE m.mcq_id = ?""",
            (mcq_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return "MCQ not found", "", "", "", "", ""
        
        mcq = dict(row)
        
        # Format MCQ display
        choices = json.loads(mcq["choices_json"])
        choices_text = "\n".join([f"{chr(65+i)}. {choice}" for i, choice in enumerate(choices)])
        correct_letter = chr(65 + mcq["correct_index"])
        
        mcq_display = f"""**Stem Scenario:**
{mcq['stem_scenario']}

**Question:**
{mcq['question']}

**Choices:**
{choices_text}

**Correct Answer: {correct_letter}**

**Explanation:**
{mcq['explanation']}"""
        
        # Format triple
        triple_display = f"**Head:** {mcq['head_entity']}\n**Relation:** {mcq['relation']}\n**Tail:** {mcq['tail_entity']}"
        
        # Format evidence
        evidence_display = mcq['evidence_snippet']
        
        # Format citation
        source = {
            "source_id": mcq["source_id"],
            "source_type": mcq["source_type"],
            "metadata_json": mcq["metadata_json"]
        }
        citation_display = format_citation(source)
        
        # Verification status
        verification_status = mcq.get("verification_status", "unknown")
        verification_confidence = mcq.get("verification_confidence", 0.0)
        status_display = f"Status: {verification_status.upper()}\nConfidence: {verification_confidence:.2f}"
        
        return str(mcq_id), mcq_display, triple_display, evidence_display, citation_display, status_display
    
    def approve_mcq(mcq_id_str: str):
        """Approve an MCQ."""
        try:
            mcq_id = int(mcq_id_str)
            conn = connect()
            update_mcq_status(conn, mcq_id, "approved")
            conn.close()
            return "MCQ approved successfully!"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def reject_mcq(mcq_id_str: str, feedback: str):
        """Reject an MCQ."""
        try:
            mcq_id = int(mcq_id_str)
            conn = connect()
            update_mcq_status(conn, mcq_id, "rejected", feedback)
            conn.close()
            return "MCQ rejected."
        except Exception as e:
            return f"Error: {str(e)}"
    
    def improve_mcq(mcq_id_str: str, feedback: str):
        """Request improvement for an MCQ."""
        try:
            mcq_id = int(mcq_id_str)
            conn = connect()
            update_mcq_status(conn, mcq_id, "refining", feedback)
            conn.close()
            return "Improvement requested. Regenerating MCQ..."
        except Exception as e:
            return f"Error: {str(e)}"
    
    with gr.Blocks(title="MCQ Review") as interface:
        gr.Markdown("# MCQ Review & Approval")
        
        with gr.Row():
            with gr.Column():
                mcq_id_input = gr.Textbox(label="MCQ ID", placeholder="Enter MCQ ID")
                load_btn = gr.Button("Load MCQ", variant="primary")
                
                mcq_display = gr.Markdown(label="MCQ")
                triple_display = gr.Markdown(label="Triple Used")
                evidence_display = gr.Textbox(label="Evidence Snippet", lines=5, interactive=False)
                citation_display = gr.Textbox(label="Source Citation", lines=3, interactive=False)
                status_display = gr.Textbox(label="Verification Status", interactive=False)
            
            with gr.Column():
                feedback_input = gr.Textbox(label="Feedback (for improvement)", lines=3)
                
                approve_btn = gr.Button("✓ Approve", variant="primary")
                reject_btn = gr.Button("✗ Reject", variant="stop")
                improve_btn = gr.Button("🔄 Request Better Question")
                
                status_output = gr.Textbox(label="Action Status", interactive=False)
        
        load_btn.click(
            display_mcq,
            inputs=[mcq_id_input],
            outputs=[mcq_id_input, mcq_display, triple_display, evidence_display, citation_display, status_display]
        )
        
        approve_btn.click(approve_mcq, inputs=[mcq_id_input], outputs=[status_output])
        reject_btn.click(reject_mcq, inputs=[mcq_id_input, feedback_input], outputs=[status_output])
        improve_btn.click(improve_mcq, inputs=[mcq_id_input, feedback_input], outputs=[status_output])
    
    return interface


def create_input_interface():
    """Create input interface for PDF/PubMed."""
    
    with gr.Blocks(title="MCQ Generator") as interface:
        gr.Markdown("# Medical MCQ Generator")
        
        source_type = gr.Radio(
            choices=["PDF Upload", "PubMed Search"],
            label="Source Type",
            value="PDF Upload"
        )
        
        with gr.Group(visible=True) as pdf_group:
            pdf_file = gr.File(
                label="Upload PDF",
                file_types=[".pdf"]
            )
        
        with gr.Group(visible=False) as pubmed_group:
            keywords_input = gr.Textbox(
                label="Search Keywords",
                placeholder="e.g., temozolomide glioblastoma"
            )
            max_results_slider = gr.Slider(
                minimum=1,
                maximum=10,
                value=5,
                step=1,
                label="Max Results"
            )
        
        submit_btn = gr.Button("Process", variant="primary")
        
        status_output = gr.Textbox(label="Status", interactive=False)
        mcqs_output = gr.JSON(label="Generated MCQs", visible=False)
        
        def toggle_source(source):
            if source == "PDF Upload":
                return gr.update(visible=True), gr.update(visible=False)
            else:
                return gr.update(visible=False), gr.update(visible=True)
        
        source_type.change(
            toggle_source,
            inputs=[source_type],
            outputs=[pdf_group, pubmed_group]
        )
        
        submit_btn.click(
            process_source,
            inputs=[source_type, pdf_file, keywords_input, max_results_slider],
            outputs=[status_output, mcqs_output]
        )
    
    return interface


def create_main_interface():
    """Create main Gradio interface with tabs."""
    
    with gr.Blocks(title="MCQ Generator") as interface:
        gr.Markdown("# Provenance-First MCQ Generation System")
        
        with gr.Tabs():
            with gr.Tab("Input"):
                input_interface = create_input_interface()
            
            with gr.Tab("Review"):
                review_interface = create_review_interface()
    
    return interface


if __name__ == "__main__":
    interface = create_main_interface()
    interface.launch(share=False)

