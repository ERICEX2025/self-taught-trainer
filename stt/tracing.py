"""Langfuse tracing: one trace per battle (every turn is a generation with the battle text in and the
player's reason + move out), plus one trace per coach decision. Sessions = runs.

Does nothing unless LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set, and never raises into the loop.
Errors go to Sentry/GlitchTip when SENTRY_DSN is set (poke-env logs player crashes at ERROR level, which Sentry
picks up). The healer (stt/heal.py) reads both back through MCP.
"""
import os

if os.environ.get("SENTRY_DSN"):
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=0, environment=os.environ.get("STT_ENV", "hackathon"))
    except Exception:
        pass

_lf = None


def client():
    global _lf
    if _lf is None and os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse import get_client
            _lf = get_client()
        except Exception:
            _lf = False
    return _lf or None


def battle_trace_id(battle_tag: str, version: str) -> str | None:
    lf = client()
    return lf.create_trace_id(seed=f"{version}:{battle_tag}") if lf else None


def start_generation(name: str, *, trace_id: str | None, session: str, tags: list[str], model: str, input, metadata: dict):
    """Start a generation observation; returns a handle or None. Never raises."""
    lf = client()
    if not lf:
        return None
    try:
        from langfuse import propagate_attributes
        with propagate_attributes(session_id=session, tags=tags, trace_name=name.split(" · ")[0]):
            return lf.start_observation(as_type="generation", name=name, model=model, input=input, metadata=metadata,
                                        trace_context={"trace_id": trace_id} if trace_id else None)
    except Exception:
        return None


def end_generation(obs, *, output=None, usage: dict | None = None, metadata: dict | None = None):
    if obs is None:
        return
    try:
        obs.update(output=output, usage_details=usage or None, metadata=metadata)
        obs.end()
    except Exception:
        pass


def event(name: str, *, trace_id: str | None, session: str, tags: list[str], output, metadata: dict):
    lf = client()
    if not lf:
        return
    try:
        from langfuse import propagate_attributes
        with propagate_attributes(session_id=session, tags=tags):
            with lf.start_as_current_observation(as_type="span", name=name, output=output, metadata=metadata,
                                                 trace_context={"trace_id": trace_id} if trace_id else None):
                pass
    except Exception:
        pass


def flush():
    lf = client()
    if lf:
        try:
            lf.flush()
        except Exception:
            pass
