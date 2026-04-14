from __future__ import annotations

import csv
import json
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.legal_extract.schemas import OutputType
from src.legal_extract.service import extract


TESTS: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------
    # AI Lead Assignment - 1.pdf
    # ------------------------------------------------------------------
    {
        "doc_name": "AI Lead Assignment - 1.pdf",
        "query": "What is the title of this assignment?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_exact",
        "expected": "Take-Home Assignment - 1",
    },
    {
        "doc_name": "AI Lead Assignment - 1.pdf",
        "query": "What is the duration?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "1-2 Days",
    },
    {
        "doc_name": "AI Lead Assignment - 1.pdf",
        "query": "What is the example output for the annual interest rate question?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 5.25,
    },
    {
        "doc_name": "AI Lead Assignment - 1.pdf",
        "query": "What is the example output for 'When does the lease start'?",
        "output_type": OutputType.DATE,
        "expected_found": True,
        "match_type": "date_exact",
        "expected": "2024-03-15",
    },
    {
        "doc_name": "AI Lead Assignment - 1.pdf",
        "query": "What are the example values shown for array of numbers?",
        "output_type": OutputType.ARRAY_NUMBER,
        "expected_found": True,
        "match_type": "array_number_exact",
        "expected": [5.25, 3.50],
    },
    {
        "doc_name": "AI Lead Assignment - 1.pdf",
        "query": "What is the repo URL to share the submission?",
        "output_type": OutputType.STRING,
        "expected_found": False,
        "match_type": "not_found",
        "expected": None,
    },

    # ------------------------------------------------------------------
    # Contract document.pdf
    # ------------------------------------------------------------------
    {
        "doc_name": "Contract document.pdf",
        "query": "What is the name of the institute?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "Indian Institute of Technology Kanpur",
    },
    {
        "doc_name": "Contract document.pdf",
        "query": "What is the security deposit amount?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 500000,
    },
    {
        "doc_name": "Contract document.pdf",
        "query": "When did the service provider commence the work?",
        "output_type": OutputType.DATE,
        "expected_found": True,
        "match_type": "date_exact",
        "expected": "2012-10-01",
    },
    {
        "doc_name": "Contract document.pdf",
        "query": "Which courts have jurisdiction under this agreement?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "Kanpur",
    },
    {
        "doc_name": "Contract document.pdf",
        "query": "What is the empanelment period?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "2 (Two) years",
        "input_mode": "bytes",
    },

    # ------------------------------------------------------------------
    # Loan Documentation - Customer copy_KB251222XCOIZ.pdf
    # ------------------------------------------------------------------
    {
        "doc_name": "Loan Documentation - Customer copy_KB251222XCOIZ.pdf",
        "query": "What is the total loan amount?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 27500,
    },
    {
        "doc_name": "Loan Documentation - Customer copy_KB251222XCOIZ.pdf",
        "query": "What is the annualized fixed rate of interest?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 28,
    },
    {
        "doc_name": "Loan Documentation - Customer copy_KB251222XCOIZ.pdf",
        "query": "What is the loan term in months?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 9,
    },
    {
        "doc_name": "Loan Documentation - Customer copy_KB251222XCOIZ.pdf",
        "query": "What is the net disbursed amount?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 25414,
    },
    {
        "doc_name": "Loan Documentation - Customer copy_KB251222XCOIZ.pdf",
        "query": "What is the cooling-off period?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "3 days",
        "examples": [
            {
                "input": {
                    "query": "What is the annualized fixed rate of interest?",
                    "output_type": "number",
                },
                "output": {
                    "value": 28,
                    "found": True,
                },
            }
        ],
    },

    # ------------------------------------------------------------------
    # PolicySoftCopy_1105948950.pdf
    # ------------------------------------------------------------------
    {
        "doc_name": "PolicySoftCopy_1105948950.pdf",
        "query": "What is the policy number?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_exact",
        "expected": "920292623071050303",
    },
    {
        "doc_name": "PolicySoftCopy_1105948950.pdf",
        "query": "What is the policy start date?",
        "output_type": OutputType.DATE,
        "expected_found": True,
        "match_type": "date_exact",
        "expected": "2026-04-05",
    },
    {
        "doc_name": "PolicySoftCopy_1105948950.pdf",
        "query": "What is the total premium payable?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 443,
    },
    {
        "doc_name": "PolicySoftCopy_1105948950.pdf",
        "query": "List the policy period dates.",
        "output_type": OutputType.ARRAY_DATE,
        "expected_found": True,
        "match_type": "array_date_exact",
        "expected": ["2026-04-05", "2027-04-04"],
    },
    {
        "doc_name": "PolicySoftCopy_1105948950.pdf",
        "query": "What is the nominee relationship?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "Father",
    },

    # ------------------------------------------------------------------
    # SampleContract-2.pdf
    # ------------------------------------------------------------------
    {
        "doc_name": "SampleContract-2.pdf",
        "query": "Who is the first party?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "NGO/UN agency",
    },
    {
        "doc_name": "SampleContract-2.pdf",
        "query": "Who is the second party?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "Company/agent",
    },
    {
        "doc_name": "SampleContract-2.pdf",
        "query": "How many days after distribution must the first party reimburse the second party in a hawala transaction?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 3,
    },
    {
        "doc_name": "SampleContract-2.pdf",
        "query": "What is the commission for Sarmada?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 0.6,
    },

    # ------------------------------------------------------------------
    # SampleContract-Shuttle.pdf
    # ------------------------------------------------------------------
    {
        "doc_name": "SampleContract-Shuttle.pdf",
        "query": "Who is the client party in this agreement?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "COMMISSION",
    },
    {
        "doc_name": "SampleContract-Shuttle.pdf",
        "query": "Who is the service provider party in this agreement?",
        "output_type": OutputType.STRING,
        "expected_found": True,
        "match_type": "string_contains",
        "expected": "CONSULTANT",
    },
    {
        "doc_name": "SampleContract-Shuttle.pdf",
        "query": "How many days written notice can COMMISSION give for convenience termination?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 30,
    },
    {
        "doc_name": "SampleContract-Shuttle.pdf",
        "query": "How many days advance notice must CONSULTANT give to terminate the agreement?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 120,
    },
    {
        "doc_name": "SampleContract-Shuttle.pdf",
        "query": "Within how many calendar days after performance of work must invoices be submitted?",
        "output_type": OutputType.NUMBER,
        "expected_found": True,
        "match_type": "number_exact",
        "expected": 45,
    },
]


DOC_ROOT = Path(__file__).resolve().parent / "test_docs"
OUT_DIR = Path(__file__).resolve().parent / "test_logs" / "test_docs_30"
DETAIL_JSON = OUT_DIR / "detailed_results.json"
SUMMARY_JSON = OUT_DIR / "summary.json"
DETAIL_CSV = OUT_DIR / "detailed_results.csv"


def normalize_text(x: Any) -> str:
    if x is None:
        return ""
    s = str(x)
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_number(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    s = str(x)
    m = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", s)
    if not m:
        return None
    return float(m[0].replace(",", ""))


def looks_like_iso_date(x: Any) -> bool:
    if not isinstance(x, str):
        return False
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", x.strip()))


def type_is_valid(value: Any, output_type: OutputType) -> bool:
    if value is None:
        return True

    if output_type == OutputType.STRING:
        return isinstance(value, str)

    if output_type == OutputType.DATE:
        return isinstance(value, str) and looks_like_iso_date(value)

    if output_type == OutputType.NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    if output_type == OutputType.ARRAY_STRING:
        return isinstance(value, list) and all(isinstance(v, str) for v in value)

    if output_type == OutputType.ARRAY_DATE:
        return isinstance(value, list) and all(isinstance(v, str) and looks_like_iso_date(v) for v in value)

    if output_type == OutputType.ARRAY_NUMBER:
        return isinstance(value, list) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)

    return False


def source_is_valid(pred: Dict[str, Any], expected_found: bool) -> bool:
    if not expected_found:
        return True

    sources = pred.get("sources", [])
    if not isinstance(sources, list) or not sources:
        return False

    for s in sources:
        if not isinstance(s, dict):
            return False
        page = s.get("page")
        snippet = s.get("snippet")
        if not isinstance(page, int):
            return False
        if not isinstance(snippet, str) or not snippet.strip():
            return False

    return True


def match_prediction(test: Dict[str, Any], pred: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    expected_found = test["expected_found"]
    pred_found = bool(pred.get("found"))
    pred_value = pred.get("value")

    if expected_found != pred_found:
        return False, {
            "reason": "found_mismatch",
            "expected_found": expected_found,
            "pred_found": pred_found,
        }

    if not expected_found:
        return True, {
            "reason": "correct_not_found",
        }

    match_type = test["match_type"]

    if match_type == "string_exact":
        ok = normalize_text(pred_value) == normalize_text(test["expected"])
        return ok, {"reason": match_type, "expected": test["expected"], "pred": pred_value}

    if match_type == "string_contains":
        ok = normalize_text(test["expected"]) in normalize_text(pred_value)
        return ok, {"reason": match_type, "expected": test["expected"], "pred": pred_value}

    if match_type == "string_contains_any":
        pred_norm = normalize_text(pred_value)
        ok = any(normalize_text(x) in pred_norm for x in test["expected_any"])
        return ok, {"reason": match_type, "expected_any": test["expected_any"], "pred": pred_value}

    if match_type == "number_exact":
        ok = normalize_number(pred_value) == float(test["expected"])
        return ok, {"reason": match_type, "expected": test["expected"], "pred": pred_value}

    if match_type == "date_exact":
        ok = normalize_text(pred_value) == normalize_text(test["expected"])
        return ok, {"reason": match_type, "expected": test["expected"], "pred": pred_value}

    if match_type == "array_string_subset":
        pred_items = pred_value if isinstance(pred_value, list) else []
        pred_norm = [normalize_text(x) for x in pred_items]
        ok = all(any(normalize_text(exp) in p or p in normalize_text(exp) for p in pred_norm) for exp in test["expected"])
        return ok, {"reason": match_type, "expected": test["expected"], "pred": pred_value}

    if match_type == "array_date_exact":
        pred_items = pred_value if isinstance(pred_value, list) else []
        ok = sorted([normalize_text(x) for x in pred_items]) == sorted([normalize_text(x) for x in test["expected"]])
        return ok, {"reason": match_type, "expected": test["expected"], "pred": pred_value}

    if match_type == "array_number_exact":
        pred_items = pred_value if isinstance(pred_value, list) else []
        pred_nums = [normalize_number(x) for x in pred_items]
        exp_nums = [float(x) for x in test["expected"]]
        ok = pred_nums == exp_nums
        return ok, {"reason": match_type, "expected": test["expected"], "pred": pred_value}

    if match_type == "not_found":
        ok = pred_found is False
        return ok, {"reason": match_type}

    return False, {"reason": "unknown_match_type", "match_type": match_type}


def init_bucket() -> Dict[str, Any]:
    return {
        "n": 0,
        "pass": 0,
        "fail": 0,
        "found_match_pass": 0,
        "type_valid_pass": 0,
        "source_valid_pass": 0,
        "latency_total_sec": 0.0,
    }


def bucket_finalize(bucket: Dict[str, Any]) -> Dict[str, Any]:
    n = bucket["n"] or 1
    return {
        **bucket,
        "pass_rate": round(bucket["pass"] / n, 4),
        "fail_rate": round(bucket["fail"] / n, 4),
        "found_match_rate": round(bucket["found_match_pass"] / n, 4),
        "type_valid_rate": round(bucket["type_valid_pass"] / n, 4),
        "source_valid_rate": round(bucket["source_valid_pass"] / n, 4),
        "avg_latency_sec": round(bucket["latency_total_sec"] / n, 4),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    detailed_results: List[Dict[str, Any]] = []
    overall = init_bucket()
    by_doc: Dict[str, Dict[str, Any]] = defaultdict(init_bucket)
    by_output_type: Dict[str, Dict[str, Any]] = defaultdict(init_bucket)

    for idx, test in enumerate(TESTS, start=1):
        pdf_path = DOC_ROOT / test["doc_name"]
        input_mode = test.get("input_mode", "path")

        if input_mode == "bytes":
            pdf_input = pdf_path.read_bytes()
        else:
            pdf_input = str(pdf_path)

        started = time.time()
        pred = extract(
            pdf=pdf_input,
            query=test["query"],
            output_type=test["output_type"],
            examples=test.get("examples"),
        )
        latency_sec = time.time() - started

        passed, match_info = match_prediction(test, pred)

        pred_found = bool(pred.get("found"))
        found_match = (pred_found == test["expected_found"])
        pred_type_valid = type_is_valid(pred.get("value"), test["output_type"])
        pred_source_valid = source_is_valid(pred, test["expected_found"])

        row = {
            "case_id": idx,
            "doc_name": test["doc_name"],
            "query": test["query"],
            "output_type": test["output_type"].value,
            "expected_found": test["expected_found"],
            "expected": test.get("expected"),
            "expected_any": test.get("expected_any"),
            "input_mode": input_mode,
            "used_examples": bool(test.get("examples")),
            "prediction": pred,
            "match_pass": passed,
            "match_info": match_info,
            "found_match": found_match,
            "type_valid": pred_type_valid,
            "source_valid": pred_source_valid,
            "latency_sec": round(latency_sec, 4),
        }
        detailed_results.append(row)

        for bucket in (overall, by_doc[test["doc_name"]], by_output_type[test["output_type"].value]):
            bucket["n"] += 1
            bucket["latency_total_sec"] += latency_sec

            if passed:
                bucket["pass"] += 1
            else:
                bucket["fail"] += 1

            if found_match:
                bucket["found_match_pass"] += 1

            if pred_type_valid:
                bucket["type_valid_pass"] += 1

            if pred_source_valid:
                bucket["source_valid_pass"] += 1

    summary = {
        "overall": bucket_finalize(overall),
        "by_doc": {k: bucket_finalize(v) for k, v in by_doc.items()},
        "by_output_type": {k: bucket_finalize(v) for k, v in by_output_type.items()},
        "meta": {
            "total_cases": len(TESTS),
            "docs_tested": sorted(list({t["doc_name"] for t in TESTS})),
            "bytes_input_cases": sum(1 for t in TESTS if t.get("input_mode") == "bytes"),
            "few_shot_cases": sum(1 for t in TESTS if t.get("examples")),
            "expected_not_found_cases": sum(1 for t in TESTS if not t["expected_found"]),
        },
    }

    with open(DETAIL_JSON, "w", encoding="utf-8") as f:
        json.dump(detailed_results, f, indent=2, ensure_ascii=False)

    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    with open(DETAIL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "doc_name",
                "query",
                "output_type",
                "expected_found",
                "input_mode",
                "used_examples",
                "match_pass",
                "found_match",
                "type_valid",
                "source_valid",
                "latency_sec",
            ],
        )
        writer.writeheader()
        for row in detailed_results:
            writer.writerow({
                "case_id": row["case_id"],
                "doc_name": row["doc_name"],
                "query": row["query"],
                "output_type": row["output_type"],
                "expected_found": row["expected_found"],
                "input_mode": row["input_mode"],
                "used_examples": row["used_examples"],
                "match_pass": row["match_pass"],
                "found_match": row["found_match"],
                "type_valid": row["type_valid"],
                "source_valid": row["source_valid"],
                "latency_sec": row["latency_sec"],
            })

    print("\n=== OVERALL ===")
    print(json.dumps(summary["overall"], indent=2, ensure_ascii=False))

    print("\n=== BY DOC ===")
    print(json.dumps(summary["by_doc"], indent=2, ensure_ascii=False))

    print("\n=== BY OUTPUT TYPE ===")
    print(json.dumps(summary["by_output_type"], indent=2, ensure_ascii=False))

    print("\nSaved:")
    print(f"- {DETAIL_JSON}")
    print(f"- {SUMMARY_JSON}")
    print(f"- {DETAIL_CSV}")


if __name__ == "__main__":
    main()
