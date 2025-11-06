"""Gradio UI for MCQ generation and review."""

import gradio as gr
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
from pipeline.workflow import run_pipeline
from database.db_utils import connect, get_mcqs_by_status, update_mcq_status, get_triple, get_source

load_dotenv()


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
    
    def list_pending_mcqs():
        """List all pending MCQ IDs."""
        conn = connect()
        mcqs = get_mcqs_by_status(conn, status="pending")
        conn.close()
        
        if not mcqs:
            return "No pending MCQs found. Generate some MCQs first!"
        
        # Format list
        lines = [f"Found {len(mcqs)} pending MCQs:\n"]
        for mcq in mcqs:
            question_preview = mcq['question'][:60] + "..." if len(mcq['question']) > 60 else mcq['question']
            lines.append(f"MCQ ID {mcq['mcq_id']}: {question_preview}")
        
        return "\n".join(lines)
    
    def display_mcq(mcq_id_str: str):
        """Display MCQ details for review."""
        try:
            mcq_id = int(mcq_id_str.strip())
        except (ValueError, AttributeError):
            return "Please enter a valid MCQ ID number", "", "", "", "", ""
        
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
            return f"MCQ ID {mcq_id} not found. Use 'List Pending MCQs' to see available IDs.", "", "", "", "", ""
        
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
        """Request improvement for an MCQ - regenerates based on user feedback."""
        try:
            mcq_id = int(mcq_id_str)
            conn = connect()
            
            # Get existing MCQ
            cursor = conn.execute(
                """SELECT m.*, t.head_entity, t.relation, t.tail_entity, t.evidence_snippet
                   FROM mcqs m
                   JOIN triples t ON m.triple_id = t.triple_id
                   WHERE m.mcq_id = ?""",
                (mcq_id,)
            )
            row = cursor.fetchone()
            if not row:
                conn.close()
                return f"Error: MCQ {mcq_id} not found"
            
            mcq = dict(row)
            triple = {
                "head_entity": mcq["head_entity"],
                "relation": mcq["relation"],
                "tail_entity": mcq["tail_entity"]
            }
            evidence_snippet = mcq["evidence_snippet"]
            
            # Build improved prompt with feedback
            head = triple["head_entity"]
            relation = triple["relation"]
            tail = triple["tail_entity"]
            
            prompt = f"""Generate an IMPROVED medical MCQ from this VERIFIED relationship, incorporating user feedback.

**VERIFIED Relationship (from database - DO NOT CHANGE):**
- Head: {head}
- Relation: {relation}
- Tail: {tail}

**Evidence Snippet:**
"{evidence_snippet}"

**User Feedback:**
"{feedback}"

**CRITICAL REQUIREMENTS:**
1. MCQ MUST test understanding of EXACT relationship: {head} {relation} {tail} (unchanged)
2. Incorporate user feedback to improve the question
3. Correct answer MUST be directly supported by evidence snippet
4. You CANNOT modify or change the relationship
5. MCQ must be accurate, educational, and medically sound
6. Use v3.2 format: stem_scenario (2-4 lines) + question (1 line) + 5 choices

**Output JSON:**
{{
    "stem_scenario": "Improved clinical vignette (2-4 lines of context)",
    "question": "Improved direct question line",
    "choices": [
        "Option A (correct answer - incorporate feedback)",
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

**IMPORTANT:** The triple_used MUST match the relationship above exactly. Incorporate user feedback into the question, choices, and explanation."""
            
            # Call LLM to regenerate
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                conn.close()
                return "Error: OPENAI_API_KEY not found"
            
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a medical education expert. Improve MCQs based on user feedback while maintaining the exact same underlying medical relationship."},
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
            if (triple_used.get("head") != head or
                triple_used.get("relation") != relation or
                triple_used.get("tail") != tail):
                conn.close()
                return "Error: Triple changed during regeneration - rejected for safety"
            
            # Update MCQ with new content
            choices_json = json.dumps(mcq_data["choices"])
            triple_used_json = json.dumps(triple_used)
            
            conn.execute(
                """UPDATE mcqs 
                   SET stem_scenario = ?, question = ?, choices_json = ?, correct_index = ?,
                       explanation = ?, triple_used_json = ?, status = 'pending',
                       user_feedback = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE mcq_id = ?""",
                (mcq_data["stem_scenario"], mcq_data["question"], choices_json,
                 mcq_data["correct_index"], mcq_data["explanation"], triple_used_json,
                 feedback, mcq_id)
            )
            conn.commit()
            
            # Log decision
            conn.execute(
                "INSERT INTO decisions (mcq_id, action, feedback) VALUES (?, ?, ?)",
                (mcq_id, "improve", feedback)
            )
            conn.commit()
            conn.close()
            
            return f"MCQ regenerated successfully! Reload MCQ ID {mcq_id} to see changes."
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    with gr.Blocks(title="MCQ Review") as interface:
        gr.Markdown("# MCQ Review & Approval")
        
        with gr.Row():
            with gr.Column():
                # Add button to list pending MCQs
                list_btn = gr.Button("📋 List Pending MCQs", variant="secondary")
                mcq_list_display = gr.Textbox(label="Pending MCQs", lines=5, interactive=False)
                
                mcq_id_input = gr.Textbox(label="MCQ ID", placeholder="Enter MCQ ID (use list above to find IDs)")
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
        
        # List pending MCQs
        list_btn.click(
            list_pending_mcqs,
            outputs=[mcq_list_display]
        )
        
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

