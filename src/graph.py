"""LangGraph 흐름 (T15) + HITL interrupt (T16).

    input_guard → parse ─┬─ policy        → END
                         ├─ blocked (G1)   → END
                         ├─ out_of_scope   → END
                         ├─ unrelated      → END
                         └─ verify → approval ─(구매 담당자 + 조치 있음)→ interrupt → 승인/거부 → END

- 판정 함수 · 도구 · 프롬프트는 src/agent.py를 그대로 쓴다. 이 파일은 흐름만 담당한다.
- 승인 대기는 interrupt()로 그래프를 멈추고 체크포인터에 thread_id별로 상태를 저장한다.
  같은 thread_id로 approval을 보내면 Command(resume=...)로 재개한다.
- 권한 확인(승인은 구매 담당자만)은 재개 전에 코드로 먼저 한다 (결정적 게이트).
"""
from __future__ import annotations

import re
import time
import uuid
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from . import agent, retriever, tools
from .agent import ACTION_LABEL, INJECTION_PATTERNS, ParsedQuery, QueryRequest, Trace

SERVICE_GUIDE = ("이 서비스는 공급사 견적의 업체 검증과 견적 검증(가격 적정성)을 돕습니다. "
                 "예: '알파상사(999-99-00001) 견적: 복사용지 A4 80g 2500매 1상자 23,000원(VAT 별도). 진행해도 될까?'")


class State(TypedDict, total=False):
    req: dict
    trace: list[dict]
    contexts: dict[str, dict]
    injected: bool
    parsed: dict
    route: str
    answer: str
    actions: list[dict]
    status: str


def _trace(state: State) -> Trace:
    t = Trace()
    t.steps = list(state.get("trace", []))
    return t


def _req(state: State) -> QueryRequest:
    return QueryRequest(**state["req"])


# ---------- 노드 ----------

def input_guard(state: State) -> dict:
    t, req = _trace(state), _req(state)
    injected = any(re.search(p, req.question, flags=re.I) for p in INJECTION_PATTERNS)
    t.add("input_guard", {"role": req.role}, {"injection_detected": injected})
    return {"trace": t.steps, "injected": injected, "contexts": {}}


def parse(state: State) -> dict:
    t, req = _trace(state), _req(state)
    if req.mode == "policy" and req.role != "supplier":
        t.add("route", {"mode": "policy"}, "policy_question")
        return {"trace": t.steps, "route": "policy"}

    parsed = ParsedQuery(**t.add("parse_query", req.question, agent.parse_query(req.question).model_dump()))
    oos = agent.rule_out_of_scope(req.question)
    if oos and parsed.intent != "other_supplier_info":
        parsed.intent, parsed.out_of_scope_type = "out_of_scope_item", oos
    elif parsed.intent in ("unrelated", "verify") and agent.rule_policy_question(req.question) \
            and not any(q.quoted_price for q in parsed.quotes):
        parsed.intent = "policy_question"
    t.add("route", {"rule_out_of_scope": oos, "rule_policy": agent.rule_policy_question(req.question)}, parsed.intent)

    # 공급사 권한 게이트 (G1)는 의도와 관계없이 먼저 본다
    if req.role == "supplier":
        own = tools.get_supplier_docs(req.supplier_id or "").get("name")
        others = [q for q in parsed.quotes if q.supplier_name and own and own not in q.supplier_name]
        if parsed.intent == "other_supplier_info" or others or re.search(r"몇\s*등|순위|얼마에\s*냈", req.question):
            return {"trace": t.steps, "parsed": parsed.model_dump(), "route": "blocked"}

    route = {"out_of_scope_item": "out_of_scope", "unrelated": "unrelated", "policy_question": "policy"}.get(parsed.intent)
    if route is None:
        route = "verify" if parsed.quotes else "policy"
    return {"trace": t.steps, "parsed": parsed.model_dump(), "route": route}


def policy(state: State) -> dict:
    t, req, ctx = _trace(state), _req(state), dict(state.get("contexts", {}))
    hits = t.add("search_policy", req.question, retriever.search_policy(req.question, k=3))
    ctx.update({h["doc_id"]: h for h in hits})
    joined = "\n".join(f"[{h['doc_id']}] {h['text']}" for h in hits)
    msg = agent._llm().invoke("다음 사내 규정만 근거로 질문에 짧게 답하고, 근거 조항을 [doc_id]로 표시하라. "
                              "규정에 없는 내용은 추측하지 말고 규정에 없다고 답하라. 업체 판정이나 가격 판정은 하지 마라.\n"
                              f"{joined}\n\n질문: {req.question}")
    answer = msg.content if isinstance(msg.content, str) else str(msg.content)
    t.add("policy_answer", [h["doc_id"] for h in hits], answer[:200])
    return {"trace": t.steps, "contexts": ctx, "answer": answer}


def blocked(state: State) -> dict:
    t, req, ctx = _trace(state), _req(state), dict(state.get("contexts", {}))
    agent._cite(t, ctx, "다른 공급사 견적 금액 순위 비공개")
    t.add("guard_G1", req.supplier_id, "blocked")
    return {"trace": t.steps, "contexts": ctx,
            "answer": "다른 공급사의 견적 금액, 순위, 판정 결과는 제공할 수 없습니다. 자사 견적의 검토 상태만 조회할 수 있습니다."}


def out_of_scope(state: State) -> dict:
    t, ctx = _trace(state), dict(state.get("contexts", {}))
    kind = state["parsed"].get("out_of_scope_type") or "범위 밖 품목"
    agent._cite(t, ctx, "용역 공사 맞춤 제작 중고 가격 검증 대상 아님")
    return {"trace": t.steps, "contexts": ctx,
            "answer": f"{kind} 견적은 시장가 검증 대상이 아닙니다. 규격이 정해진 물품만 조달 기준가와 비교할 수 있으며, "
                      f"{kind} 건은 별도의 원가 분석 절차로 검토해 주세요."}


def unrelated(state: State) -> dict:
    return {"answer": SERVICE_GUIDE}


def verify(state: State) -> dict:
    t, req, ctx = _trace(state), _req(state), dict(state.get("contexts", {}))
    parsed = ParsedQuery(**state["parsed"])
    blocks, actions = [], []
    for q in parsed.quotes:
        block, action = agent.verify_quote(q, req, t, ctx)
        blocks.append(block)
        if action:
            actions.append({"type": action, "label": ACTION_LABEL[action], "target": f"{q.supplier_name} / {q.item_text}"})
    if state.get("injected"):
        blocks.append("※ 견적서 안의 지시 문구는 검토 대상 데이터로만 보고 판정에 반영하지 않았습니다.")
    if ctx:
        blocks.append("근거 규정: " + ", ".join(f"[{k}]" for k in ctx))
    return {"trace": t.steps, "contexts": ctx, "answer": "\n\n".join(blocks), "actions": actions}


def approval(state: State) -> dict:
    """구매 담당자에게 조치 승인을 받는다. 임직원·공급사이거나 조치가 없으면 멈추지 않고 끝낸다."""
    actions = state.get("actions") or []
    if not actions or state["req"]["role"] != "buyer":
        return {}
    decision = interrupt({"action": actions[0]})  # 여기서 그래프가 멈추고, 재개되면 승인/거부 값이 들어온다
    t = _trace(state)
    t.add("approval", decision, actions[0])
    verb = "승인" if decision == "approve" else "거부"
    return {"trace": t.steps, "status": "approved" if decision == "approve" else "rejected",
            "answer": f"{actions[0]['label']} 조치가 {verb}되었습니다. (데모: 실제 발송·등록 변경은 하지 않습니다)"}


# ---------- 그래프 ----------

def build_graph():
    g = StateGraph(State)
    for name, fn in [("input_guard", input_guard), ("parse", parse), ("policy", policy), ("blocked", blocked),
                     ("out_of_scope", out_of_scope), ("unrelated", unrelated), ("verify", verify), ("approval", approval)]:
        g.add_node(name, fn)
    g.add_edge(START, "input_guard")
    g.add_edge("input_guard", "parse")
    g.add_conditional_edges("parse", lambda s: s["route"],
                            {r: r for r in ("policy", "blocked", "out_of_scope", "unrelated", "verify")})
    for end_node in ("policy", "blocked", "out_of_scope", "unrelated"):
        g.add_edge(end_node, END)
    g.add_edge("verify", "approval")
    g.add_edge("approval", END)
    return g.compile(checkpointer=MemorySaver())


GRAPH = build_graph()


def _response(values: dict[str, Any], t0: float) -> dict:
    t = Trace()
    t.steps = list(values.get("trace", []))
    t.add("done", None, {"elapsed_sec": round(time.time() - t0, 2)})
    return {"answer": values.get("answer", ""),
            "contexts": [{"doc_id": c["doc_id"], "text": c["text"]} for c in values.get("contexts", {}).values()],
            "trace": t.steps}


def run(req: QueryRequest) -> dict:
    """POST /query 처리 → {"answer","contexts","trace"} (+ 승인 대기 시 status/thread_id/action)"""
    t0 = time.time()

    # HITL 재개: 권한 게이트를 먼저 통과해야 재개한다
    if req.approval and req.thread_id:
        cfg = {"configurable": {"thread_id": req.thread_id}}
        snap = GRAPH.get_state(cfg)
        if not snap.next:
            return {"answer": "승인 대기 중인 조치를 찾을 수 없습니다.", "contexts": [], "trace": []}
        if req.role != "buyer":
            return {"answer": "조치 승인은 구매 담당자만 할 수 있습니다.", "contexts": [], "trace": []}
        values = GRAPH.invoke(Command(resume=req.approval), cfg)
        res = _response(values, t0)
        res["status"] = values.get("status")
        return res

    thread_id = req.thread_id or uuid.uuid4().hex[:12]
    cfg = {"configurable": {"thread_id": thread_id}}
    values = GRAPH.invoke({"req": req.model_dump(), "trace": []}, cfg)
    res = _response(values, t0)
    if "__interrupt__" in values:
        action = values["__interrupt__"][0].value["action"]
        res.update({"status": "pending_approval", "thread_id": thread_id, "action": action})
    return res
