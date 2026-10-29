from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from database import initialize_database
from agent import answer_question


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.data_quality = initialize_database()
    yield

app = FastAPI(title="Sales Intelligence Agent API", version="1.0.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500, examples=["Which product generated the highest revenue?"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "sales-intelligence-agent"}


@app.get("/data-quality")
def data_quality():
    return app.state.data_quality


@app.post("/ask")
def ask(request: AskRequest):
    try:
        return answer_question(request.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="The question could not be processed safely. Check the server logs.") from exc
