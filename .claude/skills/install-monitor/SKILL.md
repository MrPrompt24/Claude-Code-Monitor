---
name: install-monitor
description: Instaluje i konfiguruje Claude Code Monitor (lokalny dashboard pokazujący na żywo status Claude Code) w tym repozytorium na komputerze bieżącego użytkownika - wykrywa Pythona, instaluje zależności, dopisuje hooki cyklu życia do jego OSOBISTEGO pliku settings.json i uruchamia aplikację. Użyj, gdy użytkownik prosi o "zainstaluj monitor", "skonfiguruj Claude Code Monitor", "ustaw hooki dla monitora" albo otwiera to repozytorium po raz pierwszy i pyta jak zacząć.
---

# Instalacja Claude Code Monitor

Ten skill zakłada, że działasz z katalogu roboczego będącego **głównym folderem tego
repozytorium** (tam, gdzie leżą `app.py`, `hook_logger.py`, `run.py`). Jeśli te pliki
nie istnieją w bieżącym katalogu, zatrzymaj się i poproś użytkownika, żeby otworzył
Claude Code dokładnie w folderze sklonowanego repozytorium.

Wykonuj kroki po kolei. Nie pomijaj weryfikacji - błędna ścieżka do Pythona albo
źle złożony JSON w `settings.json` cicho wyłączy WSZYSTKIE hooki użytkownika, nie
tylko te dodane przez ciebie.

## Krok 1: Wykryj Pythona

Sprawdź po kolei (pierwszy działający wygrywa): `python --version`, `py -3 --version`,
`python3 --version`. Gdy znajdziesz działający, pobierz jego **pełną ścieżkę**:

```
<komenda> -c "import sys; print(sys.executable)"
```

Z tej ścieżki wyprowadź też ścieżkę do `pythonw.exe` (ten sam folder, plik
`pythonw.exe` zamiast `python.exe`) - potrzebna do uruchamiania bez okna konsoli.
Jeśli `pythonw.exe` nie istnieje obok `python.exe` (rzadkie, ale możliwe np. przy
niektórych dystrybucjach), użyj zwykłego `python.exe` wszędzie i uprzedź
użytkownika, że okno konsoli będzie migać przy starcie.

Jeśli żadna z komend nie działa: zatrzymaj się i poinformuj użytkownika, że
potrzebuje zainstalowanego Pythona 3.10+ (python.org, z zaznaczoną opcją "Add
python.exe to PATH") - nie kontynuuj bez tego.

## Krok 2: Zainstaluj zależności

```
<pelna_sciezka_python> -m pip install -r requirements.txt --quiet
```

Sprawdź kod wyjścia. Jeśli się nie powiedzie, pokaż użytkownikowi błąd pip i
zapytaj czy chce spróbować ręcznie (np. problem z uprawnieniami/proxy) zamiast
ciągnąć dalej w ciemno.

## Krok 3: Ustaw poprawne ścieżki w launcherach

Podmień w `start_monitor.bat` linię `py -3 "%~dp0run.py"` na wywołanie z pełną
wykrytą ścieżką do `python.exe`, np.:

```
"<pelna_sciezka_python.exe>" "%~dp0run.py"
```

Analogicznie w `start_monitor.vbs` podmień `"pyw -3 """ & scriptDir & ...` na
pełną ścieżkę do `pythonw.exe`. Rób to tylko jeśli test z Kroku 1 pokazał, że
`py`/`pyw` nie są dostępne z PATH - jeśli działają, możesz zostawić pliki
bez zmian (są już gotowe do użycia z `py`/`pyw` na PATH).

## Krok 4: Zapisz absolutną ścieżkę do `hook_logger.py`

Ustal pełną, absolutną ścieżkę do pliku `hook_logger.py` w tym katalogu
(np. przez `pwd` / bieżący katalog roboczy + nazwa pliku). Będzie potrzebna
w Kroku 5 do skonstruowania komend hooków.

## Krok 5: Zapytaj o zakres instalacji hooków

Zapytaj użytkownika (jednym pytaniem, z opcjami): czy monitor ma obserwować
**wszystkie** sesje Claude Code na tym komputerze (hooki w globalnym
`~/.claude/settings.json` - na Windows `%USERPROFILE%\.claude\settings.json`),
czy tylko sesje w **tym konkretnym projekcie** (hooki w `.claude/settings.json`
wewnątrz repo, w którym pracuje użytkownik - nie tego repo z monitorem, tylko
tego, który chce monitorować). Domyślnie/rekomendowane: globalnie.

## Krok 6: Dopisz hooki

Przeczytaj docelowy plik `settings.json` (jeśli nie istnieje, będzie utworzony
od zera). **Scal, nie nadpisuj** - jeśli są tam już inne klucze (np.
`effortLevel`, `permissions`, inne `hooks`), zachowaj je.

Dodaj (albo scal, jeśli sekcja `hooks` już istnieje) następujące zdarzenia,
każde wywołujące:
`"<pelna_sciezka_python_lub_pythonw.exe>" "<pelna_sciezka_hook_logger.py>" "<NazwaZdarzenia>"`

Zdarzenia i ich matcher (gdzie wymagany, matcher = `"*"`):
`SessionStart`, `UserPromptSubmit`, `PreToolUse` (matcher `*`),
`PostToolUse` (matcher `*`), `PostToolUseFailure` (matcher `*`),
`Notification`, `SubagentStop`, `Stop`, `SessionEnd`, `PreCompact`.

Po zapisie zweryfikuj składnię: wczytaj plik przez `json.load` (Python) - błąd
parsowania = zatrzymaj się i napraw przed kontynuowaniem, bo zepsuty
`settings.json` wyłącza WSZYSTKIE ustawienia użytkownika, nie tylko hooki.

## Krok 7: Uruchom i zweryfikuj

Uruchom `start_monitor.bat` (albo `start_monitor.vbs` dla wersji bez okna
konsoli) w tle, poczekaj chwilę, sprawdź czy `http://127.0.0.1:5151/api/status`
odpowiada (np. przez `curl`). Jeśli port zajęty lub brak odpowiedzi - sprawdź
logi/błąd procesu zamiast zgadywać.

## Krok 8: Poinformuj użytkownika

Podsumuj krótko: gdzie zapisane są hooki (globalnie czy per-projekt), jak
uruchamiać monitor na stałe (`start_monitor.vbs` - dwuklik, bez okna konsoli),
że przy pierwszym otwarciu dashboardu w panelu ustawień (⚙️) warto kliknąć
"Zezwól na powiadomienia", jeśli chce dźwięku/toastów. Wspomnij, że hooki
zaczynają działać od razu, bez restartu Claude Code (tak jak w oryginalnej
instalacji), ale jeśli coś nie działa - restart sesji/okna Claude Code jest
pierwszym krokiem do sprawdzenia.

## Uwagi

- Nie usuwaj i nie nadpisuj niczego w `settings.json` poza sekcją `hooks` (i to
  tylko scalając, nie zastępując całości).
- Jeśli w repo istnieją już pliki `events.jsonl`, `archive/`, `config.json` -
  to nie powinno się zdarzyć w świeżo sklonowanym repo (są w `.gitignore`), ale
  jeśli jednak są obecne, zostaw je - to lokalne dane użytkownika, nie twoja
  sprawa je ruszać.
