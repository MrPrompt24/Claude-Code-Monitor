# Dokumentacja techniczna

Ten plik opisuje wewnętrzną architekturę, wszystkie endpointy API i decyzje
projektowe - dla osób, które chcą rozwijać ten projekt dalej albo zrozumieć
dokładnie, jak działa pod maską. Instrukcje instalacji i podstawowy opis
funkcji są w [`README.md`](README.md).

## Architektura

```
Claude Code
      │  odpala hooki cyklu życia (SessionStart, PreToolUse, Stop, ...)
      ▼
hook_logger.py  ──► events.jsonl   (jedna linia JSON = jedno zdarzenie, sesje "żywe")
                          │
                          │  co 60s: sesje zakończone (SessionEnd) lub
                          │  nieaktywne >12h są przenoszone do archive/<sid>.json
                          ▼
                     app.py (Flask)
                          │  /api/status   - aktywne sesje (z events.jsonl)
                          │  /api/archive  - lista zarchiwizowanych rozmów
                          │  /api/archive/<sid> - pełna historia jednej archiwalnej rozmowy
                          │  /api/config   - odczyt/zapis ustawień (próg zawieszenia)
                          │  /api/stats    - zagregowane statystyki (narzędzia, błędy, aktywność)
                          │  /api/tokens   - realne zużycie tokenów (z transkryptów sesji)
                          ▼
              templates/index.html (dashboard w przeglądarce)
                          │  odpytuje /api/status co 1s (polling)
                          │  dźwięk/powiadomienie systemowe przy zmianie statusu
                          ▼
                   Ty patrzysz na okienko / na ikonę w zasobniku
                          ▲
                          │  run.py - dodatkowo ikona w tray (kolor = status),
                          │  menu: Otwórz Monitor / Zamknij
```

Hooki Claude Code są **jednokierunkowe**: Claude Code → skrypt. Nie ma kanału
zwrotnego, którym dashboard mógłby sterować sesją Claude Code (np. zmieniać model).

## Pliki

| Plik | Rola |
|---|---|
| `hook_logger.py` | Wywoływany przez Claude Code przy każdym evencie. Czyta JSON ze stdin, dopisuje wiersz do `events.jsonl` (w tym `tool_use_id`, `description`, `error`, `agent_id`, `tool_response_agent_id` - do precyzyjnego śledzenia agentów i błędów). |
| `events.jsonl` | Log **aktywnych** sesji (append-only, w `.gitignore` - to lokalne dane, nie commituje się). Sesje zakończone/nieaktywne są z niego usuwane przy rotacji i trafiają do `archive/`. |
| `config.json` | Zapisane ustawienia (obecnie: `stale_after_seconds`) - tworzony/nadpisywany przez `/api/config`, w `.gitignore`. |
| `archive/<session_id>.json` | Pełna historia jednej zakończonej/wygasłej sesji (metadane + wszystkie zdarzenia). Jeden plik = jedna rozmowa. W `.gitignore`. |
| `app.py` | Serwer Flask. Agreguje `events.jsonl` per sesja, wykrywa zawieszenia, precyzyjnie śledzi agentów, rotuje do archiwum, parsuje transkrypty pod kątem tokenów, wystawia API. |
| `templates/index.html` | Dashboard: zakładki "Aktywne sesje" / "Archiwum rozmów" / "Statystyki" / "Tokeny", panel ustawień, okna Pomoc/O aplikacji, dźwięk/powiadomienia. |
| `run.py` | Launcher: startuje Flask w wątku, otwiera dashboard jako okienko (Edge `--app`) i pokazuje ikonę w zasobniku systemowym (kolor = ogólny status, menu Otwórz/Zamknij). |
| `start_monitor.bat` / `start_monitor.vbs` | Skrypty startowe (z konsolą / bez konsoli). |
| `.claude/skills/install-monitor/SKILL.md` | Skill dla Claude Code - automatyczna instalacja u nowego użytkownika (wykrycie Pythona, hooki, uruchomienie). |

## Konfiguracja hooków

Hooki dopisuje się do pliku `settings.json` Claude Code - globalnie
(`~/.claude/settings.json`, obserwuje wszystkie sesje) albo per-projekt
(`.claude/settings.json` w konkretnym repo). Każdy z poniższych eventów
wywołuje `hook_logger.py "<NazwaEventu>"`:

- `SessionStart`, `SessionEnd` - początek/koniec rozmowy
- `UserPromptSubmit` - wysłałeś wiadomość
- `PreToolUse` / `PostToolUse` (matcher `*`) - Claude zaczyna/kończy używać narzędzia
- `PostToolUseFailure` (matcher `*`) - narzędzie zwróciło błąd
- `Notification` - Claude czeka na Twoją reakcję (np. prośba o zgodę)
- `SubagentStop` - pomocniczy agent skończył zadanie
- `Stop` - Claude skończył odpowiadać
- `PreCompact` - kompresja historii rozmowy

Zobacz `README.md` (sekcja Instalacja) albo `.claude/skills/install-monitor/SKILL.md`
po dokładny format komend i sposób scalania z istniejącym `settings.json`.

## Ikona w zasobniku systemowym

`run.py` pokazuje kolorową kropkę w zasobniku (obok zegara, ew. pod strzałką
"pokaż ukryte ikony"):
- **kolor** = najważniejszy status spośród wszystkich aktywnych sesji (czerwony = błąd,
  pomarańczowy = zawieszenie/czeka, niebieski = pracuje, zielony = gotowe, szary = brak
  aktywnych sesji) - odświeżany co 3 sekundy,
- **kliknięcie / podwójny klik** - otwiera okienko dashboardu,
- **prawy klik → menu** - "Otwórz Monitor" / "Zamknij" (zamyka cały proces: serwer + ikonę).

## Co oznaczają statusy (kategorie)

| Kategoria | Znaczenie | Kolor |
|---|---|---|
| `working` | Claude coś teraz robi (dostał wiadomość, używa narzędzia) | niebieski |
| `waiting` | Czeka na Twoją reakcję (Notification event) | pomarańczowy |
| `done` | Skończył odpowiadać, czeka na kolejną wiadomość | zielony |
| `error` | Ostatnie narzędzie zwróciło błąd (`PostToolUseFailure`) | czerwony |
| `stale` | Status "working" bez żadnego nowego zdarzenia od progu zawieszenia - może się zawiesił | pomarańczowy/czerwony, ⚠️ |
| `ended` | Sesja zakończona (`SessionEnd`) | szary |
| `info` | Zdarzenia informacyjne (start sesji, subagent skończył, kompresja historii) | fioletowy |

Próg zawieszenia jest **konfigurowalny w UI** (menu ⚙️ → "Próg zawieszenia (min)"),
zapisywany w `config.json` przez `/api/config` (domyślnie 180s / 3 min).

## Moduł "Agenci"

Pokazuje kafelki dla subagentów uruchamianych w danej sesji (np. przez Task/Agent) -
dokładnie tylu, ilu faktycznie działa naraz, każdy ze swoim statusem i wynikiem.

**Jak działa precyzyjne dopasowanie:**
- `PreToolUse` z narzędziem `Agent`/`Task` → tworzy kafelek "pracuje", etykieta z pola
  `description`, klucz roboczy = `tool_use_id`.
- `PostToolUse` tego samego wywołania:
  - jeśli agent poszedł **w tło** (`run_in_background`) - odpowiedź zawiera
    `{"isAsync": true, "agentId": "..."}`. To **nie jest zakończenie**, tylko
    potwierdzenie startu - zapamiętujemy mapowanie `agent_id → tool_use_id`
    i kafelek zostaje "pracuje".
  - jeśli wywołanie było **synchroniczne** (blokujące) - `PostToolUse` faktycznie
    oznacza koniec, więc kafelek od razu staje się "zakończony".
- `SubagentStop` niesie w sobie top-level pole **`agent_id`** - dokładnie ten sam
  identyfikator, co w `tool_response.agentId`. Dzięki zapamiętanemu mapowaniu
  wiadomo precyzyjnie, który konkretnie agent skończył - nawet gdy kilka działa
  równolegle i kończą się w innej kolejności niż wystartowały. Dodatkowo
  `SubagentStop` niesie `last_assistant_message` - ostatnią odpowiedź agenta,
  pokazywaną jako kursywą podpisany wynik na kafelku.
- Fallback (domykanie najstarszego "pracującego" agenta) zostaje tylko jako
  zabezpieczenie dla zdarzeń sprzed tej poprawki / na wypadek brakującego `agent_id`.

**Przetestowane na żywo:** 3 agenty odpalone równolegle z różnymi opóźnieniami
(kończące się w innej kolejności niż start) - każdy poprawnie dopasowany do
własnego wyniku, żaden nie zamknięty przedwcześnie ani pomylony z innym.

**Czyszczenie:** zakończone kafelki znikają z modułu automatycznie po 10 minutach
(`AGENT_TILE_RETENTION_SECONDS` w `app.py`), a dodatkowo można je odrzucić ręcznie
od razu przyciskiem **✕** w rogu kafelka (widoczny tylko na zakończonych, nie na
"pracuje"). Odrzucenie jest zapamiętywane tylko w przeglądarce (per sesja) - pełna
historia zostaje nienaruszona w osi czasu.

## Zakładka "Tokeny" (realne zużycie)

`/api/tokens` czyta prawdziwe liczby tokenów wprost z plików transkryptu Claude
Code (`transcript_path`, ta sama ścieżka, którą Claude Code i tak przekazuje w
każdym hooku) - każda odpowiedź asystenta w transkrypcie ma pole `message.usage`
z realnymi `input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens`. To nie są szacunki - to dokładnie te same liczby,
które widzi sam model.

- **Kafelki:** tokeny dziś / w tym tygodniu, z rozbiciem Input · Output · Cache.
- **Wykres słupkowy dzienny:** suma tokenów z ostatnich 14 dni (hover pokazuje pełny rozkład).
- Parsowanie transkryptów jest cache'owane po mtime+rozmiarze pliku - przy
  kolejnych odpytaniach (co 10s, gdy zakładka otwarta) pliki, które się nie
  zmieniły, nie są czytane od nowa.

**Czego to NIE pokazuje (i nie może):** autentycznych limitów konta Claude Code
(np. tygodniowy limit planu, ile Ci zostało). Sprawdzone bezpośrednio w plikach
transkryptu - nie ma tam żadnego pola z limitem/quotą/czasem resetu. Te dane
liczą i przechowują wyłącznie serwery Anthropic, nie trafiają do żadnego
lokalnego pliku ani hooka.

## Powiadomienia

Gdy status sesji zmieni się na `waiting`, `error` lub `stale`, strona:
- odtwarza krótki dźwięk (Web Audio, generowany w locie, bez pliku audio) - można wyłączyć w ustawieniach,
- pokazuje powiadomienie systemowe (Web Notification API), jeśli wcześniej kliknięto
  "Zezwól na powiadomienia" w panelu ustawień (musi być kliknięty ręcznie -
  przeglądarki ignorują `requestPermission()` wywołane automatycznie bez gestu
  użytkownika).

Działa tylko gdy strona jest otwarta (zakładka/okienko) - to zwykła strona w
przeglądarce, nie osobny proces systemowy. Ikona w zasobniku (tray) działa
niezależnie od tego, czy okienko jest otwarte.

## Archiwum zakończonych rozmów

Zakładka "Archiwum rozmów" pokazuje listę zakończonych sesji (folder projektu,
kiedy się skończyła, ile zdarzeń, ostatni status). Kliknięcie wiersza rozwija
pełną historię tej rozmowy, pobieraną z `/api/archive/<session_id>`.

**Rotacja (kiedy sesja trafia do archiwum):**
- dostała zdarzenie `SessionEnd` (poprawnie zamknięta rozmowa), **lub**
- nie miała żadnej aktywności od `ARCHIVE_AFTER_HOURS` godzin (domyślnie 12) -
  łapie przypadki, gdy okno IDE zostało po prostu zamknięte bez `SessionEnd`.

Sprawdzanie i rotacja uruchamia się automatycznie przy okazji zapytań do
`/api/status`, ale nie częściej niż raz na `ARCHIVE_CHECK_INTERVAL` sekund
(domyślnie 60s).

Stałe do zmiany ręcznie w `app.py` (nie ma jeszcze UI do tego):
`ARCHIVE_AFTER_HOURS`, `ARCHIVE_CHECK_INTERVAL`.

**Znane ograniczenie:** rotacja czyta i nadpisuje `events.jsonl` bez blokady
współdzielonej z `hook_logger.py` (który tylko dopisuje linie) - przy bardzo
pechowym zbiegu w czasie (rotacja akurat w trakcie zapisu nowego zdarzenia)
jedna linia teoretycznie mogłaby się nie zapisać. W praktyce przy typowym
użyciu (1 zdarzenie na kilka sekund) ryzyko jest znikome.

## Statystyki i wykresy

Zakładka "Statystyki" (`/api/stats`, liczone na żywo z `events.jsonl` +
wszystkich plików w `archive/`):

- **Kafelki:** sesje łącznie, średni czas trwania sesji, liczba błędów narzędzi,
  liczba wiadomości dziś / w tym tygodniu.
- **Wykres słupkowy poziomy:** najczęściej używane narzędzia (top 10, licząc
  zdarzenia `PreToolUse`).
- **Wykres słupkowy dzienny:** aktywność (liczba zdarzeń) z ostatnich 14 dni,
  z podpowiedzią (hover) pokazującą dokładną liczbę zdarzeń i wiadomości danego dnia.

Dane odświeżają się co 10s, gdy zakładka jest otwarta. Kolor wykresów używa
jednego, spójnego odcienia (pojedyncza seria danych per kategoria/dzień) -
nie ma potrzeby rozróżniania wielu serii kolorem.

**Znane ograniczenie:** średni czas sesji liczony jest jako rozpiętość między
pierwszym a ostatnim zdarzeniem danej sesji - jeśli sesja została tylko otwarta
i natychmiast zamknięta bez żadnej realnej pracy, wliczy się jako ~0 min
(pomijana poniżej 3 sekund), a bardzo długo otwarte, ale w większości bezczynne
okno IDE zawyży średnią (liczy się czas "od-do", nie czas faktycznej aktywności).

## Czytelność interfejsu (skrócona historia)

Żeby karta aktywnej sesji nie zamieniała się w ścianę tekstu, oś czasu domyślnie
pokazuje tylko ostatnie 3 zdarzenia (przyciemnione, bez scrolla) z linkiem
"Pokaż pełną historię (N zdarzeń)" - dopiero kliknięcie rozwija cały, przewijany
log. Stan rozwinięcia jest pamiętany per sesja w przeglądarce, więc nie zwija
się samo przy kolejnym odświeżeniu (1s pollingu).

## Znane ograniczenia

- Nie da się sterować Claude Code z poziomu tego dashboardu (np. zmieniać modelu) - hooki są jednokierunkowe.
- Obecna wersja jest zorientowana na Windows (tray icon przez `pystray`, Edge `--app`, `.bat`/`.vbs`).
- Brak filtrowania/szukania w kartach, archiwum, statystykach i tokenach.
- Średni czas sesji jest przybliżony (patrz wyżej) - to rozpiętość czasowa, nie suma realnej aktywności.
- Okno nie ma opcji "zawsze na wierzchu" - rozważane, patrz sekcja niżej.
- Brak autentycznych limitów konta (patrz "Zakładka Tokeny" wyżej).

## Pomysły na dalszy rozwój

- Panel ustawień: przenieść `ARCHIVE_AFTER_HOURS`/`ARCHIVE_CHECK_INTERVAL` do UI.
- Filtrowanie kart/archiwum/statystyk/tokenów po folderze projektu / szukanie w historii.
- Eksport podsumowania sesji ("co dziś zrobił Claude") jako tekst/markdown.
- Wykres trendu tygodniowego (obecnie tylko dzienny za ostatnie 14 dni).
- Okno "zawsze na wierzchu" - albo przejście na `pywebview` (ma to wbudowane, solidniejsze), albo hack przez Windows API na obecnym oknie Edge.
- Obsługa Linux/macOS (obecnie tray icon i okno zależą od komponentów specyficznych dla Windows).
