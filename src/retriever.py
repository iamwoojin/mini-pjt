"""사내 규정 문서(data/docs/*.md) RAG. 조항 단위로 나눠 Chroma에 넣고, doc_id는 '파일명#조항번호'로 고정한다."""
from __future__ import annotations

import re
from functools import lru_cache

from langchain_aws import BedrockEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from . import config

PERSIST_DIR = config.BASE_DIR / "chroma_db"
COLLECTION = "policy_docs"


def load_chunks() -> list[Document]:
    docs = []
    for path in sorted(config.DOCS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        for m in re.finditer(r"^## 제(\d+)조 \(([^)]*)\)\n(.*?)(?=^## |\Z)", text, flags=re.M | re.S):
            num, name, body = m.group(1), m.group(2), m.group(3).strip()
            doc_id = f"{path.stem}#{num}"
            docs.append(Document(
                page_content=f"{title} 제{num}조({name}) {body}",
                metadata={"doc_id": doc_id, "title": title},
            ))
    return docs


@lru_cache
def _store() -> Chroma:
    emb = BedrockEmbeddings(model_id=config.EMBED_MODEL, region_name=config.AWS_REGION)
    store = Chroma(collection_name=COLLECTION, embedding_function=emb, persist_directory=str(PERSIST_DIR))
    chunks = load_chunks()
    # 조항 수뿐 아니라 내용이 바뀌어도 다시 만든다 (규정 문구 수정이 검색에 반영되도록)
    stored = store._collection.get(include=["documents"])
    if dict(zip(stored["ids"], stored["documents"])) != {d.metadata["doc_id"]: d.page_content for d in chunks}:
        store.reset_collection()
        store.add_documents(chunks, ids=[d.metadata["doc_id"] for d in chunks])
    return store


def build_index() -> int:
    return _store()._collection.count()


@lru_cache
def _clauses() -> dict[str, str]:
    return {d.metadata["doc_id"]: d.page_content for d in load_chunks()}


def get_clauses(doc_ids: list[str]) -> list[dict]:
    """판정이 정해진 경우 해당 조항을 doc_id로 정확히 가져온다 (임베딩 검색 없이)"""
    clauses = _clauses()
    return [{"doc_id": i, "text": clauses[i]} for i in doc_ids if i in clauses]


def search_policy(query: str, k: int = 3) -> list[dict]:
    """규정 조항 검색 → [{"doc_id": "purchase_rule#7", "text": "..."}]"""
    hits = _store().similarity_search(query, k=k)
    return [{"doc_id": h.metadata["doc_id"], "text": h.page_content} for h in hits]
