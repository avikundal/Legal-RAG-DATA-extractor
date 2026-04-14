# PDF Data Extraction for Legal Documents

This is a PDF Data Extractor built for the HyperVerge AI Lead take-home assignment.

The system extracts **one field per call** from a PDF using:

* a natural-language query
* an expected output type
* optional few-shot examples

Although the system is optimized for legal-style retrieval and extraction, other text-based PDFs can also be used.

It returns structured JSON with:

* `value`
* `found`
* `sources`
* `error`

Example queries:

* Who are the named parties in this agreement?
* What law governs this plan?
* What is the maximum term of an option?
* What is the total premium payable?
* List the policy period dates.

---

## What the system supports

Supported output types:

* `string`
* `date`
* `number`
* `array[string]`
* `array[date]`
* `array[number]`

PDF input supports:

* file path
* raw bytes

The system is designed for **text-based multi-page PDFs** and tries to preserve useful structure like:

* section headers
* numbered clauses
* tables

---

## High-level pipeline

The pipeline is split into separate parts:

* **PDF parser**
  Uses PyMuPDF for body text extraction and pdfplumber for table extraction.

* **Chunker**
  Splits parsed text into retrieval chunks while trying to keep clauses / paragraphs intact.

* **Retriever**
  Uses hybrid retrieval over chunks to avoid sending the full document to the LLM.

* **Extractor**
  Builds a grounded prompt from the retrieved chunks and asks the LLM to return strict JSON.

* **Validator**
  Enforces the requested output type and normalizes dates / numbers / arrays.

* **Service layer**
  Orchestrates the full flow and returns a structured response.

---

## Example output

```json
{
  "value": "2024-03-15",
  "found": true,
  "sources": [
    {
      "page": 3,
      "snippet": "The lease start date shall be March 15, 2024..."
    }
  ],
  "error": null
}
```

---

## Setup

Create and activate a fresh conda environment:

```bash
conda create -n hv_env python=3.10 -y
conda activate hv_env
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your API key:

```bash
export OPENAI_API_KEY="your_key_here"
```

Optional model override:

```bash
export OPENAI_MODEL="gpt-4.1-mini"
```

---

## CLI usage

Example:

```bash
python cli.py --pdf "test_docs/PolicySoftCopy_1105948950.pdf" --query "What is the total premium payable?" --output-type number
```

Another example:

```bash
python cli.py --pdf "test_docs/SampleContract-2.pdf" --query "Who is the first party?" --output-type string
```

Array example:

```bash
python cli.py --pdf "test_docs/PolicySoftCopy_1105948950.pdf" --query "List the policy period dates." --output-type "array[date]"
```

---

## Python usage

```python
from src.legal_extract.service import extract
from src.legal_extract.schemas import OutputType

result = extract(
    pdf="test_docs/PolicySoftCopy_1105948950.pdf",
    query="What is the total premium payable?",
    output_type=OutputType.NUMBER,
)

print(result)
```

Raw bytes input also works:

```python
from pathlib import Path
from src.legal_extract.service import extract
from src.legal_extract.schemas import OutputType

pdf_bytes = Path("test_docs/PolicySoftCopy_1105948950.pdf").read_bytes()

result = extract(
    pdf=pdf_bytes,
    query="What is the policy start date?",
    output_type=OutputType.DATE,
)

print(result)
```

---

## Few-shot examples

Few-shot examples can be passed through the `examples` argument.

```python
from src.legal_extract.service import extract
from src.legal_extract.schemas import OutputType

examples = [
    {
        "input": {
            "query": "What law governs this agreement?",
            "output_type": "string"
        },
        "output": {
            "value": "the laws of Delaware",
            "found": True
        }
    }
]

result = extract(
    pdf="test_docs/SampleContract-2.pdf",
    query="Who is the second party?",
    output_type=OutputType.STRING,
    examples=examples,
)

print(result)
```

---

## Gradio demo

A small Gradio UI is also included for quick manual testing.

Run it with:

```bash
python gradio_app.py
```

This lets you:

* upload a PDF
* enter a query
* choose the output type
* optionally provide few-shot examples
* inspect the structured JSON response

---

## Testing

Run the main test suite:

```bash
python -m pytest -q tests
```

Run the curated 30-case evaluation:

```bash
python eval_test_docs_30.py | tee test_logs/test_docs_30_console.txt
```

Saved outputs:

* `test_logs/test_docs_30/detailed_results.json`
* `test_logs/test_docs_30/summary.json`
* `test_logs/test_docs_30/detailed_results.csv`

---

## What was tested

I created a curated **30-case end-to-end evaluation set** covering:

* string
* date
* number
* array[number]
* array[date]
* found cases
* not-found cases
* bytes input
* few-shot input

The evaluation was run on these public/sample PDFs:

* `AI Lead Assignment - 1.pdf`
* `Contract document.pdf`
* `Loan Documentation - Customer copy_KB251222XCOIZ.pdf`
* `PolicySoftCopy_1105948950.pdf`
* `SampleContract-2.pdf`
* `SampleContract-Shuttle.pdf`

### Final curated results

* **30 total cases**
* **29 passed**
* **1 failed**
* **Pass rate: 96.67%**
* **Found/not-found correctness: 100%**
* **Type-valid outputs: 100%**
* **Source attribution validity: 100%**
* **Average latency: 18.30 seconds/query**

### Per-document

* `AI Lead Assignment - 1.pdf` → **6/6**
* `Contract document.pdf` → **4/5**
* `Loan Documentation - Customer copy_KB251222XCOIZ.pdf` → **5/5**
* `PolicySoftCopy_1105948950.pdf` → **5/5**
* `SampleContract-2.pdf` → **4/4**
* `SampleContract-Shuttle.pdf` → **5/5**

### Per-output-type

* `string` → **13/13**
* `number` → **12/12**
* `date` → **2/3**
* `array[number]` → **1/1**
* `array[date]` → **1/1**

### Additional coverage

* **1 bytes-input case**
* **1 few-shot case**
* **1 expected not-found case**

### Unit tests

* **25 unit tests passed**

---

## Notes on test data

I initially explored using the **CUAD** dataset for evaluation, since it is a common legal benchmark. It was useful as a stress test, but in practice it was harder to debug while building the system because the dataset was available in JSON/text form, not as original PDFs in the same workflow I was testing. That meant I could evaluate extraction quality, but the PDF parsing side was not really under my control in that setup.

Because of that, I used a curated set of public/sample PDFs for practical end-to-end testing. That made it much easier to inspect:

* the original document
* parsed text
* chunks
* retrieved evidence
* final extracted answer

So the final test results in this repo are based on documents where I could directly verify the full pipeline end to end.

---

## Known limitations

This is a practical extraction system, not a perfect legal reasoning engine.

Main limitations right now:

* scanned PDFs / OCR-heavy docs are not the main target yet
* party extraction and legal disambiguation can still be tricky on more complex documents
* the current evaluation is strong, but still limited in size compared to a large benchmark

In the final public-document evaluation, the only failed case came from a contract-style document where a date-like clause was retrieved instead of the exact commencement date. This highlights that dense legal/template contracts can still require stronger clause-level retrieval or reranking for date extraction.

Broader PDF coverage would still benefit from:

* more evaluation data
* OCR fallback for harder PDFs
* stronger reranking / retrieval tuning for ambiguous queries

---

## Notes

A few practical implementation choices:

* switched body-text extraction from pdfplumber to **PyMuPDF** because it handled some PDFs better
* kept **pdfplumber** for table extraction
* used targeted chunk retrieval instead of full-document prompting to keep token usage lower
* added explicit output validation before returning results

---

## Deliverables included

* Python project
* working CLI
* optional Gradio demo
* modular source code
* test suite
* test results
* curated evaluation logs

---

## Possible future improvements

* confidence scores
* reranking layer for evidence chunks
* OCR fallback for harder PDFs
* broader benchmark evaluation

---

## Submission note

Before sharing the repo / zip:

* make sure `README.md` is included
* include tests and final evaluation logs
* remove any real API keys from code, shell history, or saved files
* remove cache files / temporary files / OS metadata before zipping
