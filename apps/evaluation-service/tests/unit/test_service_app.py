"""Tests for the standalone evaluation-service FastAPI app."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sentinelrag_evaluation_service.main import app


@pytest.mark.unit
def test_health_and_evaluator_catalog() -> None:
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "sentinelrag-evaluation-service"

    evaluators = client.get("/evaluators")
    assert evaluators.status_code == 200
    assert set(evaluators.json()) == {
        "answer_correctness",
        "citation_accuracy",
        "context_relevance",
        "faithfulness",
    }


@pytest.mark.unit
def test_score_endpoint_runs_selected_evaluator() -> None:
    client = TestClient(app)
    chunk_id = str(uuid4())

    response = client.post(
        "/score",
        json={
            "case": {
                "case_id": str(uuid4()),
                "input_query": "kubernetes rollback",
                "expected_citation_chunk_ids": [chunk_id],
            },
            "context": {
                "answer_text": "Use helm rollback.",
                "retrieved_chunks": [
                    {"chunk_id": chunk_id, "content": "kubernetes rollback uses helm"}
                ],
                "cited_chunk_ids": [chunk_id],
            },
            "evaluators": ["citation_accuracy"],
        },
    )

    assert response.status_code == 200
    assert response.json()["scores"] == {"citation_accuracy": 1.0}
