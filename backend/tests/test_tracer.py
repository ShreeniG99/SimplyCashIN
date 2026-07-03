from app.obs.tracer import NullTracer, RecordingTracer


def test_null_tracer_no_error():
    NullTracer().trace(agent="conversation", model="stub", prompt="p", response="r", meta={})


def test_recording_tracer_collects():
    t = RecordingTracer()
    t.trace(agent="orchestrator", model="-", prompt="-", response="-", meta={"decision": "act"})
    assert t.events[0]["agent"] == "orchestrator"
    assert t.events[0]["meta"]["decision"] == "act"
