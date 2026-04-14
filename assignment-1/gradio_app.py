from __future__ import annotations

import json
from typing import Any

import gradio as gr

from src.legal_extract.schemas import OutputType
from src.legal_extract.service import extract


OUTPUT_TYPE_MAP = {
    "string": OutputType.STRING,
    "date": OutputType.DATE,
    "number": OutputType.NUMBER,
    "array[string]": OutputType.ARRAY_STRING,
    "array[date]": OutputType.ARRAY_DATE,
    "array[number]": OutputType.ARRAY_NUMBER,
}

DEFAULT_EXAMPLES_JSON = """[
  {
    "input": {
      "query": "What law governs this agreement?",
      "output_type": "string"
    },
    "output": {
      "value": "the laws of Delaware",
      "found": true
    }
  }
]"""


def run_extract(pdf_file: str, query: str, output_type_str: str, examples_json: str) -> dict[str, Any]:
    if not pdf_file:
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": {
                "code": "NO_FILE",
                "message": "Please upload a PDF file.",
            },
        }

    if not query or not query.strip():
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": {
                "code": "NO_QUERY",
                "message": "Please enter a query.",
            },
        }

    output_type = OUTPUT_TYPE_MAP[output_type_str]

    examples = None
    if examples_json and examples_json.strip():
        try:
            examples = json.loads(examples_json)
            if not isinstance(examples, list):
                return {
                    "value": None,
                    "found": False,
                    "sources": [],
                    "error": {
                        "code": "BAD_EXAMPLES",
                        "message": "Examples must be a JSON array.",
                    },
                }
        except Exception as e:
            return {
                "value": None,
                "found": False,
                "sources": [],
                "error": {
                    "code": "BAD_EXAMPLES_JSON",
                    "message": f"Could not parse examples JSON: {e}",
                },
            }

    try:
        result = extract(
            pdf=pdf_file,
            query=query.strip(),
            output_type=output_type,
            examples=examples,
        )
        return result
    except Exception as e:
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": {
                "code": "UI_RUNTIME_ERROR",
                "message": str(e),
            },
        }


# 🔥 Custom styling
custom_css = """
h1 { font-size: 36px !important; font-weight: 700 !important; }
h2 { font-size: 22px !important; margin-top: 10px !important; }
.section { padding: 15px; border-radius: 10px; background: #f9fafb; }
.gr-button { font-size: 16px !important; padding: 10px !important; }
"""


with gr.Blocks(title="PDF Data Extraction", css=custom_css) as demo:

    gr.Markdown("# 📄 PDF Data Extraction")
    gr.Markdown(
        "Upload a legal PDF, enter a query, and extract structured information."
    )

    with gr.Row():

        with gr.Column(scale=1):
            gr.Markdown("## 🔹 Input")

            pdf_file = gr.File(
                label="Upload PDF",
                file_types=[".pdf"],
                type="filepath",
            )

            query = gr.Textbox(
                label="Query",
                placeholder="Example: What law governs this agreement?",
                lines=2,
            )

            output_type = gr.Dropdown(
                label="Output Type",
                choices=list(OUTPUT_TYPE_MAP.keys()),
                value="string",
            )

            examples_json = gr.Textbox(
                label="Few-shot Examples (optional)",
                value="",
                placeholder=DEFAULT_EXAMPLES_JSON,
                lines=10,
            )

            run_btn = gr.Button("Run Extraction", variant="primary")

        with gr.Column(scale=1):
            gr.Markdown("## 🔹 Output")

            result_json = gr.JSON(label="Result")

    run_btn.click(
        fn=run_extract,
        inputs=[pdf_file, query, output_type, examples_json],
        outputs=result_json,
    )


if __name__ == "__main__":
    demo.launch()
