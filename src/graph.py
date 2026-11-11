"""LangGraph 흐름: 규칙 라우팅 + Supervisor(하위 에이전트 병렬 배분) + HITL interrupt.

    input_guard → parse ─┬─ policy        → END        (규정 질의 RAG)
                         ├─ blocked (G1)   → END        (공급사 권한 차단)
                         ├─ out_of_scope   → END        (용역·공사·맞춤 제작·중고·렌탈)
                         ├─ unrelated      → END        (서비스 안내)
                         └─ supervisor ──Send──┬─ vendor_agent × 견적 수   (업체 검증)
                                               └─ price_agent  × 견적 수   (가격 검증)
                                                        ↓ (모두 끝나면)
                                                  policy_agent              (규정 검토 · 권고 · 답변)
                                                        ↓
                                                  approval ─(구매 담당자 + 조치)→ interrupt → 승인/거부 → END

- Supervisor는 LLM이 아닌 코드로 작업을 배분한다. 이중 검증 원칙상 모든 견적은 업체·가격 검증을 반드시 거치고,
  두 검증은 서로 독립이라 견적별로 병렬 실행한다(LangGraph Send).
- 판정 함수 · 도구 · 프롬프트는 src/agent.py, 사내 데이터 접근은 src/data.py. 이 파일은 흐름만 담당한다.
- 승인 대기는 interrupt()로 그래프를 멈추고 체크포인터에 thread_id별 상태를 저장한다.
  같은 thread_id로 approval을 보내면 Command(resume=...)로 재개하며, 재개 전에 권한(구매 담당자만)을 코드로 확인한다.
"""
from __future__ import annotations

import operator
import re
import time
import uuid
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send, interrupt

from . import agent, config, data, retriever
from .agent import ACTION_LABEL, INJECTION_PATTERNS, ParsedQuery, QueryRequest, QuoteItem, Trace

SERVICE_GUIDE = ("이 서비스는 공급사 견적의 업체 검증과 견적 검증(가격 적정성)을 돕습니다. "
                 "예: '알파상사(999-99-00001) 견적: 복사용지 A4 80g 2500매 1상자 23,000원(VAT 별도). 진행해도 될까?'")


def _merge(a: dict | None, b: dict | None) -> dict:
    return {**(a or {}), **(b or {})}


class State(TypedDict, total=False):
    req: dict
    trace: Annotated[list[dict], operator.add]          # 노드는 새로 추가한 단계만 반환한다 (병렬 노드 결과를 이어 붙임)
    contexts: Annotated[dict[str, dict], _merge]        # 인용 조항 (doc_id → 조항)
    injected: bool
    parsed: dict
    route: str
    vendor_results: Annotated[list[dict], operator.add]
    price_results: Annotated[list[dict], operator.add]
    answer: str
    actions: list[dict]
    status: str


def _req(state: dict) -> QueryRequest:
    return QueryRequest(**state["req"])


# ---------- 라우팅 노드 ----------

def input_guard(state: State) -> dict:
    t, req = Trace(), _req(state)
    injected = any(re.search(p, req.question, flags=re.I) for p in INJECTION_PATTERNS)
    t.add("input_guard", {"role": req.role}, {"injection_detected": injected})
    return {"trace": t.steps, "injected": injected}


def parse(state: State) -> dict:
    t, req = Trace(), _req(state)
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
        own = data.get_supplier_docs(req.supplier_id or "").get("name")
        others = [q for q in parsed.quotes if q.supplier_name and own and own not in q.supplier_name]
        if parsed.intent == "other_supplier_info" or others or re.search(r"몇\s*등|순위|얼마에\s*냈", req.question):
            return {"trace": t.steps, "parsed": parsed.model_dump(), "route": "blocked"}

    route = {"out_of_scope_item": "out_of_scope", "unrelated": "unrelated", "policy_question": "policy"}.get(parsed.intent)
    if route is None:
        route = "supervisor" if parsed.quotes else "policy"
    return {"trace": t.steps, "parsed": parsed.model_dump(), "route": route}


def policy(state: State) -> dict:
    t, req, ctx = Trace(), _req(state), {}
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
    t, req, ctx = Trace(), _req(state), {}
    agent._cite(t, ctx, "공급사 비공개")
    t.add("guard_G1", req.supplier_id, "blocked")
    return {"trace": t.steps, "contexts": ctx,
            "answer": "다른 공급사의 견적 금액, 순위, 판정 결과는 제공할 수 없습니다. 자사 견적의 검토 상태만 조회할 수 있습니다."}


def out_of_scope(state: State) -> dict:
    t, ctx = Trace(), {}
    kind = state["parsed"].get("out_of_scope_type") or "범위 밖 품목"
    agent._cite(t, ctx, "범위 밖")
    return {"trace": t.steps, "contexts": ctx,
            "answer": f"{kind} 견적은 시장가 검증 대상이 아닙니다. 규격이 정해진 물품만 조달 기준가와 비교할 수 있으며, "
                      f"{kind} 건은 별도의 원가 분석 절차로 검토해 주세요."}


def unrelated(state: State) -> dict:
    return {"answer": SERVICE_GUIDE}


# ---------- Supervisor + 하위 에이전트 ----------

def supervisor(state: State) -> dict:
    """견적별 작업 계획을 세운다. 실제 배분은 dispatch()가 Send로 한다."""
    t = Trace()
    quotes = state["parsed"]["quotes"]
    plan = [{"quote": i, "supplier": q.get("supplier_name"), "item": q.get("item_text"), "agents": ["vendor_agent", "price_agent"]}
            for i, q in enumerate(quotes)]
    t.add("supervisor", {"quotes": len(quotes)}, plan)
    return {"trace": t.steps}


def dispatch(state: State) -> list[Send]:
    payloads = [{"req": state["req"], "idx": i, "quote": q} for i, q in enumerate(state["parsed"]["quotes"])]
    return [Send("vendor_agent", p) for p in payloads] + [Send("price_agent", p) for p in payloads]


def vendor_agent(task: dict) -> dict:
    t, ctx = Trace(), {}
    q, req = QuoteItem(**task["quote"]), _req(task)
    t.add("vendor_agent", {"quote": task["idx"], "supplier": q.supplier_name, "b_no": q.b_no}, "start")
    result = agent.vendor_check(q, req, t, ctx)
    t.add("vendor_agent", {"quote": task["idx"]}, {"verdict": result["verdict"]})
    return {"trace": t.steps, "contexts": ctx, "vendor_results": [{"idx": task["idx"], **result}]}


def price_agent(task: dict) -> dict:
    t, ctx = Trace(), {}
    q, req = QuoteItem(**task["quote"]), _req(task)
    t.add("price_agent", {"quote": task["idx"], "item": q.item_text, "quoted_price": q.quoted_price}, "start")
    result = agent.price_check(q, req, t, ctx)
    t.add("price_agent", {"quote": task["idx"]}, {"verdict": result["verdict"]})
    return {"trace": t.steps, "contexts": ctx, "price_results": [{"idx": task["idx"], **result}]}


def policy_agent(state: State) -> dict:
    """규정 검토 에이전트: 견적별 업체·가격 결과를 모아 권고·조치·근거 조항을 정하고 답변을 만든다."""
    t, req = Trace(), _req(state)
    ctx = dict(state.get("contexts", {}))
    t.add("policy_agent", {"quotes": len(state["parsed"]["quotes"])}, "start")
    vendors = {r["idx"]: r for r in state.get("vendor_results", [])}
    prices = {r["idx"]: r for r in state.get("price_results", [])}
    blocks, actions = [], []
    for i, qd in enumerate(state["parsed"]["quotes"]):
        q = QuoteItem(**qd)
        block, action = agent.policy_review(q, req, vendors[i], prices[i], t, ctx)
        blocks.append(block)
        if action:
            actions.append({"type": action, "label": ACTION_LABEL[action], "target": f"{q.supplier_name} / {q.item_text}"})
    if state.get("injected"):
        agent._cite(t, ctx, "지시문")
        blocks.append("※ 견적서 안의 지시 문구는 검토 대상 데이터로만 보고 판정에 반영하지 않았습니다.")
    if ctx:
        blocks.append("근거 규정: " + ", ".join(f"[{k}]" for k in sorted(ctx)))
    return {"trace": t.steps, "contexts": ctx, "answer": "\n\n".join(blocks), "actions": actions}


def approval(state: State) -> dict:
    """구매 담당자에게 조치 승인을 받는다. 임직원·공급사이거나 조치가 없으면 멈추지 않고 끝낸다."""
    actions = state.get("actions") or []
    if not actions or state["req"]["role"] != "buyer":
        return {}
    decision = interrupt({"action": actions[0]})  # 여기서 그래프가 멈추고, 재개되면 승인/거부 값이 들어온다
    t = Trace()
    t.add("approval", decision, actions[0])
    verb = "승인" if decision == "approve" else "거부"
    return {"trace": t.steps, "status": "approved" if decision == "approve" else "rejected",
            "answer": f"{actions[0]['label']} 조치가 {verb}되었습니다. (데모: 실제 발송·등록 변경은 하지 않습니다)"}


# ---------- 그래프 ----------

def build_graph():
    g = StateGraph(State)
    for name, fn in [("input_guard", input_guard), ("parse", parse), ("policy", policy), ("blocked", blocked),
                     ("out_of_scope", out_of_scope), ("unrelated", unrelated), ("supervisor", supervisor),
                     ("vendor_agent", vendor_agent), ("price_agent", price_agent), ("policy_agent", policy_agent),
                     ("approval", approval)]:
        g.add_node(name, fn)
    g.add_edge(START, "input_guard")
    g.add_edge("input_guard", "parse")
    g.add_conditional_edges("parse", lambda s: s["route"],
                            {r: r for r in ("policy", "blocked", "out_of_scope", "unrelated", "supervisor")})
    for end_node in ("policy", "blocked", "out_of_scope", "unrelated"):
        g.add_edge(end_node, END)
    g.add_conditional_edges("supervisor", dispatch, ["vendor_agent", "price_agent"])
    g.add_edge("vendor_agent", "policy_agent")
    g.add_edge("price_agent", "policy_agent")
    g.add_edge("policy_agent", "approval")
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

    # 입력 길이 가드레일: LLM을 부르기 전에 코드로 거른다
    if len(req.question) > config.MAX_QUESTION_CHARS:
        t = Trace()
        t.add("input_guard", {"role": req.role, "chars": len(req.question)}, {"too_long": True})
        return _response({"trace": t.steps,
                          "answer": f"질문이 너무 깁니다 ({len(req.question):,}자). {config.MAX_QUESTION_CHARS:,}자 이내로 줄이거나 "
                                    "견적을 나눠서 입력해 주세요."}, t0)

    thread_id = req.thread_id or uuid.uuid4().hex[:12]
    cfg = {"configurable": {"thread_id": thread_id}}
    values = GRAPH.invoke({"req": req.model_dump(), "trace": []}, cfg)
    res = _response(values, t0)
    if "__interrupt__" in values:
        action = values["__interrupt__"][0].value["action"]
        res.update({"status": "pending_approval", "thread_id": thread_id, "action": action})
    return res
