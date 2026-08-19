Option Explicit

Dim shell
Dim scriptDir
Dim batPath

scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
batPath = scriptDir & "launch_dashboard.bat"

Set shell = CreateObject("WScript.Shell")
shell.Run """" & batPath & """", 0, False
