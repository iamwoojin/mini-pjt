"""사내 데이터 MCP 서버 (fastmcp, stdio).

노출 도구 3개 (모두 가상 데이터):
  - find_supplier(name, b_no)        공급사 기본 정보 조회
  - get_supplier_docs(supplier_id)   제출 서류(설립일 · 상시 인원 · 서류 완비 여부)
  - get_quotes(item_keyword, supplier_id)  접수된 견적 조회 (supplier_id를 주면 그 공급사 견적만)

단독 실행 파일이 아니라 에이전트(src/supplier_data/mcp_client.py)가 자식 프로세스로 띄워 쓴다.
경로는 실행 위치와 무관하게 이 파일 기준으로 잡는다.
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))

from fastmcp import FastMCP  # noqa: E402

from src.supplier_data import store  # noqa: E402

mcp = FastMCP("procurement-company-data")


@mcp.tool()
def find_supplier(name: str = "", b_no: str = "") -> str:
    """등록된 공급사를 이름 또는 사업자등록번호로 찾는다.

    공급사 ID, 이름, 사업자번호, 소재지, 업종이 필요할 때 사용한다. 없으면 null을 반환한다.

    Args:
        name: 공급사 이름 (일부만 있어도 됨)
        b_no: 사업자등록번호 (하이픈 유무 무관)
    """
    return json.dumps(store.find_supplier(name or None, b_no or None), ensure_ascii=False)


@mcp.tool()
def get_supplier_docs(supplier_id: str) -> str:
    """공급사 제출 서류 정보(설립일, 상시 인원, 서류 완비 여부)를 조회한다.

    업체 검증의 '주의' 판정(설립 1년 미만, 인원 3명 미만, 서류 누락)에 사용한다.

    Args:
        supplier_id: 공급사 ID (예: S01)
    """
    return json.dumps(store.get_supplier_docs(supplier_id), ensure_ascii=False)


@mcp.tool()
def get_quotes(item_keyword: str, supplier_id: str = "") -> str:
    """사내에 접수된 견적을 품목 키워드로 조회한다.

    supplier_id를 주면 그 공급사의 견적만 반환한다 (공급사 권한 사용자는 반드시 자사 ID로 조회).

    Args:
        item_keyword: 품목명 일부 (예: 복사용지)
        supplier_id: 공급사 ID로 제한할 때 사용 (선택)
    """
    quotes = store.get_quotes(item_keyword)
    if supplier_id:
        quotes = [q for q in quotes if q.get("supplier_id") == supplier_id]
    return json.dumps(quotes, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(show_banner=False)
