from fastapi import FastAPI
from pydantic import BaseModel
from agent import answer_query

app = FastAPI()


class QueryRequest(BaseModel):
    message: str
    email: str | None = None
    user_id: str | None = "default"


@app.get("/")
def root():
    return {"status": "RAG + CRM Agent API is running"}


@app.post("/ask")
def ask(request: QueryRequest):
    answer = answer_query(request.message, user_email=request.email, user_id=request.user_id)
    return {"answer": answer}