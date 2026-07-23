"""
Hook zapisujacy zdarzenia cyklu zycia Claude Code do pliku JSONL.
Wywolywany przez Claude Code z JSON-em na stdin (patrz settings.json -> hooks).
Nazwa zdarzenia (Stop, PreToolUse, ...) jest przekazywana jako pierwszy argument CLI.
"""
import sys
import os
import json
from datetime import datetime, timezone

EVENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.jsonl")


def main():
    hook_event_name = sys.argv[1] if len(sys.argv) > 1 else "Unknown"

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw": raw}

    tool_response = payload.get("tool_response")
    error_text = payload.get("error")
    if not error_text and isinstance(tool_response, dict):
        error_text = tool_response.get("error") or tool_response.get("stderr") or None

    tool_input = payload.get("tool_input")
    description = None
    if isinstance(tool_input, dict):
        description = (
            tool_input.get("description")
            or tool_input.get("subagent_type")
            or tool_input.get("prompt")
        )
        if isinstance(description, str):
            description = description[:120]

    # korelacja agentow w tle: Agent/Task PostToolUse zwraca {isAsync:true, agentId:...}
    # gdy zlecenie poszlo w tlo (jeszcze nie skonczone!); SubagentStop nioset top-level
    # "agent_id" dokladnie tego samego agenta, ktory faktycznie skonczyl.
    tool_response_is_async = bool(isinstance(tool_response, dict) and tool_response.get("isAsync"))
    tool_response_agent_id = tool_response.get("agentId") if isinstance(tool_response, dict) else None

    last_assistant_message = payload.get("last_assistant_message")
    if isinstance(last_assistant_message, str):
        last_assistant_message = last_assistant_message[:200]

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "hook_event_name": payload.get("hook_event_name", hook_event_name),
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "tool_name": payload.get("tool_name"),
        "tool_use_id": payload.get("tool_use_id"),
        "description": description,
        "message": payload.get("message"),
        "error": error_text[:300] if isinstance(error_text, str) else None,
        "agent_id": payload.get("agent_id"),
        "agent_type": payload.get("agent_type"),
        "tool_response_is_async": tool_response_is_async,
        "tool_response_agent_id": tool_response_agent_id,
        "last_assistant_message": last_assistant_message,
        "raw": payload,
    }

    with open(EVENTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
