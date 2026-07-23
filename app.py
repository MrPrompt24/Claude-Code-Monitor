"""
Claude Code Monitor - lekki dashboard Flask.
Czyta events.jsonl (dopisywany przez hooki Claude Code) i wystawia stan sesji
przez /api/status. Strona HTML odpytuje ten endpoint co 1s (polling).
"""
import os
import json
import time
import threading
from collections import Counter
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_FILE = os.path.join(BASE_DIR, "events.jsonl")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
ARCHIVE_DIR = os.path.join(BASE_DIR, "archive")

app = Flask(__name__)
_lock = threading.Lock()
_config_lock = threading.Lock()
_archive_lock = threading.Lock()

DEFAULT_CONFIG = {"stale_after_seconds": 180}

ARCHIVE_AFTER_HOURS = 12       # sesja bez SessionEnd, ale bez zadnej aktywnosci przez tyle godzin -> tez archiwizowana
ARCHIVE_CHECK_INTERVAL = 60    # jak czesto (w sekundach) sprawdzac czy jest co archiwizowac
_last_archive_check = 0.0


def load_config():
    with _config_lock:
        if not os.path.exists(CONFIG_FILE):
            return dict(DEFAULT_CONFIG)
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with _config_lock:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

TOOL_LABELS = {
    "Bash": "terminal",
    "PowerShell": "terminal (PowerShell)",
    "Edit": "edycję pliku",
    "Write": "zapis pliku",
    "Read": "odczyt pliku",
    "Grep": "szukanie w kodzie",
    "Glob": "szukanie plików",
    "TodoWrite": "listę zadań",
    "Agent": "pomocniczego agenta",
    "Task": "pomocniczego agenta",
    "WebFetch": "pobieranie strony WWW",
    "WebSearch": "szukanie w internecie",
    "NotebookEdit": "edycję notatnika",
    "Artifact": "publikację artefaktu",
    "AskUserQuestion": "pytanie do Ciebie",
}

AGENT_TOOL_NAMES = {"Agent", "Task"}
AGENT_TILE_RETENTION_SECONDS = 600  # zakonczone zadania znikaja z kafelkow po 10 minutach


def tool_label(tool_name):
    if not tool_name:
        return "narzędzie"
    return TOOL_LABELS.get(tool_name, tool_name)


def describe_event(ev):
    """Zwraca (ikona, tekst, kategoria) dla pojedynczego zdarzenia - jezyk zrozumialy dla laika."""
    hook_name = ev.get("hook_event_name") or "Unknown"
    tool = ev.get("tool_name")
    error = ev.get("error")

    if hook_name == "SessionStart":
        return "🟢", "Rozpoczęto nową rozmowę", "info"
    if hook_name == "UserPromptSubmit":
        return "💬", "Wysłałeś wiadomość", "working"
    if hook_name == "PreToolUse":
        return "⚙️", f"Zaczyna: {tool_label(tool)}", "working"
    if hook_name == "PostToolUse":
        return "✅", f"Skończył: {tool_label(tool)}", "working"
    if hook_name == "PostToolUseFailure":
        extra = f" ({error})" if error else ""
        return "❌", f"Błąd podczas: {tool_label(tool)}{extra}", "error"
    if hook_name == "Notification":
        return "🔔", "Czeka na Twoją reakcję", "waiting"
    if hook_name == "SubagentStop":
        return "🤖", "Pomocniczy agent skończył zadanie", "info"
    if hook_name == "Stop":
        return "🏁", "Skończył odpowiadać, czeka na wiadomość", "done"
    if hook_name == "SessionEnd":
        return "⚪", "Rozmowa zakończona", "ended"
    if hook_name == "PreCompact":
        return "🗜️", "Porządkuje historię rozmowy", "info"
    return "•", hook_name, "info"


def parse_ts(ts):
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def read_events():
    if not os.path.exists(EVENTS_FILE):
        return []
    events = []
    with _lock:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def archive_session(sid, raw_events):
    """Zapisuje pelna historie sesji do archive/<sid>.json."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    cwd = None
    for ev in raw_events:
        if ev.get("cwd"):
            cwd = ev["cwd"]
    last_ev = raw_events[-1]
    icon, text, category = describe_event(last_ev)
    record = {
        "session_id": sid,
        "cwd": cwd,
        "started_ts": raw_events[0].get("ts"),
        "ended_ts": last_ev.get("ts"),
        "event_count": len(raw_events),
        "last_status_label": text,
        "last_status_category": category,
        "events": raw_events,
    }
    path = os.path.join(ARCHIVE_DIR, f"{sid}.json")
    with _archive_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)


def maybe_rotate_archive():
    """Co ARCHIVE_CHECK_INTERVAL sekund sprawdza, czy sa sesje do zarchiwizowania
    (SessionEnd otrzymany, albo brak aktywnosci od ARCHIVE_AFTER_HOURS godzin) i przenosi
    ich zdarzenia z events.jsonl do archive/<sid>.json, zeby log nie rosl w nieskonczonosc."""
    global _last_archive_check
    now_mono = time.monotonic()
    if now_mono - _last_archive_check < ARCHIVE_CHECK_INTERVAL:
        return
    _last_archive_check = now_mono

    events = read_events()
    if not events:
        return

    by_sid = {}
    for ev in events:
        sid = ev.get("session_id") or "unknown"
        by_sid.setdefault(sid, []).append(ev)

    now = datetime.now(timezone.utc)
    to_archive = set()
    for sid, evs in by_sid.items():
        last_hook = evs[-1].get("hook_event_name")
        last_ts = parse_ts(evs[-1].get("ts"))
        inactive_too_long = last_ts is not None and (now - last_ts).total_seconds() > ARCHIVE_AFTER_HOURS * 3600
        if last_hook == "SessionEnd" or inactive_too_long:
            to_archive.add(sid)

    if not to_archive:
        return

    for sid in to_archive:
        archive_session(sid, by_sid[sid])

    remaining_lines = []
    with _lock:
        for ev in events:
            sid = ev.get("session_id") or "unknown"
            if sid not in to_archive:
                remaining_lines.append(json.dumps(ev, ensure_ascii=False))
        tmp_path = EVENTS_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            for line in remaining_lines:
                f.write(line + "\n")
        os.replace(tmp_path, EVENTS_FILE)


def list_archived_sessions():
    if not os.path.isdir(ARCHIVE_DIR):
        return []
    items = []
    for name in os.listdir(ARCHIVE_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(ARCHIVE_DIR, name), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        items.append({
            "session_id": data.get("session_id"),
            "cwd": data.get("cwd"),
            "started_ts": data.get("started_ts"),
            "ended_ts": data.get("ended_ts"),
            "event_count": data.get("event_count"),
            "last_status_label": data.get("last_status_label"),
            "last_status_category": data.get("last_status_category"),
        })
    items.sort(key=lambda x: x.get("ended_ts") or "", reverse=True)
    return items


def get_archived_session(sid):
    path = os.path.join(ARCHIVE_DIR, f"{sid}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    history = []
    for ev in data.get("events", []):
        icon, text, category = describe_event(ev)
        history.append({"ts": ev.get("ts"), "icon": icon, "text": text, "category": category})
    data["history"] = history
    data.pop("events", None)
    return data


def build_state():
    maybe_rotate_archive()
    cfg = load_config()
    stale_after_seconds = cfg.get("stale_after_seconds", DEFAULT_CONFIG["stale_after_seconds"])
    events = read_events()
    sessions = {}
    # agents_by_id[sid][tool_use_id] = agent dict; agent_order[sid] = lista tool_use_id w kolejnosci startu
    agents_by_id = {}
    agent_order = {}
    # agent_id_to_key[sid][agent_id] = tool_use_id -- korelacja dla agentow w tle (run_in_background)
    agent_id_to_key = {}

    for ev in events:
        sid = ev.get("session_id") or "unknown"
        icon, text, category = describe_event(ev)
        hook_name = ev.get("hook_event_name")
        tool = ev.get("tool_name")

        session = sessions.setdefault(sid, {
            "session_id": sid,
            "cwd": ev.get("cwd"),
            "status_label": text,
            "status_category": category,
            "status_icon": icon,
            "last_tool": None,
            "last_ts": ev.get("ts"),
            "history": [],
            "agents": [],
        })
        agents_by_id.setdefault(sid, {})
        agent_order.setdefault(sid, [])
        agent_id_to_key.setdefault(sid, {})

        session["cwd"] = ev.get("cwd") or session["cwd"]
        session["status_label"] = text
        session["status_category"] = category
        session["status_icon"] = icon
        session["last_ts"] = ev.get("ts")
        if ev.get("tool_name"):
            session["last_tool"] = tool_label(ev.get("tool_name"))

        session["history"].append({
            "ts": ev.get("ts"),
            "icon": icon,
            "text": text,
            "category": category,
        })
        session["history"] = session["history"][-100:]

        # --- sledzenie agentow/subagentow ---
        # Kluczowa korelacja: gdy Agent/Task jest odpalony w tle (run_in_background),
        # PostToolUse wraca natychmiast z {isAsync:true, agentId:...} - to NIE jest
        # zakonczenie zadania, tylko potwierdzenie startu. Prawdziwe zakonczenie
        # sygnalizuje SubagentStop, ktory niesie ten sam "agent_id" - dzieki temu
        # przy wielu agentach naraz wiadomo dokladnie, ktory konkretnie skonczyl
        # (a nie tylko "najstarszy wciaz pracujacy", jak w poprzedniej, przyblizonej wersji).
        if hook_name == "PreToolUse" and tool in AGENT_TOOL_NAMES:
            tuid = ev.get("tool_use_id") or f"noid-{ev.get('ts')}"
            agent = {
                "id": tuid,
                "label": ev.get("description") or "Subagent",
                "status": "pracuje",
                "started_ts": ev.get("ts"),
                "ended_ts": None,
                "result": None,
            }
            agents_by_id[sid][tuid] = agent
            agent_order[sid].append(tuid)
        elif hook_name == "PostToolUse" and tool in AGENT_TOOL_NAMES:
            tuid = ev.get("tool_use_id")
            agent = agents_by_id.get(sid, {}).get(tuid)
            if agent:
                if ev.get("tool_response_is_async") and ev.get("tool_response_agent_id"):
                    # zlecony w tle - dopiero wystartowal, jeszcze nie skonczony
                    agent_id_to_key[sid][ev["tool_response_agent_id"]] = tuid
                elif agent["status"] == "pracuje":
                    # wywolanie synchroniczne (blokujace) - PostToolUse == realne zakonczenie
                    agent["status"] = "zakończony"
                    agent["ended_ts"] = ev.get("ts")
        elif hook_name == "SubagentStop":
            agent_id = ev.get("agent_id")
            tuid = agent_id_to_key.get(sid, {}).get(agent_id) if agent_id else None
            agent = agents_by_id.get(sid, {}).get(tuid) if tuid else None
            if agent is None:
                # brak dopasowania po agent_id (np. stare zdarzenia sprzed tej poprawki) -
                # domykamy najstarszego wciaz "pracujacego" agenta jako bezpiecznik
                for k in agent_order.get(sid, []):
                    candidate = agents_by_id[sid][k]
                    if candidate["status"] == "pracuje":
                        agent = candidate
                        break
            if agent and agent["status"] == "pracuje":
                agent["status"] = "zakończony"
                agent["ended_ts"] = ev.get("ts")
                if ev.get("last_assistant_message"):
                    agent["result"] = ev["last_assistant_message"]

    now = datetime.now(timezone.utc)
    for sid, session in sessions.items():
        ordered = [agents_by_id[sid][tuid] for tuid in agent_order.get(sid, [])]
        visible = []
        for a in reversed(ordered):
            if a["status"] == "pracuje":
                visible.append(a)
                continue
            ended = parse_ts(a["ended_ts"]) if a["ended_ts"] else None
            # zakonczone zadania znikaja z kafelkow po AGENT_TILE_RETENTION_SECONDS,
            # zeby modul nie zaslail sie starymi wpisami - historia i tak zostaje w timeline
            if ended and (now - ended).total_seconds() <= AGENT_TILE_RETENTION_SECONDS:
                visible.append(a)
        session["agents"] = visible[:12]

    for session in sessions.values():
        if session["status_category"] == "working":
            ts = parse_ts(session["last_ts"])
            if ts:
                elapsed = (now - ts).total_seconds()
                if elapsed > stale_after_seconds:
                    minutes = int(elapsed // 60)
                    session["status_category"] = "stale"
                    session["status_icon"] = "⚠️"
                    session["status_label"] = f"Brak aktywności od {minutes} min — może się zawiesił?"

    session_list = sorted(
        sessions.values(), key=lambda s: s["last_ts"] or "", reverse=True
    )
    return session_list


def iter_all_raw_events():
    """Zwraca wszystkie zdarzenia (aktywne z events.jsonl + zarchiwizowane) - do statystyk."""
    for ev in read_events():
        yield ev
    if os.path.isdir(ARCHIVE_DIR):
        for name in os.listdir(ARCHIVE_DIR):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(ARCHIVE_DIR, name), "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            for ev in data.get("events", []):
                yield ev


_transcript_cache = {}  # transcript_path -> {"mtime":, "size":, "day_totals": {date: {...}}}


def parse_transcript_usage(path):
    """Parsuje plik transkryptu Claude Code (JSONL) i sumuje prawdziwe zuzycie
    tokenow (message.usage) per dzien. Cache po mtime+size, zeby nie czytac
    calego pliku od nowa przy kazdym odpytaniu /api/tokens."""
    try:
        stat = os.stat(path)
    except OSError:
        return {}

    cached = _transcript_cache.get(path)
    if cached and cached["mtime"] == stat.st_mtime and cached["size"] == stat.st_size:
        return cached["day_totals"]

    day_totals = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") != "assistant":
                    continue
                msg = d.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not isinstance(usage, dict):
                    continue
                ts = d.get("timestamp")
                if not ts:
                    continue
                date_str = ts[:10]
                bucket = day_totals.setdefault(date_str, {
                    "input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "messages": 0,
                })
                bucket["input"] += usage.get("input_tokens") or 0
                bucket["output"] += usage.get("output_tokens") or 0
                bucket["cache_creation"] += usage.get("cache_creation_input_tokens") or 0
                bucket["cache_read"] += usage.get("cache_read_input_tokens") or 0
                bucket["messages"] += 1
    except OSError:
        return {}

    _transcript_cache[path] = {"mtime": stat.st_mtime, "size": stat.st_size, "day_totals": day_totals}
    return day_totals


def compute_token_stats():
    transcript_paths = set()
    for ev in iter_all_raw_events():
        raw = ev.get("raw")
        if isinstance(raw, dict):
            tp = raw.get("transcript_path")
            if tp:
                transcript_paths.add(tp)

    combined_days = {}
    for path in transcript_paths:
        for date_str, bucket in parse_transcript_usage(path).items():
            agg = combined_days.setdefault(date_str, {
                "input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "messages": 0,
            })
            for k in agg:
                agg[k] += bucket[k]

    def with_total(bucket):
        b = dict(bucket)
        b["total"] = b["input"] + b["output"] + b["cache_creation"] + b["cache_read"]
        return b

    today = datetime.now(timezone.utc).date()
    days_series = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        ds = d.isoformat()
        bucket = combined_days.get(ds, {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "messages": 0})
        entry = with_total(bucket)
        entry["date"] = ds
        entry["label"] = d.strftime("%d.%m")
        days_series.append(entry)

    def sum_dates(dates):
        agg = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "messages": 0}
        for ds in dates:
            bucket = combined_days.get(ds)
            if bucket:
                for k in agg:
                    agg[k] += bucket[k]
        return with_total(agg)

    week_start = today - timedelta(days=today.weekday())
    week_dates = [(week_start + timedelta(days=i)).isoformat() for i in range((today - week_start).days + 1)]

    return {
        "today": sum_dates([today.isoformat()]),
        "this_week": sum_dates(week_dates),
        "days_series": days_series,
    }


def compute_stats():
    tool_counts = Counter()
    error_count = 0
    day_event_counts = Counter()
    day_message_counts = Counter()
    session_span = {}  # sid -> [first_ts, last_ts]

    for ev in iter_all_raw_events():
        sid = ev.get("session_id") or "unknown"
        ts = ev.get("ts")
        hook_name = ev.get("hook_event_name")
        tool = ev.get("tool_name")

        if ts:
            span = session_span.setdefault(sid, [ts, ts])
            if ts < span[0]:
                span[0] = ts
            if ts > span[1]:
                span[1] = ts
            date_str = ts[:10]
            day_event_counts[date_str] += 1
            if hook_name == "UserPromptSubmit":
                day_message_counts[date_str] += 1

        if hook_name == "PreToolUse" and tool:
            tool_counts[tool_label(tool)] += 1
        if hook_name == "PostToolUseFailure":
            error_count += 1

    durations_minutes = []
    for sid, (first_ts, last_ts) in session_span.items():
        t1, t2 = parse_ts(first_ts), parse_ts(last_ts)
        if t1 and t2:
            minutes = (t2 - t1).total_seconds() / 60
            if minutes > 0.05:
                durations_minutes.append(minutes)

    avg_minutes = round(sum(durations_minutes) / len(durations_minutes), 1) if durations_minutes else 0

    today = datetime.now(timezone.utc).date()
    days_series = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        ds = d.isoformat()
        days_series.append({
            "date": ds,
            "label": d.strftime("%d.%m"),
            "events": day_event_counts.get(ds, 0),
            "messages": day_message_counts.get(ds, 0),
        })

    week_start = today - timedelta(days=today.weekday())
    messages_this_week = sum(v for k, v in day_message_counts.items() if k >= week_start.isoformat())
    messages_today = day_message_counts.get(today.isoformat(), 0)

    return {
        "tool_usage": [{"tool": k, "count": v} for k, v in tool_counts.most_common(10)],
        "error_count": error_count,
        "total_sessions": len(session_span),
        "avg_session_minutes": avg_minutes,
        "days_series": days_series,
        "messages_today": messages_today,
        "messages_this_week": messages_this_week,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify({"sessions": build_state(), "server_time": datetime.now(timezone.utc).isoformat()})


@app.route("/api/config", methods=["GET"])
def api_config_get():
    return jsonify(load_config())


@app.route("/api/config", methods=["POST"])
def api_config_set():
    cfg = load_config()
    data = request.get_json(silent=True) or {}
    if "stale_after_seconds" in data:
        try:
            value = int(data["stale_after_seconds"])
            if 30 <= value <= 3600:
                cfg["stale_after_seconds"] = value
        except (TypeError, ValueError):
            pass
    save_config(cfg)
    return jsonify(cfg)


@app.route("/api/archive")
def api_archive_list():
    return jsonify({"sessions": list_archived_sessions()})


@app.route("/api/archive/<session_id>")
def api_archive_detail(session_id):
    data = get_archived_session(session_id)
    if data is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(data)


@app.route("/api/stats")
def api_stats():
    return jsonify(compute_stats())


@app.route("/api/tokens")
def api_tokens():
    return jsonify(compute_token_stats())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5151, debug=False)
