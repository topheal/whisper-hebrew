' מפעיל את scan_silent.bat ללא חלון קונסולה גלוי (WindowStyle=0)
Dim fso, dir, WshShell
Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "cmd.exe /c """ & dir & "\scan_silent.bat""", 0, False
