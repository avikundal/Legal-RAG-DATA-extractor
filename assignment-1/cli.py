from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.legal_extract.schemas import OutputType
from src.legal_extract.service import extract


def parse_output_type(output_type_str: str) -> OutputType:
    s = output_type_str.strip().lower()

    allowed = {
        "string": OutputType.STRING,
        "date": OutputType.DATE,
        "number": OutputType.NUMBER,
        "array[string]": OutputType.ARRAY_STRING,
        "array[date]": OutputType.ARRAY_DATE,
        "array[number]": OutputType.ARRAY_NUMBER,
    }

    if s not in allowed:
        raise ValueError(
            "Unsupported output_type. Use one of: string, date, number, array[string], array[date], array[number]"
        )

    return allowed[s]


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract one structured field from a legal PDF.")
    parser.add_argument("--pdf", required=True, help="Path to the source PDF document")
    parser.add_argument("--query", required=True, help="Natural-language query describing one field to extract")
    parser.add_argument(
        "--output-type",
        required=True,
        help="Expected output type: string, date, number, array[string], array[date], array[number]",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieved chunks to pass into extraction")

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(
            json.dumps(
                {
                    "value": None,
                    "found": False,
                    "sources": [],
                    "error": {
                        "code": "FILE_NOT_FOUND",
                        "message": f"PDF file not found: {pdf_path}",
                    },
                },
                indent=2,
            )
        )
        return 1

    try:
        output_type = parse_output_type(args.output_type)
    except Exception as e:
        print(
            json.dumps(
                {
                    "value": None,
                    "found": False,
                    "sources": [],
                    "error": {
                        "code": "INVALID_OUTPUT_TYPE",
                        "message": str(e),
                    },
                },
                indent=2,
            )
        )
        return 1

    try:
        result = extract(
            pdf=str(pdf_path),
            query=args.query,
            output_type=output_type,
            examples=None,
            top_k=args.top_k,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        print(
            json.dumps(
                {
                    "value": None,
                    "found": False,
                    "sources": [],
                    "error": {
                        "code": "CLI_ERROR",
                        "message": str(e),
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
