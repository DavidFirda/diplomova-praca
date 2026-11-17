# ============================================================
# AdaptPy - AI asistent: jedna požiadavka študenta -> streamovaná odpoveď (SSE).
#
# Postup (rovnaký pre všetky režimy):
#   1. overenie (zapnutý asistent, rate limit, prístup ku cvičeniu/úlohe, nápovedy),
#   2. uloženie správy študenta do DB,
#   3. RAG: vyhľadanie kúskov prednášok/kníh (cvičenia, úlohy),
#   4. prompt = pravidlá režimu + kontext + história konverzácie + otázka,
#   5. streamovanie odpovede cez strážcu (guard.py) -> udalosti pre klienta,
#   6. uloženie odpovede: model, časy, tokeny, zásahy strážcu a použité zdroje.
#
# Udalosti SSE (data = JSON):
#   meta    {conversation_id, student_message_id, hint_level, task_state}
#   sources {sources:[{rank, label, link}]}   z čoho RAG čerpal (čísla [1], [2] v texte)
#   status  {state: "searching" | "thinking" | "writing"}
#   delta   {text}                 kúsok odpovede (už skontrolovaný strážcom)
#   replace {text}                 celá odpoveď po záverečnej kontrole (ak sa zmenila)
#   done    {message_id, status, hint_level, task_state, allow_insert, guard_hits}
#   error   {error, error_key}
# ============================================================
import json
import re
import time
from datetime import datetime, timezone
from functools import lru_cache

from flask import current_app
from sqlalchemy.exc import IntegrityError

from models import db
from models_ai import AssistantConversation, AssistantMessage, AssistantSource, CourseMaterial
from services import task_agent, task_flow
from services.ai import config as ai_config
from services.ai import context as ctx
from services.ai import guard as guard_mod
from services.ai import llm, prompts
from services.ai.rag import indexer, store
from services.rate_limiter import rate_limited, retry_after
from services.task_log import log_event
from services.task_text import normalize_lang
from services.test_flow import lock_student

MODES = ("dashboard", "exercise", "task")
MAX_MESSAGE = 1500
HISTORY_TURNS = 10
HISTORY_CHARS = 1500
INSERT_INTENT = re.compile(
    r"(vlo[žz]|zap[íi][šs]|nap[íi][šs]\w* (mi )?(to )?do (bunky|editora)|do (bunky|editora)|insert|"
    r"put (it|this|the code) (in|into)|write (it )?(in|into) (the )?(cell|editor))", re.I)

TEXT = {
    "sk": {
        "disabled": "AI asistent je momentálne vypnutý.",
        "rate": "Posielaš príliš veľa správ. Skús to znova o {s} s.",
        "busy": "Asistent je práve vyťažený inými študentmi. Skús to o chvíľu znova.",
        "unavailable": "Asistent teraz nie je dostupný (model neodpovedá). Skús to neskôr.",
        "empty": "Napíš otázku.",
        "closed": "Úloha je už uzavretá.",
        "hint_request": "Daj mi nápovedu.",
        "hint_fallback": "(Jazykový model teraz nie je dostupný, nápovedu som pripravil automaticky.)",
        "empty_answer": "Prepáč, odpoveď sa nepodarilo vytvoriť. Skús otázku položiť inak.",
        "hint_prefix": "**Nápoveda {n}/{max}.** ",
    },
    "en": {
        "disabled": "The AI assistant is currently turned off.",
        "rate": "You are sending too many messages. Try again in {s} s.",
        "busy": "The assistant is busy with other students right now. Try again in a moment.",
        "unavailable": "The assistant is not available right now (the model does not respond). Try again later.",
        "empty": "Type a question.",
        "closed": "The task is already finished.",
        "hint_request": "Give me a hint.",
        "hint_fallback": "(The language model is not available right now, this hint was prepared automatically.)",
        "empty_answer": "Sorry, I couldn't create an answer. Try asking differently.",
        "hint_prefix": "**Hint {n}/{max}.** ",
    },
}


class RequestError(Exception):
    def __init__(self, message, status=400, key=None, extra=None):
        super().__init__(message)
        self.status, self.key, self.extra = status, key, extra or {}


def _t(lang, key, **kw):
    return TEXT.get(lang, TEXT["sk"])[key].format(**kw)


def _now():
    return datetime.now(timezone.utc)


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ------------------------------------------------------------
# Konverzácie
# ------------------------------------------------------------
def context_key(mode, exercise_id=None, assignment_id=None):
    if mode == "exercise":
        return f"exercise:{int(exercise_id)}"
    if mode == "task":
        return f"task:{int(assignment_id)}"
    return "dashboard"


def get_conversation(student_id, mode, exercise_id=None, assignment_id=None, create=True):
    key = context_key(mode, exercise_id, assignment_id)
    conv = AssistantConversation.query.filter_by(student_id=student_id, context_key=key).first()
    if conv is None and create:
        conv = AssistantConversation(student_id=student_id, mode=mode, context_key=key,
                                     exercise_id=exercise_id, assignment_id=assignment_id,
                                     created_at=_now(), updated_at=_now())
        db.session.add(conv)
        try:
            db.session.commit()
        except IntegrityError:          # súbežná požiadavka ju už vytvorila
            db.session.rollback()
            conv = AssistantConversation.query.filter_by(student_id=student_id, context_key=key).first()
    return conv


def _material_visibility():
    return {m.id: m.visible_to_students for m in CourseMaterial.query.with_entities(
        CourseMaterial.id, CourseMaterial.visible_to_students).all()}


def source_view(src, lang, visible):
    """Zdroj pre študenta: popis + odkaz na materiál (ak je sprístupnený)."""
    chunk = {"typ": src.source_type, "nazov": src.title, "poloha": src.location,
             "prednaska": src.lecture_no}
    return {
        "rank": src.rank,
        "label": store.source_label(chunk, lang),
        "link": f"/materialy#m-{src.material_id}" if src.material_id and visible.get(src.material_id) else None,
    }


def history(student_id, mode, exercise_id=None, assignment_id=None, lang="sk", limit=60):
    conv = get_conversation(student_id, mode, exercise_id, assignment_id, create=False)
    if conv is None:
        return []
    rows = (AssistantMessage.query.filter_by(conversation_id=conv.id)
            .order_by(AssistantMessage.id.desc()).limit(limit).all())[::-1]
    ids = [r.id for r in rows if r.role == "assistant"]
    sources = {}
    if ids:
        for s in AssistantSource.query.filter(AssistantSource.message_id.in_(ids)).order_by(
                AssistantSource.message_id, AssistantSource.rank).all():
            sources.setdefault(s.message_id, []).append(s)
    visible = _material_visibility()
    out = []
    for r in rows:
        item = {"id": r.id, "role": r.role, "kind": r.kind, "text": r.text, "hint_level": r.hint_level,
                "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None}
        if r.role == "assistant":
            item["sources"] = [source_view(s, lang, visible) for s in sources.get(r.id, [])]
            item["allow_insert"] = _allow_insert_saved(r)
        if r.role == "event":
            try:
                item["context"] = json.loads(r.context_json or "{}")
            except ValueError:
                item["context"] = {}
        out.append(item)
    return out


def _allow_insert_saved(msg):
    try:
        return bool(json.loads(msg.context_json or "{}").get("allow_insert"))
    except ValueError:
        return False


# ------------------------------------------------------------
# Pomocné: preklad otázky, história pre model
# ------------------------------------------------------------
SK_Q = set("""ako aky aka ake ktory ktora ktore co preco kedy kde ked je su sa si mam ma na v vo z zo s so pre pri
po do od a alebo aj ale nie rozdiel medzi funguje funguju robi znamena urobim spravim pouzit pouzivat""".split())
EN_Q = set("""how what why when where which who is are does do can the a an of in on for to and or not
difference between work works mean use""".split())


def question_lang(text):
    if re.search(r"[áäčďéíĺľňóôŕšťúýž]", text.lower()):
        return "sk"
    words = re.findall(r"[a-z]+", text.lower())
    sk, en = sum(w in SK_Q for w in words), sum(w in EN_Q for w in words)
    return "en" if en > sk else "sk"


@lru_cache(maxsize=256)
def _translate_cached(model, ollama_url, question):
    cfg = ai_config.load()
    text, _ = llm.chat(cfg, [
        {"role": "system", "content": prompts.TRANSLATE.format(glossary=prompts.glossary())},
        {"role": "user", "content": question}], max_tokens=200)
    return text.strip().strip('"')[:500]


def translate_to_slovak(cfg, question):
    try:
        return _translate_cached(cfg.chat_model, cfg.ollama_url, question)
    except llm.LlmUnavailable:
        return None


def model_history(conv_id, before_id):
    rows = (AssistantMessage.query
            .filter(AssistantMessage.conversation_id == conv_id, AssistantMessage.id < before_id,
                    AssistantMessage.role.in_(("student", "assistant")),
                    AssistantMessage.status != "error")
            .order_by(AssistantMessage.id.desc()).limit(HISTORY_TURNS).all())[::-1]
    out = []
    for r in rows:
        text = (r.text or "")[:HISTORY_CHARS]
        if not text.strip():
            continue
        out.append({"role": "user" if r.role == "student" else "assistant", "content": text})
    return out


def materials_block(chunks):
    if not chunks:
        return ""
    return "COURSE MATERIALS (numbered excerpts):\n" + "\n\n".join(
        f"[{i}] ({store.source_label(c)})\n{c['text']}" for i, c in enumerate(chunks, start=1))


# ------------------------------------------------------------
# Príprava požiadavky (v request kontexte, pred streamovaním)
# ------------------------------------------------------------
class Prepared:
    pass


def prepare(student, data):
    """Overí požiadavku, uloží správu študenta a pripraví všetko pre stream. Vyhodí RequestError."""
    cfg = ai_config.load()
    lang = normalize_lang(data.get("lang"))
    mode = data.get("mode")
    if mode not in MODES:
        raise RequestError("Neznámy režim asistenta.", 400)
    action = data.get("action") or "chat"
    if action not in ("chat", "hint") or (action == "hint" and mode != "task"):
        raise RequestError("Neznáma akcia.", 400)
    if not cfg.enabled:
        raise RequestError(_t(lang, "disabled"), 503, "ai.disabled")

    message = (data.get("message") or "").strip()[:MAX_MESSAGE]
    if action == "chat" and not message:
        raise RequestError(_t(lang, "empty"), 400, "ai.empty")

    rl_key = f"ai:{student.id}"
    if rate_limited(rl_key, cfg.rate_limit, cfg.rate_window):
        raise RequestError(_t(lang, "rate", s=retry_after(rl_key, cfg.rate_window)), 429, "ai.rate")

    p = Prepared()
    p.cfg, p.lang, p.mode, p.action, p.message = cfg, lang, mode, action, message
    p.student_id = student.id
    p.hint_level = None
    p.chunks, p.retrieval_info = [], None
    p.allow_insert = False
    p.task_state = None
    p.fallback_hint = None
    p.exercise_id = p.assignment_id = None
    p.extra_queries = []

    if mode == "dashboard":
        text, links, meta = ctx.dashboard_context(student, lang)
        p.context_text, p.meta = text, meta
        p.policy = guard_mod.Policy("dashboard", lang, allowed_links=links)
        p.query = None
        p.system = prompts.system_prompt("dashboard", lang, with_rag=False)

    elif mode == "exercise":
        try:
            p.exercise_id = int(data.get("exercise_id"))
        except (TypeError, ValueError):
            raise RequestError("Chýba ID cvičenia.", 400)
        cell_index = data.get("cell_index")
        cell_index = cell_index if isinstance(cell_index, int) else None
        try:
            c = ctx.exercise_context(student, p.exercise_id, cell_index,
                                     (data.get("cell_code") or "")[:20000] or None,
                                     (data.get("cell_output") or "")[:4000], lang)
        except ctx.ContextError as e:
            raise RequestError(str(e), e.status)
        p.context_text, p.meta = c["text"], c["meta"]
        links = ["/cvicenia", f"/cvicenie?id={p.exercise_id}"] + ctx.material_links()
        p.policy = guard_mod.Policy("exercise", lang, starter=c["starter"],
                                    target_functions=c["target_functions"], allowed_links=links)
        p.query = message
        p.extra_queries = [c["retrieval_hint"]] if c["retrieval_hint"] else []
        p.system = prompts.system_prompt("exercise", lang, with_rag=True)
        p.allow_insert = True

    else:  # task
        try:
            p.assignment_id = int(data.get("assignment_id"))
        except (TypeError, ValueError):
            raise RequestError("Chýba ID úlohy.", 400)
        code = (data.get("code") or "")[:20000]
        lock_student(student.id)
        try:
            c = ctx.task_context(student, p.assignment_id, code, lang)
        except ctx.ContextError as e:
            db.session.rollback()
            raise RequestError(str(e), e.status)
        a = c["assignment"]
        if a.status != "open":
            db.session.rollback()
            raise RequestError(_t(lang, "closed"), 409, "ai.closed")
        if not a.agent_opened:
            a.agent_opened = True
            log_event(student.id, "agent_opened", a, payload={"wrong_attempts": a.wrong_attempts})
        if action == "hint":
            state = task_flow.hint_state(a)
            if not state["hint_available"]:
                db.session.commit()
                raise RequestError(task_flow.hint_block_message(state, lang), 403,
                                   f"ai.hint.{state['hint_reason']}", {"task_state": task_flow.state_fields(a)})
            a.hints_used += 1
            a.last_hint_wrong = a.wrong_attempts
            p.hint_level = a.hints_used
            p.message = _t(lang, "hint_request")
            # záloha bez modelu (pravidlová nápoveda), ak Ollama neodpovie
            p.fallback_hint = task_agent._hint(p.hint_level, c["question"], code,
                                               task_flow.last_attempt(a), lang)
            log_event(student.id, "hint_given", a, payload={
                "hint_level": p.hint_level, "wrong_attempts": a.wrong_attempts,
                "credit_after": task_flow.hint_credit(a.hints_used)})
        log_event(student.id, "agent_message", a,
                  payload={"role": "student", "text": p.message, "intent": action})
        p.task_state = task_flow.state_fields(a)
        p.context_text, p.meta = c["text"], c["meta"]
        p.policy = guard_mod.Policy("task", lang, reference=c["reference"], question_id=c["question"].id,
                                    starter=c["starter"], allowed_links=ctx.material_links())
        p.query = c["retrieval_query"] if action == "hint" else f"{message}\n{c['retrieval_query']}"
        p.system = prompts.hint_prompt(p.hint_level, lang) if action == "hint" else \
            prompts.system_prompt("task", lang, with_rag=True)
        p.allow_insert = action == "chat" and bool(INSERT_INTENT.search(message))
        db.session.commit()

    conv = get_conversation(student.id, mode, p.exercise_id, p.assignment_id)
    p.conversation_id = conv.id
    msg = AssistantMessage(conversation_id=conv.id, role="student",
                           kind="hint" if action == "hint" else "chat", text=p.message,
                           hint_level=p.hint_level, created_at=_now(),
                           context_json=json.dumps(p.meta, ensure_ascii=False, default=str))
    conv.updated_at = _now()
    db.session.add(msg)
    db.session.commit()
    p.student_message_id = msg.id
    return p


# ------------------------------------------------------------
# Streamovanie
# ------------------------------------------------------------
def stream(p):
    """Generátor SSE udalostí (beží v stream_with_context)."""
    yield sse("meta", {"conversation_id": p.conversation_id, "student_message_id": p.student_message_id,
                       "hint_level": p.hint_level, "task_state": p.task_state})
    t0 = time.time()

    # --- RAG ---
    if p.query:
        yield sse("status", {"state": "searching"})
        extra = list(p.extra_queries)
        if p.cfg.translate_query and p.message and question_lang(p.message) == "en":
            sk = translate_to_slovak(p.cfg, p.message)
            if sk:
                extra.append(sk)
        k = p.cfg.rag_k if p.mode == "exercise" else max(3, p.cfg.rag_k - 1)
        p.chunks, p.retrieval_info = indexer.retrieve(p.cfg, p.query, extra, k=k)
    sources_payload = _sources_payload(p)
    if sources_payload:
        yield sse("sources", {"sources": sources_payload})

    # --- prompt ---
    user_parts = [p.context_text]
    mats = materials_block(p.chunks)
    if mats:
        user_parts.append(mats)
    if p.action == "hint":
        user_parts.append(f"Give hint {p.hint_level} of 3 now, following the CURRENT REQUEST rules.")
    else:
        user_parts.append(f"STUDENT'S MESSAGE:\n{p.message}")
    messages = [{"role": "system", "content": p.system}]
    messages += model_history(p.conversation_id, p.student_message_id)
    messages.append({"role": "user", "content": "\n\n".join(user_parts)})
    # počas generovania (aj desiatky sekúnd) nedržať DB spojenie z poolu
    db.session.commit()

    # --- generovanie cez strážcu ---
    g = guard_mod.StreamGuard(p.policy)
    prefix = _t(p.lang, "hint_prefix", n=p.hint_level, max=task_agent.MAX_HINTS) if p.hint_level else ""
    if prefix:
        g.out.append(prefix)
        yield sse("delta", {"text": prefix})
    stats, status, error = {}, "ok", None
    thinking_sent = writing_sent = False
    try:
        with llm.slot(p.cfg):
            for ev in llm.chat_stream(p.cfg, messages):
                if ev["type"] == "thinking":
                    if not thinking_sent:
                        thinking_sent = True
                        yield sse("status", {"state": "thinking"})
                elif ev["type"] == "content":
                    if not writing_sent:
                        writing_sent = True
                        yield sse("status", {"state": "writing"})
                    out = g.feed(ev["text"])
                    if out:
                        yield sse("delta", {"text": out})
                elif ev["type"] == "done":
                    stats = ev["stats"]
        out = g.finish()
        if out:
            yield sse("delta", {"text": out})
    except GeneratorExit:
        # študent zavrel stránku počas písania: uložíme, čo stihol dostať, a končíme
        _save_answer(p, p.policy.check_final(g.text()), "aborted", stats, t0)
        return
    except llm.Busy:
        status, error = "error", _t(p.lang, "busy")
    except llm.LlmUnavailable as e:
        status, error = "error", _t(p.lang, "unavailable")
        current_app.logger.warning("AI asistent: %s", e)
    except Exception:  # noqa: BLE001
        current_app.logger.exception("AI asistent zlyhal")
        status, error = "error", _t(p.lang, "unavailable")

    streamed = g.text()
    final = p.policy.check_final(streamed)
    body = final[len(prefix):].strip() if prefix else final
    if status == "ok" and not body:
        status, error = "error", _t(p.lang, "empty_answer")

    # nápoveda bez modelu -> pravidlová záloha (nápoveda sa už započítala)
    if status == "error" and p.fallback_hint:
        final = prefix + p.fallback_hint + "\n\n" + _t(p.lang, "hint_fallback")
        status, error = "fallback", None

    # najprv uložiť (ak klient medzitým odišiel, odpoveď ostane v DB), potom poslať
    msg_id = _save_answer(p, final if status != "error" else (error or ""), status, stats, t0)
    if status == "error":
        yield sse("error", {"error": error, "message_id": msg_id, "task_state": p.task_state})
        return
    if final != streamed:
        yield sse("replace", {"text": final})
    yield sse("done", {
        "message_id": msg_id, "status": status, "hint_level": p.hint_level,
        "task_state": p.task_state, "allow_insert": p.allow_insert,
        "guard_hits": len(p.policy.hits),
    })


def _sources_payload(p):
    if not p.chunks:
        return []
    visible = _material_visibility()
    out = []
    for i, c in enumerate(p.chunks, start=1):
        mid = c.get("material_id")
        out.append({"rank": i, "label": store.source_label(c, p.lang),
                    "link": f"/materialy#m-{mid}" if mid and visible.get(mid) else None})
    return out


def _save_answer(p, text, status, stats, t0):
    meta = {"retrieval": p.retrieval_info, "allow_insert": p.allow_insert}
    msg = AssistantMessage(
        conversation_id=p.conversation_id, role="assistant",
        kind="hint" if p.hint_level else "chat", text=text, hint_level=p.hint_level, status=status,
        model=p.cfg.chat_model, think=ai_config.think_label(p.cfg.think), prompt_version=prompts.PROMPT_VERSION,
        latency_ms=stats.get("latency_ms") or int((time.time() - t0) * 1000),
        first_token_ms=stats.get("first_token_ms"), tokens_in=stats.get("tokens_in"),
        tokens_out=stats.get("tokens_out"),
        guard_json=json.dumps(p.policy.hits, ensure_ascii=False) if p.policy.hits else None,
        guard_hits=len(p.policy.hits),
        context_json=json.dumps(meta, ensure_ascii=False, default=str), created_at=_now(),
    )
    db.session.add(msg)
    db.session.flush()
    for i, c in enumerate(p.chunks, start=1):
        signals = ", ".join(f"{k} #{v}" for k, v in (c.get("poradie") or {}).items())
        db.session.add(AssistantSource(
            message_id=msg.id, rank=i, material_id=c.get("material_id"), chunk_id=c.get("id", ""),
            lecture_no=c.get("prednaska"),
            source_type=c.get("typ", ""), title=(c.get("nazov") or "")[:255],
            location=(c.get("poloha") or "")[:120], score=c.get("skore"), signals=signals[:255],
            snippet=" ".join((c.get("text") or "").split())[:600]))
    conv = db.session.get(AssistantConversation, p.conversation_id)
    if conv is not None:
        conv.updated_at = _now()
    if p.mode == "task":
        from models_ulohy import TaskAssignment
        a = db.session.get(TaskAssignment, p.assignment_id)
        if a is not None:
            log_event(p.student_id, "agent_message", a, payload={
                "role": "agent", "text": text, "intent": p.action, "hint_level": p.hint_level,
                "status": status, "guard_hits": len(p.policy.hits), "assistant_message_id": msg.id})
    db.session.commit()
    return msg.id


# ------------------------------------------------------------
# Vloženie kódu z odpovede do bunky / editora (po potvrdení študentom)
# ------------------------------------------------------------
def log_insert(student, data):
    try:
        message_id = int(data.get("message_id"))
    except (TypeError, ValueError):
        raise RequestError("Chýba ID správy.", 400)
    msg = db.session.get(AssistantMessage, message_id)
    conv = db.session.get(AssistantConversation, msg.conversation_id) if msg else None
    if msg is None or conv is None or conv.student_id != student.id or msg.role != "assistant":
        raise RequestError("Správa neexistuje.", 404)
    code = (data.get("code") or "")[:20000]
    # vložiť sa smie len kód, ktorý v (skontrolovanej) odpovedi naozaj bol
    if guard_mod.norm_line(code) not in guard_mod.norm_line(msg.text):
        raise RequestError("Kód sa nezhoduje s odpoveďou asistenta.", 400)
    target = str(data.get("target") or "")[:40]
    how = "append" if data.get("how") == "append" else "replace"
    event = AssistantMessage(conversation_id=conv.id, role="event", kind="insert", text=code,
                             created_at=_now(),
                             context_json=json.dumps({"target": target, "how": how, "from_message": msg.id}))
    db.session.add(event)
    if conv.mode == "task" and conv.assignment_id:
        from models_ulohy import TaskAssignment
        a = db.session.get(TaskAssignment, conv.assignment_id)
        if a is not None:
            log_event(student.id, "assistant_code_inserted", a,
                      payload={"target": target, "how": how, "assistant_message_id": msg.id},
                      file_extra={"code": code})
    db.session.commit()
    return {"ok": True, "event_id": event.id}
