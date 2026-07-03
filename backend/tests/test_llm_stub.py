from pydantic import BaseModel

from app.llm.stub import StubLLM


class Plan(BaseModel):
    upfront_pct: int


def test_stub_text():
    llm = StubLLM(text_response="Namaste")
    assert llm.complete_text("sys", "user") == "Namaste"


def test_stub_structured():
    llm = StubLLM(structured_response=Plan(upfront_pct=30))
    out = llm.complete_structured("sys", "user", Plan)
    assert out.upfront_pct == 30


def test_stub_records_calls():
    llm = StubLLM(text_response="ok")
    llm.complete_text("sys-A", "user-A")
    assert llm.calls[0] == ("text", "sys-A", "user-A")
