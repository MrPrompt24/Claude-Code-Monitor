# Claude Code Monitor

**Wersja 1.0 / Version 1.0** · stworzone przez / created by [MrPrompt](https://mrprompt.eu/)

🇵🇱 [Polski](#polski) &nbsp;|&nbsp; 🇬🇧 [English](#english)

---

## Polski

[⬆ Wróć do wyboru języka](#claude-code-monitor) &nbsp;|&nbsp; [🇬🇧 Przejdź do wersji angielskiej](#english)

Lokalny dashboard w przeglądarce, który w czasie rzeczywistym pokazuje, co robi
[Claude Code](https://www.anthropic.com/claude-code): czy właśnie pracuje, czy
czeka na Twoją reakcję, czy skończył, czy któreś narzędzie zwróciło błąd, czy
uruchomił subagentów - bez konieczności patrzenia w okno terminala/IDE.

Do tego: ikona statusu w zasobniku systemowym, archiwum zakończonych rozmów,
statystyki użycia narzędzi i realne zużycie tokenów - wszystko liczone lokalnie,
na Twoim komputerze, z danych, które Claude Code i tak już generuje.

### Jak to wygląda

Dashboard to zwykła strona w przeglądarce (lub osobne okienko), z czterema
zakładkami:

- **Aktywne sesje** - karta na każdą trwającą rozmowę: kolorowy status, ostatnio
  użyte narzędzie, kafelki uruchomionych agentów, skrócona (rozwijalna) historia zdarzeń.
- **Archiwum rozmów** - lista zakończonych sesji z podglądem pełnej historii po kliknięciu.
- **Statystyki** - najczęściej używane narzędzia, liczba błędów, aktywność dzienna z ostatnich 14 dni.
- **Tokeny** - realne zużycie tokenów (input/output/cache) parsowane z transkryptów Claude Code.

### Dlaczego to działa

Claude Code ma wbudowany mechanizm **hooków** - komend uruchamianych automatycznie
przy zdarzeniach cyklu życia sesji (start, koniec, użycie narzędzia, błąd, itd.).
Ten projekt podpina lekki skrypt Python pod te hooki, który dopisuje zdarzenia do
pliku, a serwer Flask je czyta, agreguje i wystawia jako dashboard. Hooki są
**jednokierunkowe** (Claude Code → skrypt) - to narzędzie tylko podgląda, nigdy
nie steruje sesją Claude Code.

### Wymagania

- **Windows** (obecna wersja korzysta z `pystray`, Microsoft Edge w trybie `--app`
  i skryptów `.bat`/`.vbs` - na Linux/macOS wymagałoby to adaptacji tych elementów).
- **Python 3.10+** z `pip` (sprawdź: `python --version` albo `py -3 --version`).
- **Claude Code** (CLI lub rozszerzenie VS Code) z uprawnieniem do edycji
  własnego pliku `settings.json`.
- Przeglądarka oparta na Chromium (Edge, Chrome) - do trybu okienkowego bez
  paska adresu; w innym wypadku dashboard i tak działa jako zwykła karta w
  dowolnej przeglądarce pod `http://127.0.0.1:5151/`.

### Instalacja

#### Opcja A: przez Claude Code (zalecane)

To repozytorium zawiera gotowy **Skill** (`.claude/skills/install-monitor/`),
który Claude Code może wykonać sam - wykrywa Twojego Pythona, instaluje
zależności, dopisuje hooki do Twojego **własnego** `settings.json` (z
poprawnymi, wykrytymi u Ciebie ścieżkami) i uruchamia aplikację.

1. Sklonuj to repozytorium i **otwórz Claude Code dokładnie w tym folderze**.
2. Napisz do Claude Code: `zainstaluj monitor` (albo dowolne podobne polecenie).
3. Claude Code przeprowadzi Cię przez resztę - w tym przez pytanie, czy hooki
   mają obserwować wszystkie sesje na komputerze, czy tylko wybrany projekt.

#### Opcja B: ręcznie

```bash
git clone <adres-tego-repo>
cd ClaudeCodeMonitor
pip install -r requirements.txt
```

Znajdź pełną ścieżkę swojego Pythona (`python -c "import sys; print(sys.executable)"`)
i dopisz hooki do swojego `~/.claude/settings.json` (Windows:
`%USERPROFILE%\.claude\settings.json`), scalając z istniejącą zawartością:

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"SessionStart\"" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"UserPromptSubmit\"" }] }],
    "PreToolUse": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"PreToolUse\"" }] }],
    "PostToolUse": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"PostToolUse\"" }] }],
    "PostToolUseFailure": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"PostToolUseFailure\"" }] }],
    "Notification": [{ "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"Notification\"" }] }],
    "SubagentStop": [{ "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"SubagentStop\"" }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"Stop\"" }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"SessionEnd\"" }] }],
    "PreCompact": [{ "hooks": [{ "type": "command", "command": "\"<ŚCIEŻKA_DO_PYTHON>\" \"<ŚCIEŻKA_DO_REPO>\\hook_logger.py\" \"PreCompact\"" }] }]
  }
}
```

Podmień `<ŚCIEŻKA_DO_PYTHON>` i `<ŚCIEŻKA_DO_REPO>` na swoje rzeczywiste ścieżki.
Zweryfikuj, że plik jest poprawnym JSON-em (np. wklejając do dowolnego walidatora
JSON) - błąd składni cicho wyłączy wszystkie Twoje dotychczasowe ustawienia
Claude Code, nie tylko hooki.

### Uruchamianie

Najwygodniej: dwuklik na `start_monitor.vbs` (uruchamia bez migającego okna
konsoli, pokazuje ikonę w zasobniku systemowym). Alternatywnie `start_monitor.bat`
(z widoczną konsolą - przydatne przy diagnozowaniu problemów), albo ręcznie:

```bash
python app.py
```

i wejście na `http://127.0.0.1:5151/` w przeglądarce.

### Konfiguracja

Panel ustawień (ikona ⚙️ w headerze dashboardu) pozwala zmienić próg, po którym
status "pracuje" zamienia się w ostrzeżenie "może się zawiesił" (domyślnie 3 minuty),
oraz włączyć/wyłączyć dźwięk powiadomień. Powiadomienia systemowe wymagają
jednorazowego kliknięcia "Zezwól na powiadomienia" w tym samym panelu.

### Architektura

```
Claude Code  ──hooki──▶  hook_logger.py  ──▶  events.jsonl / archive/*.json
                                                        │
                                                        ▼
                                                    app.py (Flask)
                                                        │  REST API
                                                        ▼
                                            dashboard w przeglądarce
                                                        ▲
                                                        │
                                        run.py - ikona w zasobniku systemowym
```

Pełny opis wewnętrznej architektury, wszystkich endpointów API i decyzji
projektowych - patrz [`DEVELOPMENT.md`](DEVELOPMENT.md).

### Znane ograniczenia

- Hooki są jednokierunkowe - nie da się sterować Claude Code (np. zmieniać modelu) z poziomu tego dashboardu.
- Obecna wersja jest zorientowana na Windows (tray icon, Edge `--app`, `.bat`/`.vbs`).
- Nie pokazuje autentycznych limitów konta Claude Code (np. tygodniowego limitu planu) - te dane istnieją wyłącznie po stronie Anthropic, nie lokalnie. Zakładka "Tokeny" pokazuje wyłącznie realne zużycie, nigdy pozostały limit.
- Brak filtrowania/szukania w kartach, archiwum i statystykach.

### Rozwój i zgłaszanie błędów

Issues i pull requesty mile widziane. Przy większych zmianach warto najpierw
otworzyć issue z opisem propozycji.

### Licencja

[MIT](LICENSE) © 2026 [MrPrompt](https://mrprompt.eu/)

---

## English

[⬆ Back to language picker](#claude-code-monitor) &nbsp;|&nbsp; [🇵🇱 Go to the Polish version](#polski)

A local, browser-based dashboard that shows in real time what
[Claude Code](https://www.anthropic.com/claude-code) is doing: whether it's
currently working, waiting for your input, finished, whether a tool call
failed, or whether it spawned subagents - without having to keep an eye on a
terminal/IDE window.

On top of that: a status icon in the system tray, an archive of finished
conversations, tool-usage statistics, and real token consumption - all
computed locally, on your own machine, from data Claude Code already produces.

### What it looks like

The dashboard is a plain browser page (or a standalone window), with four tabs:

- **Active sessions** - a card per ongoing conversation: color-coded status,
  the most recently used tool, tiles for running agents, a short (expandable)
  event history.
- **Conversation archive** - a list of finished sessions with a full-history
  preview on click.
- **Statistics** - most-used tools, error count, a 14-day daily activity chart.
- **Tokens** - real token consumption (input/output/cache), parsed from Claude
  Code's own transcripts.

### Why it works

Claude Code has a built-in **hooks** mechanism - commands that run automatically
on session lifecycle events (start, end, tool use, error, etc.). This project
wires a lightweight Python script into those hooks; it appends each event to a
file, and a Flask server reads, aggregates, and serves that data as a
dashboard. Hooks are **one-directional** (Claude Code → script) - this tool
only observes, it never controls a Claude Code session.

### Requirements

- **Windows** (the current version relies on `pystray`, Microsoft Edge in
  `--app` mode, and `.bat`/`.vbs` scripts - Linux/macOS would need those parts
  adapted).
- **Python 3.10+** with `pip` (check with `python --version` or `py -3 --version`).
- **Claude Code** (CLI or the VS Code extension) with permission to edit its
  own `settings.json`.
- A Chromium-based browser (Edge, Chrome) - for the address-bar-free windowed
  mode; otherwise the dashboard works fine as a regular tab in any browser at
  `http://127.0.0.1:5151/`.

### Installation

#### Option A: via Claude Code (recommended)

This repository ships a ready-made **Skill** (`.claude/skills/install-monitor/`)
that Claude Code can run on its own - it detects your Python, installs
dependencies, appends hooks to **your own** `settings.json` (with paths
detected on your machine) and starts the app.

1. Clone this repository and **open Claude Code exactly in this folder**.
2. Tell Claude Code: `install the monitor` (or any similar phrasing).
3. Claude Code will walk you through the rest - including asking whether hooks
   should watch every session on your machine, or just one chosen project.

#### Option B: manual

```bash
git clone <this-repo-url>
cd ClaudeCodeMonitor
pip install -r requirements.txt
```

Find your Python's full path (`python -c "import sys; print(sys.executable)"`)
and append hooks to your `~/.claude/settings.json` (Windows:
`%USERPROFILE%\.claude\settings.json`), merging with whatever is already there:

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"SessionStart\"" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"UserPromptSubmit\"" }] }],
    "PreToolUse": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"PreToolUse\"" }] }],
    "PostToolUse": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"PostToolUse\"" }] }],
    "PostToolUseFailure": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"PostToolUseFailure\"" }] }],
    "Notification": [{ "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"Notification\"" }] }],
    "SubagentStop": [{ "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"SubagentStop\"" }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"Stop\"" }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"SessionEnd\"" }] }],
    "PreCompact": [{ "hooks": [{ "type": "command", "command": "\"<PATH_TO_PYTHON>\" \"<PATH_TO_REPO>\\hook_logger.py\" \"PreCompact\"" }] }]
  }
}
```

Replace `<PATH_TO_PYTHON>` and `<PATH_TO_REPO>` with your real paths. Validate
that the file is well-formed JSON (e.g. paste it into any JSON validator) - a
syntax error will silently disable all of your existing Claude Code settings,
not just the hooks.

### Running it

Easiest: double-click `start_monitor.vbs` (starts with no flashing console
window, shows the tray icon). Alternatively `start_monitor.bat` (with a visible
console - useful for troubleshooting), or manually:

```bash
python app.py
```

then open `http://127.0.0.1:5151/` in your browser.

### Configuration

The settings panel (⚙️ icon in the dashboard header) lets you change the
threshold after which a "working" status turns into a "might be stuck" warning
(default 3 minutes), and toggle notification sound on/off. System notifications
require a one-time click on "Allow notifications" in the same panel.

### Architecture

```
Claude Code  ──hooks──▶  hook_logger.py  ──▶  events.jsonl / archive/*.json
                                                        │
                                                        ▼
                                                    app.py (Flask)
                                                        │  REST API
                                                        ▼
                                              browser dashboard
                                                        ▲
                                                        │
                                        run.py - system tray icon
```

For the full internal architecture, all API endpoints, and design decisions,
see [`DEVELOPMENT.md`](DEVELOPMENT.md).

### Known limitations

- Hooks are one-directional - you can't control Claude Code (e.g. switch
  models) from this dashboard.
- The current version is Windows-oriented (tray icon, Edge `--app`, `.bat`/`.vbs`).
- It does not show authentic Claude Code account limits (e.g. a weekly plan
  quota) - that data only exists on Anthropic's side, not locally. The
  "Tokens" tab shows real consumption only, never a remaining quota.
- No filtering/search across cards, archive, or statistics.

### Development and bug reports

Issues and pull requests are welcome. For larger changes, please open an issue
describing the proposal first.

### License

[MIT](LICENSE) © 2026 [MrPrompt](https://mrprompt.eu/)
