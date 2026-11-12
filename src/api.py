"""POST /query 진입점. 실행: uvicorn src.api:app --reload (mini-pjt 폴더에서)"""
from fastapi import FastAPI
from fastapi.responses import FileResponse

from . import agent
from .shared import config

app = FastAPI(title="구매 업체·가격 검증 에이전트")


@app.post("/query")
def query(req: agent.QueryRequest) -> dict:
    return agent.run(req)


@app.get("/")
def index() -> FileResponse:
    """테스트용 웹 화면 (web/index.html)"""
    return FileResponse(config.WEB_DIR / "index.html")
