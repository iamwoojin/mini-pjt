"""규정 RAG 진입점 (산출물 구조 `src/retriever.py`). 구현은 src/policy/retriever.py.

사내 규정 문서(data/docs/*.md)를 조항 단위로 나눠 Chroma에 넣고, doc_id는 '파일명#조항번호'로 고정한다.
"""
from .policy.retriever import build_index, get_clauses, load_chunks, search_policy

__all__ = ["build_index", "get_clauses", "load_chunks", "search_policy"]
