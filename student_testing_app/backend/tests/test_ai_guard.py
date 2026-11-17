"""Testy strážcu AI asistenta (services/ai/guard.py) - bez DB, bez modelu, bez sandboxu.

Spustenie (v priečinku backend/):  python -m pytest tests -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from services.ai import guard  # noqa: E402

REFERENCE = """def sum_to(n):
    total = 0
    for i in range(1, n + 1):
        total += i
    return total

print(sum_to(10))"""


@pytest.fixture(autouse=True)
def fake_runner(monkeypatch):
    """Sandbox nahradíme lokálnym exec-om (len pre testy)."""
    import contextlib
    import io

    def run(code):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(code, {})
        except Exception as e:  # noqa: BLE001
            return "", str(e)
        return buf.getvalue().strip(), None

    monkeypatch.setattr(guard, "capture_output", run)
    monkeypatch.setattr(guard, "expected_output", lambda qid, sol: run(sol))


def task_policy(**kw):
    return guard.Policy("task", "sk", reference=REFERENCE, question_id=1,
                        starter="def sum_to(n):\n    pass\n\nprint(sum_to(10))", **kw)


def stream(policy, text, size=5):
    g = guard.StreamGuard(policy)
    out = [g.feed(text[i:i + size]) for i in range(0, len(text), size)]
    out.append(g.finish())
    return "".join(out), policy.check_final(g.text())


# ------------------------------------------------------------ úlohy
def test_copied_solution_becomes_skeleton():
    p = task_policy()
    streamed, final = stream(p, f"Tu je riešenie:\n```python\n{REFERENCE}\n```\nHotovo.")
    assert "total += i" not in streamed and "total += i" not in final
    assert "for ...:" in streamed or "..." in streamed
    assert p.hits and p.hits[0]["rule"] == "similar_to_solution"


def test_rewritten_solution_caught_by_running():
    p = task_policy()
    code = "s = 0\nfor k in range(11):\n    s = s + k\nprint(s)"
    streamed, _ = stream(p, f"Skús:\n```python\n{code}\n```\n")
    assert "s = s + k" not in streamed
    assert any(h["rule"] == "solves_task" for h in p.hits)


def test_skeleton_with_placeholders_passes():
    p = task_policy()
    sk = "def sum_to(n):\n    total = ...\n    for ... in ...:\n        ...\n    return ..."
    streamed, _ = stream(p, f"Kostra:\n```python\n{sk}\n```\n")
    assert sk in streamed
    assert not p.hits


def test_unrelated_example_passes():
    p = task_policy()
    code = "mena = ['Ana', 'Bob']\nfor m in mena:\n    print(m)"
    streamed, _ = stream(p, f"Príklad cyklu:\n```python\n{code}\n```\n")
    assert "print(m)" in streamed and not p.hits


def test_solution_line_outside_code_block_removed():
    p = task_policy()
    streamed, _ = stream(p, "Napíš tam:\n    for i in range(1, n + 1):\na hotovo.\n")
    assert "range(1, n + 1)" not in streamed
    assert any(h["rule"] == "solution_line_in_text" for h in p.hits)


def test_unclosed_block_is_checked_too():
    p = task_policy()
    streamed, _ = stream(p, f"```python\n{REFERENCE}")
    assert "total += i" not in streamed


# ------------------------------------------------------------ cvičenia
def test_exercise_full_function_becomes_skeleton():
    p = guard.Policy("exercise", "sk", target_functions={"is_prime"})
    code = ("def is_prime(number):\n    if number < 2:\n        return False\n"
            "    for d in range(2, number):\n        if number % d == 0:\n            return False\n    return True")
    streamed, _ = stream(p, f"```python\n{code}\n```\n")
    assert "number % d == 0" not in streamed
    assert "def is_prime(number):" in streamed
    assert p.hits[0]["rule"] == "full_exercise_solution"


def test_exercise_skeleton_and_other_examples_pass():
    p = guard.Policy("exercise", "sk", target_functions={"is_prime"})
    text = ("```python\ndef is_prime(number):\n    # ...\n    pass\n```\n"
            "```python\ndef pozdrav(meno):\n    text = 'Ahoj ' + meno\n    return text\n```\n")
    streamed, _ = stream(p, text)
    assert "return text" in streamed and not p.hits


# ------------------------------------------------------------ dashboard + odkazy
def test_dashboard_blocks_code_links_and_internals():
    p = guard.Policy("dashboard", "sk", allowed_links=["/cvicenia", "/cvicenie?id=3"])
    text = ("Choď na [Cvičenia](/cvicenia) alebo [cvičenie 3](/cvicenie?id=3).\n"
            "Admin nájdeš na [tu](/admin-users) a http://evil.example.com.\n"
            "Aplikácia beží na Flask a Postgres.\n"
            "```python\nprint('x')\n```\n")
    streamed, _ = stream(p, text)
    assert "[Cvičenia](/cvicenia)" in streamed and "(/cvicenie?id=3)" in streamed
    assert "/admin-users" not in streamed and "evil.example.com" not in streamed
    assert "Flask" not in streamed and "print('x')" not in streamed
    rules = {h["rule"] for h in p.hits}
    assert {"link_not_allowed", "dashboard_forbidden", "code_in_dashboard"} <= rules


def test_prose_streams_before_line_ends():
    """Bežný text ide k študentovi hneď (plynulé písanie), nečaká na koniec riadku."""
    p = guard.Policy("exercise", "sk")
    g = guard.StreamGuard(p)
    assert g.feed("Premenná je ") == "Premenná je "
    assert g.feed("miesto v pamäti") == "miesto v pamäti"
    assert g.feed(".\n") == ".\n"


def test_skeletonize_keeps_structure():
    sk = guard.skeletonize(REFERENCE)
    assert sk.splitlines()[0] == "def sum_to(n):"
    assert "for ...:" in sk and "return ..." in sk and "total += i" not in sk


def test_short_code_line_in_prose_not_leaked_while_streaming():
    """Riadok riešenia v texte (bez bloku) neprekĺzne ani pri streamovaní po kúskoch."""
    p = task_policy()
    for size in (2, 3, 7, 50):
        p = task_policy()
        streamed, final = stream(p, "A ešte raz riadok:\ntotal = 0\na hotovo.\n", size=size)
        assert "total = 0" not in streamed, size
        assert "total = 0" not in final


def test_long_prose_streams_in_task_mode():
    p = task_policy()
    g = guard.StreamGuard(p)
    assert g.feed("Pozri sa na to, ako sa mení ") == "Pozri sa na to, ako sa mení "
    assert g.feed("hodnota") == "hodnota"
