# Revision 3: run a shell script while asking Windows not to sleep (ES_CONTINUOUS | ES_SYSTEM_REQUIRED).
# Usage: powershell -File src/revision3/keep_awake_run.ps1 <script.sh>   (from Paper2/)
param([string]$Script)
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Start-Process -FilePath "C:\Program Files\Git\bin\sh.exe" -ArgumentList $Script -WorkingDirectory (Get-Location) -WindowStyle Hidden -Wait
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
