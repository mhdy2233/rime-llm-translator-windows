Set fso = CreateObject("Scripting.FileSystemObject")
curDir = fso.GetParentFolderName(WScript.ScriptFullName)
pyEmbed = curDir & "\python\pythonw.exe"
daemonPy = curDir & "\daemon.py"
Set ws = CreateObject("WScript.Shell")
If fso.FileExists(pyEmbed) Then
    ws.Run """" & pyEmbed & """ """ & daemonPy & """", 0, False
Else
    ws.Run "pythonw.exe """ & daemonPy & """", 0, False
End If
