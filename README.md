# HyperVerge Assignment

This repository contains both parts of the HyperVerge AI Lead take-home assignment.

## Repository structure

* `assignment-1/` — Legal PDF QnA Agent
* `assignment-2/` — OCR / notebook-based assignment work

---

## Assignment 1

This is the main system implementation for PDF question answering and structured field extraction.

It includes:

* CLI
* Gradio demo
* source code
* tests
* evaluation logs

Main entry points:

* `assignment-1/cli.py`
* `assignment-1/gradio_app.py`

### Quick setup

```bash
cd assignment-1

conda create -n hv_env python=3.10 -y
conda activate hv_env

pip install -r requirements.txt
```

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your_key_here"
```

Optional model override:

```bash
export OPENAI_MODEL="gpt-4.1-mini"
```

### Run tests

```bash
python -m pytest -q tests
python eval_test_docs_30.py
```

### Run CLI

```bash
python cli.py --pdf "test_docs/PolicySoftCopy_1105948950.pdf" --query "What is the total premium payable?" --output-type number
```

### Run Gradio demo

```bash
python gradio_app.py
```

---

## Assignment 2

This folder contains the OCR / notebook-based part of the assignment.

It includes:

* `AI_Lead_Assignment_2.ipynb`
* supporting testing crops

### Quick setup

```bash
cd assignment-2

conda create -n hv_ocr_env python=3.10 -y
conda activate hv_ocr_env
```

Then open the notebook and run it step by step.

If needed:

```bash
jupyter notebook
```

or

```bash
jupyter lab
```

---

## Notes

* Assignment 1 is the main production-style implementation.
* Assignment 2 is notebook-driven and includes sample testing crops for experimentation and validation.
* All paths in the repo are kept relative so the project can be run without changing hardcoded machine-specific paths.
