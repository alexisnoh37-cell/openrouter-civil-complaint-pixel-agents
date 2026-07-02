import asyncio
from typing import Any, AsyncGenerator, Awaitable, Callable

from app.openrouter_client import openrouter
from app.privacy import detect_personal_info
from app.prompts import (
    CLASSIFICATION_PROMPT,
    DRAFT_PROMPT,
    EXPRESSION_REVIEW_PROMPT,
    JURISDICTION_PROMPT,
    MISSING_QUESTION_REVIEW_PROMPT,
    PRIVACY_REVIEW_PROMPT,
    build_draft_user_prompt,
    build_review_user_prompt,
    complaint_context,
)
from app.schemas import AgentEvent, ComplaintRequest, ProcessResponse
from app.similar_search import search_similar_cases


AGENT_LABELS = {
    "classification": "분류 에이전트",
    "jurisdiction": "소관판단 에이전트",
    "similar_search": "유사민원검색 에이전트",
    "draft": "초안작성 에이전트",
    "expression_review": "표현검토 에이전트",
    "missing_question_review": "누락질문검토 에이전트",
    "privacy_review": "개인정보검토 에이전트",
}


AGENT_MESSAGES = {
    "classification": "민원 유형을 분류하고 있습니다.",
    "jurisdiction": "소관 부서와 이송 필요 여부를 판단하고 있습니다.",
    "similar_search": "기존 유사민원을 검색하고 있습니다.",
    "draft": "보수적 안전형 답변 초안을 작성하고 있습니다.",
    "expression_review": "답변 표현의 적절성을 검토하고 있습니다.",
    "missing_question_review": "추가 확인이 필요한 질문을 검토하고 있습니다.",
    "privacy_review": "개인정보 노출 위험을 검토하고 있습니다.",
}


async def classification_agent(complaint: ComplaintRequest) -> dict[str, Any]:
    return await openrouter.json_chat(
        system_prompt=CLASSIFICATION_PROMPT,
        user_prompt=complaint_context(complaint),
    )


async def jurisdiction_agent(complaint: ComplaintRequest) -> dict[str, Any]:
    return await openrouter.json_chat(
        system_prompt=JURISDICTION_PROMPT,
        user_prompt=complaint_context(complaint),
    )


async def similar_search_agent(complaint: ComplaintRequest) -> dict[str, Any]:
    # TF-IDF is CPU-bound but small; offload so the event loop stays responsive.
    return await asyncio.to_thread(search_similar_cases, complaint.title, complaint.body)


async def draft_agent(complaint: ComplaintRequest, analysis: dict[str, Any]) -> dict[str, Any]:
    return await openrouter.json_chat(
        system_prompt=DRAFT_PROMPT,
        user_prompt=build_draft_user_prompt(complaint, analysis),
    )


async def expression_review_agent(
    complaint: ComplaintRequest, draft_result: dict[str, Any]
) -> dict[str, Any]:
    return await openrouter.json_chat(
        system_prompt=EXPRESSION_REVIEW_PROMPT,
        user_prompt=build_review_user_prompt(complaint, draft_result),
    )


async def missing_question_review_agent(
    complaint: ComplaintRequest, draft_result: dict[str, Any]
) -> dict[str, Any]:
    return await openrouter.json_chat(
        system_prompt=MISSING_QUESTION_REVIEW_PROMPT,
        user_prompt=build_review_user_prompt(complaint, draft_result),
    )


async def privacy_review_agent(
    complaint: ComplaintRequest, draft_result: dict[str, Any]
) -> dict[str, Any]:
    llm_result = await openrouter.json_chat(
        system_prompt=PRIVACY_REVIEW_PROMPT,
        user_prompt=build_review_user_prompt(complaint, draft_result),
    )
    local_findings = detect_personal_info(
        f"{complaint.title}\n{complaint.body}\n{draft_result.get('draft', '')}"
    )
    if local_findings:
        issues = list(llm_result.get("issues") or [])
        issues.append(f"로컬 개인정보 패턴 감지: {', '.join(local_findings)}")
        llm_result["issues"] = issues
        if llm_result.get("status") == "통과":
            llm_result["status"] = "수정필요"
    return llm_result


def event(agent: str, status: str, message: str | None = None, result: dict[str, Any] | None = None) -> AgentEvent:
    return AgentEvent(
        agent=agent,
        label=AGENT_LABELS[agent],
        status=status,  # type: ignore[arg-type]
        message=message,
        result=result,
    )


async def run_agent(
    agent: str,
    call: Callable[[], Awaitable[dict[str, Any]]],
    emit: Callable[[AgentEvent], Awaitable[None]] | None = None,
) -> tuple[str, AgentEvent]:
    if emit:
        await emit(event(agent, "running", AGENT_MESSAGES[agent]))
    try:
        result = await call()
        completed = event(agent, "completed", result=result)
        if emit:
            await emit(completed)
        return agent, completed
    except Exception as exc:
        failed = event(agent, "error", message=str(exc))
        if emit:
            await emit(failed)
        return agent, failed


def decide_final_status(review_results: dict[str, dict[str, Any]]) -> str:
    statuses = [result.get("status") for result in review_results.values()]
    if not statuses or any(status not in {"통과", "수정필요", "위험"} for status in statuses):
        return "담당자 검토 필수"
    if any(status == "위험" for status in statuses):
        return "담당자 검토 필수"
    if any(status == "수정필요" for status in statuses):
        return "수정 후 검토"
    return "초안 사용 가능"


def build_response(complaint: ComplaintRequest, agent_events: dict[str, AgentEvent]) -> ProcessResponse:
    draft_result = (agent_events.get("draft") or AgentEvent(agent="draft", label="", status="error")).result or {}
    review_results = {
        key: (agent_events.get(key) or AgentEvent(agent=key, label="", status="error")).result or {}
        for key in ["expression_review", "missing_question_review", "privacy_review"]
    }
    return ProcessResponse(
        complaint_no=complaint.complaint_no,
        agents={key: value.model_dump() for key, value in agent_events.items()},
        final_status=decide_final_status(review_results),  # type: ignore[arg-type]
        final_draft=str(draft_result.get("draft", "")),
        review_results=review_results,
    )


async def process_complaint(complaint: ComplaintRequest) -> ProcessResponse:
    agent_events: dict[str, AgentEvent] = {}

    first_wave = await asyncio.gather(
        run_agent("classification", lambda: classification_agent(complaint)),
        run_agent("jurisdiction", lambda: jurisdiction_agent(complaint)),
        run_agent("similar_search", lambda: similar_search_agent(complaint)),
    )
    agent_events.update(dict(first_wave))

    analysis = {
        name: agent_events[name].result
        for name in ["classification", "jurisdiction", "similar_search"]
        if agent_events[name].status == "completed"
    }
    _, draft_event = await run_agent("draft", lambda: draft_agent(complaint, analysis))
    agent_events["draft"] = draft_event

    if draft_event.status != "completed":
        for name in ["expression_review", "missing_question_review", "privacy_review"]:
            agent_events[name] = event(name, "error", "초안 작성 실패로 검토를 실행하지 않았습니다.")
        return build_response(complaint, agent_events)

    draft_result = draft_event.result or {}
    review_wave = await asyncio.gather(
        run_agent("expression_review", lambda: expression_review_agent(complaint, draft_result)),
        run_agent("missing_question_review", lambda: missing_question_review_agent(complaint, draft_result)),
        run_agent("privacy_review", lambda: privacy_review_agent(complaint, draft_result)),
    )
    agent_events.update(dict(review_wave))
    return build_response(complaint, agent_events)


async def stream_process_complaint(complaint: ComplaintRequest) -> AsyncGenerator[AgentEvent, None]:
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
    agent_events: dict[str, AgentEvent] = {}

    async def emit(agent_event: AgentEvent) -> None:
        await queue.put(agent_event)

    async def orchestrate() -> None:
        try:
            for name in AGENT_LABELS:
                await emit(event(name, "waiting", "대기중입니다."))

            first_wave = await asyncio.gather(
                run_agent("classification", lambda: classification_agent(complaint), emit),
                run_agent("jurisdiction", lambda: jurisdiction_agent(complaint), emit),
                run_agent("similar_search", lambda: similar_search_agent(complaint), emit),
            )
            agent_events.update(dict(first_wave))

            analysis = {
                name: agent_events[name].result
                for name in ["classification", "jurisdiction", "similar_search"]
                if agent_events[name].status == "completed"
            }
            _, draft_event = await run_agent(
                "draft", lambda: draft_agent(complaint, analysis), emit
            )
            agent_events["draft"] = draft_event

            if draft_event.status == "completed":
                draft_result = draft_event.result or {}
                review_wave = await asyncio.gather(
                    run_agent(
                        "expression_review",
                        lambda: expression_review_agent(complaint, draft_result),
                        emit,
                    ),
                    run_agent(
                        "missing_question_review",
                        lambda: missing_question_review_agent(complaint, draft_result),
                        emit,
                    ),
                    run_agent(
                        "privacy_review",
                        lambda: privacy_review_agent(complaint, draft_result),
                        emit,
                    ),
                )
                agent_events.update(dict(review_wave))
            else:
                for name in ["expression_review", "missing_question_review", "privacy_review"]:
                    failed = event(name, "error", "초안 작성 실패로 검토를 실행하지 않았습니다.")
                    agent_events[name] = failed
                    await emit(failed)

            await queue.put(
                AgentEvent(
                    agent="final",
                    label="최종 결과",
                    status="completed",
                    result=build_response(complaint, agent_events).model_dump(),
                )
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(orchestrate())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        await task
