"""FastAPI app for standalone evaluator smoke checks.

The production eval run control plane lives in the API and the durable work
lives in the Temporal worker. This service exposes the evaluator catalog and a
small scoring endpoint so the workspace package is runnable and does not
collide with the API's top-level ``app`` package.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentinelrag_shared.evaluation import (
    AnswerCorrectnessEvaluator,
    CitationAccuracyEvaluator,
    ContextRelevanceEvaluator,
    EvalCase,
    EvalContext,
    Evaluator,
    FaithfulnessEvaluator,
)


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "sentinelrag-evaluation-service"


class EvalCaseIn(BaseModel):
    case_id: UUID
    input_query: str = Field(..., min_length=1)
    expected_answer: str | None = None
    expected_citation_chunk_ids: list[UUID] = Field(default_factory=list)
    grading_rubric: dict[str, object] = Field(default_factory=dict)


class EvalContextIn(BaseModel):
    answer_text: str
    retrieved_chunks: list[dict[str, object]] = Field(default_factory=list)
    cited_chunk_ids: list[UUID] = Field(default_factory=list)
    cited_quoted_texts: list[str] = Field(default_factory=list)


class ScoreRequest(BaseModel):
    case: EvalCaseIn
    context: EvalContextIn
    evaluators: list[str] | None = None


class ScoreResponse(BaseModel):
    scores: dict[str, float | None]
    reasoning: dict[str, str | None]


def _evaluator_catalog() -> dict[str, Evaluator]:
    evaluators: list[Evaluator] = [
        ContextRelevanceEvaluator(),
        FaithfulnessEvaluator(),
        AnswerCorrectnessEvaluator(),
        CitationAccuracyEvaluator(),
    ]
    return {e.name: e for e in evaluators}


app = FastAPI(
    title="SentinelRAG Evaluation Service",
    version="0.1.0",
    description="Standalone evaluator catalog and scoring endpoint.",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.get("/evaluators", response_model=list[str])
async def list_evaluators() -> list[str]:
    return sorted(_evaluator_catalog())


@app.post("/score", response_model=ScoreResponse)
async def score(payload: ScoreRequest) -> ScoreResponse:
    catalog = _evaluator_catalog()
    names = payload.evaluators or sorted(catalog)
    unknown = sorted(set(names) - set(catalog))
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown evaluator(s): {', '.join(unknown)}",
        )

    case = EvalCase(
        case_id=payload.case.case_id,
        input_query=payload.case.input_query,
        expected_answer=payload.case.expected_answer,
        expected_citation_chunk_ids=payload.case.expected_citation_chunk_ids,
        grading_rubric=payload.case.grading_rubric,
    )
    context = EvalContext(
        answer_text=payload.context.answer_text,
        retrieved_chunks=payload.context.retrieved_chunks,
        cited_chunk_ids=payload.context.cited_chunk_ids,
        cited_quoted_texts=payload.context.cited_quoted_texts,
    )

    scores: dict[str, float | None] = {}
    reasoning: dict[str, str | None] = {}
    for name in names:
        evaluator = catalog[name]
        output = await evaluator.evaluate(case=case, context=context)
        scores[name] = output.score
        reasoning[name] = output.reasoning
    return ScoreResponse(scores=scores, reasoning=reasoning)
