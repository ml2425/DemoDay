"""Main entry point for MCQ generation system."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from ui.gradio_app import create_main_interface

if __name__ == "__main__":
    interface = create_main_interface()
    interface.launch(share=False, server_name="localhost", server_port=7860)

