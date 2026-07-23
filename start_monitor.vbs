' Uruchamia Claude Code Monitor bez okna konsoli (Python Launcher w trybie "pyw").
' Jesli "pyw" nie jest rozpoznawane, zainstaluj Python z python.org (Python
' Launcher instaluje sie razem z nim) albo podmien "pyw -3" na pelna sciezke
' do swojego pythonw.exe.
Set objShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run "pyw -3 """ & scriptDir & "\run.py""", 0, False
