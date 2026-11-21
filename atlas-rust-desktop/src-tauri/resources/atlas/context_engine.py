"""Context, memory and retrieval helpers for Atlas chat. Standard library only.

What this module does:
- Real context size: asks llama-server (through llama-swap /upstream/<model>/props) for n_ctx.
- Exact prompt count: /upstream/<model>/apply-template + /tokenize, only when the model is already loaded
  (so a count never starts a model or delays a chat by a model load).
- Retrieval filter: keeps only relevant, non-duplicate hits and caps them to a token budget.
- Memory: facts the user asked Atlas to remember, kept in <data>/.atlas/memory.json, added to the system prompt.
- Compaction: asks the local model for a summary of older turns, so a long chat keeps its facts
  when the oldest messages no longer fit.
"""
import http.client
import json
import os
import re
import threading
import time
import uuid
from urllib.parse import quote

CHARS_PER_TOKEN = 3.5          # fallback estimate when no real count is available
_PROPS_TTL = 600               # seconds to cache a model's n_ctx
_props_cache = {}
_props_lock = threading.Lock()
_memory_lock = threading.Lock()

WORD_RE = re.compile(r"[\w'-]{2,}", re.UNICODE)
STOP = set("the a an and or of to in on for with is are was were be been it this that these those you your i me my we our "
           "what which who how why when where do does did can could would should will shall about from into at by as "
           "not no yes if then than so just please tell show give make get".split())


def estimate_tokens(text):
    return int(len(str(text or "")) / CHARS_PER_TOKEN + 0.999)


# ---------------------------------------------------------------- llama-server props / tokenize
def _get_json(host, port, method, path, payload=None, timeout=5.0, headers=None):
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        conn.request(method, path, body=body, headers=headers or {"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read()
        if resp.status != 200:
            return None
        return json.loads(raw.decode("utf-8", "replace"))
    except (OSError, http.client.HTTPException, ValueError):
        return None
    finally:
        conn.close()


def parse_n_ctx(props):
    """n_ctx from a llama-server /props answer, or None. Per-slot size wins when the server splits slots."""
    if not isinstance(props, dict):
        return None
    gen = props.get("default_generation_settings")
    for source in (gen if isinstance(gen, dict) else {}, props):
        value = source.get("n_ctx")
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    return None


def running_models(host, port, headers=None):
    """Names of models llama-swap has loaded right now. None when llama-swap does not say."""
    data = _get_json(host, port, "GET", "/running", timeout=2.0, headers=headers)
    if not isinstance(data, dict) or not isinstance(data.get("running"), list):
        return None
    names = set()
    for row in data["running"]:
        if isinstance(row, dict) and str(row.get("state", "ready")).lower() in ("ready", ""):
            if row.get("model"):
                names.add(str(row["model"]))
    return names


def context_window(host, port, model, timeout=300, headers=None, now=None):
    """Real n_ctx of a model, cached. Starts the model if needed (llama-swap does that on /upstream)."""
    now = time.time() if now is None else now
    key = (host, int(port), str(model))
    with _props_lock:
        hit = _props_cache.get(key)
        if hit and now - hit[1] < _PROPS_TTL:
            return hit[0]
    n_ctx = parse_n_ctx(_get_json(host, port, "GET", "/upstream/" + quote(str(model), safe="") + "/props",
                                  timeout=timeout, headers=headers))
    if n_ctx:
        with _props_lock:
            _props_cache[key] = (n_ctx, now)
    return n_ctx


def exact_prompt_tokens(host, port, model, messages, headers=None, timeout=4.0):
    """Exact prompt token count with the model's own chat template, or None.

    Only runs when the model is already loaded. Image parts are not counted here (the caller adds them)."""
    loaded = running_models(host, port, headers)
    if not loaded or str(model) not in loaded:
        return None
    base = "/upstream/" + quote(str(model), safe="")
    text_only = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        content = m.get("content")
        if isinstance(content, list):
            content = "\n".join(str(p.get("text", "")) for p in content if isinstance(p, dict) and p.get("type") == "text")
        text_only.append({"role": m.get("role", "user"), "content": str(content or "")})
    templ = _get_json(host, port, "POST", base + "/apply-template", {"messages": text_only}, timeout, headers)
    prompt = templ.get("prompt") if isinstance(templ, dict) else None
    if not isinstance(prompt, str):
        return None
    tok = _get_json(host, port, "POST", base + "/tokenize", {"content": prompt, "add_special": True}, timeout, headers)
    tokens = tok.get("tokens") if isinstance(tok, dict) else None
    return len(tokens) if isinstance(tokens, list) else None


# ---------------------------------------------------------------- retrieval
def _words(text):
    return [w for w in (x.lower() for x in WORD_RE.findall(str(text or ""))) if w not in STOP]


def _text_of(content):
    if isinstance(content, list):
        return " ".join(str(p.get("text", "")) for p in content if isinstance(p, dict) and p.get("type") == "text")
    return str(content or "")


def retrieval_query(messages):
    """The search query for a chat turn. A short follow-up ("and the second one?") also uses the previous user turn."""
    users = [_text_of(m.get("content")) for m in messages
             if isinstance(m, dict) and m.get("role") == "user" and _text_of(m.get("content")).strip()]
    if not users:
        return ""
    latest = users[-1].strip()
    if len(_words(latest)) < 6 and len(users) > 1:
        return (users[-2].strip()[-600:] + "\n" + latest).strip()
    return latest[-2000:]


def _overlap(a, b):
    A, B = set(_words(a)), set(_words(b))
    if not A or not B:
        return 0.0
    return len(A & B) / max(1, min(len(A), len(B)))


def select_hits(hits, token_budget, relative=0.35, min_score=0.0, duplicate=0.8):
    """Keep relevant, non-duplicate hits that fit in token_budget (estimated tokens)."""
    rows = [h for h in hits if isinstance(h, dict) and str(h.get("text", "")).strip()]
    if not rows:
        return []
    top = max(float(h.get("score") or 0) for h in rows)
    if top <= 0:
        return []
    kept, used = [], 0
    for h in sorted(rows, key=lambda x: float(x.get("score") or 0), reverse=True):
        score = float(h.get("score") or 0)
        if score < top * relative or score < min_score:
            continue
        if any(_overlap(h["text"], k["text"]) >= duplicate for k in kept):
            continue
        cost = estimate_tokens(h["text"]) + 30
        if used + cost > token_budget:
            continue
        kept.append(h)
        used += cost
    return kept


def knowledge_block(hits):
    if not hits:
        return ""
    head = ("ATLAS RETRIEVED KNOWLEDGE (from the user's local library; use it only when relevant; "
            "cite the source title in square brackets like [Title] when you use it; say so when the library does not cover the question):\n")
    return head + "\n\n".join(
        f"[{h.get('title', 'Source')}] ({h.get('kind', 'source')}, relevance {round(float(h.get('score') or 0), 3)})\n{h.get('text', '')}"
        for h in hits)


# ---------------------------------------------------------------- memory
def memory_path(data_dir):
    return os.path.join(data_dir, ".atlas", "memory.json")


def load_memory(data_dir):
    try:
        with open(memory_path(data_dir), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"enabled": True, "items": []}
    if not isinstance(data, dict):
        return {"enabled": True, "items": []}
    items = [x for x in data.get("items", []) if isinstance(x, dict) and str(x.get("text", "")).strip()]
    return {"enabled": data.get("enabled", True) is not False, "items": items}


def save_memory(data_dir, data):
    path = memory_path(data_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def memory_action(data_dir, payload):
    """add / update / delete / forget / enable. Returns the new memory data."""
    action = str(payload.get("action", "")).lower()
    with _memory_lock:
        data = load_memory(data_dir)
        items = data["items"]
        if action == "add":
            text = " ".join(str(payload.get("text", "")).split())[:1000]
            if not text:
                raise ValueError("Memory text is empty")
            if not any(x["text"].casefold() == text.casefold() for x in items):
                items.append({"id": uuid.uuid4().hex[:12], "text": text, "at": int(time.time() * 1000),
                              "source": str(payload.get("source", "user"))[:40]})
            if len(items) > 500:
                raise ValueError("Memory is full (500 items). Delete some first.")
        elif action == "update":
            row = next((x for x in items if x.get("id") == payload.get("id")), None)
            text = " ".join(str(payload.get("text", "")).split())[:1000]
            if not row or not text:
                raise ValueError("Memory item not found or empty text")
            row["text"] = text
        elif action == "delete":
            data["items"] = [x for x in items if x.get("id") != payload.get("id")]
        elif action == "forget":
            words = set(_words(payload.get("text", "")))
            if not words:
                raise ValueError("Say what to forget")
            keep = [x for x in items if not words <= set(_words(x["text"]))]
            if len(keep) == len(items):
                raise ValueError("No memory matches all of those words")
            data["items"] = keep
        elif action == "enable":
            data["enabled"] = bool(payload.get("enabled"))
        elif action == "clear":
            data["items"] = []
        else:
            raise ValueError("Unknown memory action")
        save_memory(data_dir, data)
        return data


def memory_block(data, query="", token_budget=1500):
    """System-prompt text with the user's saved memories. The most relevant ones first when they do not all fit."""
    if not data or not data.get("enabled", True) or not data.get("items"):
        return "", []
    items = list(data["items"])
    q = set(_words(query))
    if q:
        items.sort(key=lambda x: (-len(q & set(_words(x["text"]))), -int(x.get("at") or 0)))
    else:
        items.sort(key=lambda x: -int(x.get("at") or 0))
    kept, used = [], 0
    for x in items:
        cost = estimate_tokens(x["text"]) + 3
        if used + cost > token_budget:
            continue
        kept.append(x)
        used += cost
    if not kept:
        return "", []
    text = ("ATLAS MEMORY (facts and preferences the user asked you to remember across chats; follow them, "
            "do not repeat them back unless asked):\n" + "\n".join("- " + x["text"] for x in kept))
    return text, kept


# ---------------------------------------------------------------- compaction
COMPACT_PROMPT = (
    "You compress a conversation so it can continue without the full history. Write a summary of at most {words} words. "
    "Keep: the user's goals, decisions made, facts and numbers, names, file paths, code identifiers, open questions, "
    "and what the assistant promised to do next. Drop small talk. Use short bullet points under the headings "
    "Goals, Decisions, Facts, Open items. Write only the summary.")


def compact_messages(previous_summary, messages, max_chars=60000):
    """Build the request messages for a compaction call."""
    lines = []
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        text = re.sub(r"<think>[\s\S]*?(</think>|$)", "", _text_of(m.get("content"))).strip()
        if text:
            lines.append(("USER: " if m["role"] == "user" else "ASSISTANT: ") + text)
    transcript = "\n\n".join(lines)
    if len(transcript) > max_chars:  # keep the start and the end, both carry decisions
        transcript = transcript[: max_chars // 3] + "\n\n[... middle cut ...]\n\n" + transcript[-(2 * max_chars) // 3:]
    body = ("EARLIER SUMMARY:\n" + previous_summary.strip() + "\n\n" if previous_summary and previous_summary.strip() else "")
    body += "CONVERSATION TO ADD TO THE SUMMARY:\n" + transcript
    return body


def compact(host, port, model, previous_summary, messages, words=400, headers=None, timeout=600, max_chars=60000):
    """Ask the model for a summary. Returns (summary, usage dict)."""
    request = {
        "model": model, "stream": False, "temperature": 0.2, "max_tokens": max(256, int(words * 2.2)),
        "messages": [{"role": "system", "content": COMPACT_PROMPT.format(words=words)},
                     {"role": "user", "content": compact_messages(previous_summary, messages, max_chars)}],
    }
    data = _get_json(host, port, "POST", "/v1/chat/completions", request, timeout, headers)
    if not isinstance(data, dict) or not data.get("choices"):
        raise RuntimeError("The model did not return a summary")
    message = data["choices"][0].get("message") or {}
    text = re.sub(r"<think>[\s\S]*?(</think>|$)", "", str(message.get("content") or "")).strip()
    if not text:
        raise RuntimeError("The model returned an empty summary")
    return text, data.get("usage") or {}
