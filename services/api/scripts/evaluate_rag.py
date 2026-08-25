"""Small deterministic evaluation harness for the retrieval endpoint.

Usage:
  API_URL=http://localhost:8000 WORKSPACE_ID=<uuid> python scripts/evaluate_rag.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")
WORKSPACE_ID = os.environ["WORKSPACE_ID"]
TOKEN = os.environ.get("CLERK_SESSION_TOKEN", "")


def main() -> None:
    cases = json.loads(
        Path(__file__).resolve().parents[1].joinpath("evals/rag_eval.json").read_text()
    )
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

    passed = 0
    with httpx.Client(base_url=API_URL, headers=headers, timeout=30) as client:
        for case in cases:
            response = client.post(
                f"/api/v1/workspaces/{WORKSPACE_ID}/search",
                json={"query": case["question"], "top_k": 5, "min_similarity": 0.0},
            )
            response.raise_for_status()
            text = " ".join(item["content"] for item in response.json()["results"]).lower()
            ok = all(term.lower() in text for term in case["expected_terms"])
            passed += int(ok)
            print(f"{case['id']}: {'PASS' if ok else 'FAIL'}")

    print(f"Recall-style term coverage: {passed}/{len(cases)}")


if __name__ == "__main__":
    main()
