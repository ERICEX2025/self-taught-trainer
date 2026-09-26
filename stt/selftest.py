"""Offline checks the healer must pass before any code change is kept. No network, no model calls.

Run: python -m stt.selftest   (exit code 0 = pass)
"""
import sys


def run() -> list[str]:
    failures = []

    def check(name, fn):
        try:
            if fn() is False:
                failures.append(name)
        except Exception as e:
            failures.append(f"{name}: {type(e).__name__}: {e}")

    from stt import adapter, coach, evaluate, harness, loop, tools, tracing  # noqa: F401  every module still imports

    legal = {"move:thunderbolt": "", "move:thunderwave": "", "switch:starmie": ""}
    check("resolve exact", lambda: harness.resolve_action("move:thunderbolt", legal) == "move:thunderbolt")
    check("resolve missing prefix", lambda: harness.resolve_action("Thunder Wave", legal) == "move:thunderwave")
    check("resolve switch", lambda: harness.resolve_action("switch: Starmie", legal) == "switch:starmie")
    check("resolve illegal", lambda: harness.resolve_action("move:surf", legal) is None)

    cfg = harness.v1()
    check("v1 has editable fields", lambda: all(k in cfg for k in harness.EDITABLE))
    check("guardrails intact", lambda: cfg["guardrails"] == harness.GUARDRAILS and any("action:" in g for g in harness.GUARDRAILS))
    check("sample tool compiles", lambda: tools.compile_tool("def tool(s):\n    return 'ok'\n")[0] is not None)
    check("banned tool rejected", lambda: tools.compile_tool("import os\ndef tool(s):\n    return ''\n")[0] is None)
    check("crashing tool rejected", lambda: tools.compile_tool("def tool(s):\n    return 1/0\n")[0] is None)
    check("coach parses candidates", lambda: len(coach.parse_candidates('{"candidates": [{"kind": "add_rule", "value": "x"}]}')) == 1)
    return failures


if __name__ == "__main__":
    bad = run()
    print("selftest:", "PASS" if not bad else "FAIL\n  " + "\n  ".join(bad))
    sys.exit(1 if bad else 0)
