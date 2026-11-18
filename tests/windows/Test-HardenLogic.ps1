<#
  Logic tests for scripts/windows/Harden.ps1 that run anywhere PowerShell 7 runs
  (including Linux): the script's functions are loaded without running it, and
  Windows-only programs (secedit.exe, auditpol.exe ...) are replaced by fakes.

      pwsh tests/windows/Test-HardenLogic.ps1

  This does NOT replace a real test on a Windows practice image (Audit mode first!).
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$scriptPath = Join-Path $root 'scripts/windows/Harden.ps1'
if ($env:HARDEN_PS1) { $scriptPath = $env:HARDEN_PS1 }   # e.g. an older copy, to see a test fail

# --- Load every function from Harden.ps1 without running its main code -------
$ast = [System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$null, [ref]$null)
foreach ($fn in $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
# Top-level tables the functions use ($Sections, $ServiceCatalog, regexes ...)
foreach ($st in $ast.EndBlock.Statements) {
    if ($st -is [System.Management.Automation.Language.AssignmentStatementAst] -and $st.Left.Extent.Text -match '^\$(Sections|ServiceCatalog|CoreServices|SoftwarePatterns|SoftwareReviewPattern|AppxPattern|SuspiciousCmdRegex|CpProtectRegex|DcProtectedServices|FirewallGroupsForCritical)$') {
        . ([scriptblock]::Create($st.Extent.Text))
    }
}

# --- Test environment ----------------------------------------------------------
$tmp = Join-Path ([IO.Path]::GetTempPath()) "harden-test-$PID"
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$RunId = 'test'; $BackupDir = Join-Path $tmp 'backup'; $LogFile = Join-Path $tmp 'log.txt'; $ReportFile = Join-Path $tmp 'report.txt'
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
if (-not $env:TEMP) { $env:TEMP = $tmp }
$script:Results = New-Object System.Collections.Generic.List[object]
$script:CurrentSection = 'test'; $script:BackedUpKeys = @{}; $script:Me = 'alice'
function Write-Host { }   # keep the test output readable

$pass = 0; $fail = 0
function Assert([string]$Name, [scriptblock]$Test) {
    try { $ok = & $Test } catch { $ok = $false; $Name += " (threw: $($_.Exception.Message))" }
    if ($ok) { $script:pass++; [Console]::WriteLine("PASS  $Name") } else { $script:fail++; [Console]::WriteLine("FAIL  $Name") }
}
function Reset-Results { $script:Results.Clear() }
function Last-Status { $script:Results[$script:Results.Count - 1].Status }

# --- Fake secedit.exe: keeps a policy "database" in a file ----------------------
$script:FakePolicy = @{ 'System Access' = [ordered]@{ MinimumPasswordLength = '0'; PasswordComplexity = '0'; LockoutBadCount = '0' }
                        'Privilege Rights' = [ordered]@{ SeDebugPrivilege = '*S-1-1-0,*S-1-5-32-544'; SeNetworkLogonRight = '*S-1-1-0,*S-1-5-32-544,*S-1-5-32-545';
                                                         SeDenyInteractiveLogonRight = '*S-1-5-32-545'; SeTcbPrivilege = '*S-1-1-0' } }
function secedit.exe {
    $all = $args
    $cfg = $all[[array]::IndexOf($all, '/cfg') + 1]
    if ($all -contains '/export') {
        $out = @('[Unicode]', 'Unicode=yes')
        # Like the real secedit, a right that nobody holds is left out of the export
        foreach ($sec in $script:FakePolicy.Keys) { $out += "[$sec]"; foreach ($k in $script:FakePolicy[$sec].Keys) { if ("$($script:FakePolicy[$sec][$k])" -ne '') { $out += "$k = $($script:FakePolicy[$sec][$k])" } } }
        $out | Set-Content -Path $cfg
    } elseif ($all -contains '/configure') {
        $section = ''
        foreach ($line in (Get-Content $cfg)) {
            if ($line -match '^\[(.+)\]$') { $section = $Matches[1]; continue }
            if ($line -match '^(\S+) = (.*)$' -and $section -notin @('Unicode', 'Version')) {
                if (-not $script:FakePolicy.ContainsKey($section)) { $script:FakePolicy[$section] = [ordered]@{} }
                $script:FakePolicy[$section][$Matches[1]] = $Matches[2]
            }
        }
    }
}

# ===========================================================================
# Tests
# ===========================================================================
Assert 'Split-Names handles commas, semicolons and spaces' { (Split-Names 'alice, bob;carol   dave').Count -eq 4 }
Assert 'Split-Names: a config array element is ONE name, even with a space (local user "John Smith")' { $n = @(Split-Names @('alice', 'John Smith')); $n.Count -eq 2 -and $n[1] -eq 'John Smith' }
Assert 'Split-Names: an array element with commas is still split' { (Split-Names @('alice, bob', 'carol')).Count -eq 3 }
Assert 'Split-Names: typed names can be quoted ("John Smith" stays whole)' { $n = @(Split-Names 'alice "John Smith" bob'); $n.Count -eq 3 -and $n[1] -eq 'John Smith' }
Assert 'Split-Names: DOMAIN\name and .\name are reduced to the name' { (@(Split-Names 'CORP\alice .\bob') -join ',') -eq 'alice,bob' }
Assert 'Split-Names: $null, empty and a single name' { @(Split-Names $null).Count -eq 0 -and @(Split-Names '').Count -eq 0 -and @(Split-Names 'alice').Count -eq 1 }
Assert 'Strong password accepted' { Test-StrongPassword 'Cyb3r!Patr1ot#2026' }
Assert 'Weak password rejected (no symbol)' { -not (Test-StrongPassword 'Password12345') }
Assert 'Short password rejected' { -not (Test-StrongPassword 'Ab1!') }

$cfgFile = Join-Path $root 'scripts/windows/config.example.psd1'
Import-ReadmeConfig $cfgFile
Assert 'Example config: admins loaded' { $script:AuthAdmins -contains 'alice' }
Assert 'Example config: users loaded' { $script:AuthUsers -contains 'carol' }
Assert 'Example config: critical services lower-cased' { $script:Critical -contains 'rdp' }
Assert 'Test-Critical finds a listed service' { Test-Critical @('remotedesktop', 'rdp') }
Assert 'Test-Critical ignores unlisted services' { -not (Test-Critical @('ftp')) }
Assert 'Test-Authorized' { (Test-Authorized 'carol') -and -not (Test-Authorized 'mallory') }

$script:Mode = 'Audit'; $script:AssumeYes = $false
Assert 'Audit mode never says yes' { -not (Confirm-Step 'x' 'y') }
$script:Mode = 'Apply'; $script:AssumeYes = $true
Assert '-Yes answers yes' { Confirm-Step 'x' 'n' }
Assert '-Yes with -Strict uses the default' { -not (Confirm-Step 'x' 'n' -Strict) }

$script:Mode = 'Audit'; Reset-Results
Invoke-Fix 'do something' { throw 'must not run in audit mode' } | Out-Null
Assert 'Invoke-Fix in Audit mode reports WOULD and runs nothing' { (Last-Status) -eq 'WOULD' }
$script:Mode = 'Apply'; Reset-Results
Invoke-Fix 'works' { 1 } | Out-Null
Assert 'Invoke-Fix success -> CHANGED' { (Last-Status) -eq 'CHANGED' }
Invoke-Fix 'breaks' { throw 'boom' } | Out-Null
Assert 'Invoke-Fix error -> FAILED' { (Last-Status) -eq 'FAILED' }

Assert 'reg.exe path conversion (HKLM:)' { (ConvertTo-RegExePath 'HKLM:\SOFTWARE\X') -eq 'HKLM\SOFTWARE\X' }
Assert 'reg.exe path conversion (provider path)' { (ConvertTo-RegExePath 'Microsoft.PowerShell.Core\Registry::HKEY_LOCAL_MACHINE\SOFTWARE\X') -eq 'HKEY_LOCAL_MACHINE\SOFTWARE\X' }

# Password policy through the fake secedit
$script:Mode = 'Audit'; Reset-Results; $script:EnableLockout = 'yes'
Invoke-Passwords
Assert 'Audit: weak password policy reported as WOULD' { @($script:Results | Where-Object Status -eq 'WOULD').Count -eq 1 }
Assert 'Audit: policy untouched' { $script:FakePolicy['System Access']['MinimumPasswordLength'] -eq '0' }
$script:Mode = 'Apply'; Reset-Results
Invoke-Passwords
Assert 'Apply: password policy CHANGED' { (Last-Status) -eq 'CHANGED' }
Assert 'Apply: length 12, complexity on, lockout 5' {
    $sa = $script:FakePolicy['System Access']; $sa['MinimumPasswordLength'] -eq '12' -and $sa['PasswordComplexity'] -eq '1' -and $sa['LockoutBadCount'] -eq '5' }
Reset-Results
Invoke-Passwords
Assert 'Second run: password policy already OK (idempotent)' { (Last-Status) -eq 'OK' }

# User rights
$script:Mode = 'Apply'; Reset-Results
Invoke-UserRights
$pr = $script:FakePolicy['Privilege Rights']
Assert 'Everyone removed from Debug programs' { $pr['SeDebugPrivilege'] -eq '*S-1-5-32-544' }
Assert 'Everyone removed from network logon, Users kept' { $pr['SeNetworkLogonRight'] -eq '*S-1-5-32-544,*S-1-5-32-545' }
Assert 'Users taken off "deny local logon", Guests added' { $pr['SeDenyInteractiveLogonRight'] -eq '*S-1-5-32-546' }
Assert 'Guests denied network logon' { $pr['SeDenyNetworkLogonRight'] -eq '*S-1-5-32-546' }
Assert 'Everyone removed from "Act as part of the OS" (now No One)' { "$($pr['SeTcbPrivilege'])" -eq '' }
Assert 'Emptying a right is reported CHANGED, not a false FAILED' { (Last-Status) -eq 'CHANGED' -and -not @($script:Results | Where-Object Status -eq 'FAILED').Count }
Reset-Results
Invoke-UserRights
Assert 'Second run: user rights OK (idempotent)' { (Last-Status) -eq 'OK' }

# Suspicious command detection
Assert 'Encoded PowerShell is suspicious' { 'powershell.exe -w hidden -enc SQBFAFgA' -match $SuspiciousCmdRegex }
Assert 'netcat is suspicious' { 'C:\Users\Public\nc.exe -lvp 4444 -e cmd.exe' -match $SuspiciousCmdRegex }
Assert 'OneDrive is not suspicious' { -not ('"C:\Program Files\Microsoft OneDrive\OneDrive.exe" /background' -match $SuspiciousCmdRegex) }
Assert 'Security Health is not suspicious' { -not ('%windir%\system32\SecurityHealthSystray.exe' -match $SuspiciousCmdRegex) }
Assert 'CyberPatriot scoring is protected' { 'C:\CyberPatriot\CCSClient.exe' -match $CpProtectRegex }

# Software patterns
Assert 'Wireshark is a hacking tool' { 'Wireshark 4.2.0 64-bit' -match "(?i)$($SoftwarePatterns['hacking tool'])" }
Assert 'uTorrent is P2P' { 'uTorrent' -match "(?i)$($SoftwarePatterns['file-sharing (P2P)'])" }
Assert 'Notepad++ is not flagged' { -not (@($SoftwarePatterns.Values | Where-Object { 'Notepad++ (64-bit x64)' -match "(?i)$_" }).Count) }
Assert 'Microsoft Edge is not flagged' { -not (@($SoftwarePatterns.Values | Where-Object { 'Microsoft Edge' -match "(?i)$_" }).Count) }

# --- Fake registry: HK* paths live in a hashtable, everything else goes to the real cmdlets ---
$script:FakeReg = @{}
function Reset-Reg { $script:FakeReg = @{} }
function Set-FakeReg([string]$Path, [string]$Name, $Value) {
    if (-not $script:FakeReg.ContainsKey($Path)) { $script:FakeReg[$Path] = [ordered]@{} }
    $script:FakeReg[$Path][$Name] = $Value
}
function reg.exe { }
function Test-Path {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$Path, [string]$LiteralPath)
    $p = if ($LiteralPath) { $LiteralPath } else { $Path }
    if ($p -match '^HK') { return $script:FakeReg.ContainsKey($p) }
    if ($LiteralPath) { return Microsoft.PowerShell.Management\Test-Path -LiteralPath $p }
    return Microsoft.PowerShell.Management\Test-Path -Path $p
}
function Get-Item {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$Path, [string]$LiteralPath, [switch]$Force)
    $p = if ($LiteralPath) { $LiteralPath } else { $Path }
    if ($p -notmatch '^HK') { return Microsoft.PowerShell.Management\Get-Item @PSBoundParameters }
    if (-not $script:FakeReg.ContainsKey($p)) { if ($ErrorActionPreference -eq 'Stop') { throw "Cannot find path '$p'" } else { return $null } }
    $o = [pscustomobject]@{ Vals = $script:FakeReg[$p]; ValueCount = $script:FakeReg[$p].Count
                            SubKeyCount = @($script:FakeReg.Keys | Where-Object { $_ -like "$p\*" }).Count }
    # like RegistryKey.GetValue: a REG_MULTI_SZ comes back as one string[] (even an empty one)
    $o | Add-Member ScriptMethod GetValue { param($n, $d) if (-not $this.Vals.Contains($n)) { return $d }; $v = $this.Vals[$n]; if ($v -is [array]) { return ,$v }; return $v }
    $o | Add-Member ScriptMethod GetValueNames { @($this.Vals.Keys) }
    return $o
}
function New-Item {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$Path, [string]$ItemType, [switch]$Force)
    if ($Path -match '^HK') { if (-not $script:FakeReg.ContainsKey($Path)) { $script:FakeReg[$Path] = [ordered]@{} }; return }
    Microsoft.PowerShell.Management\New-Item @PSBoundParameters
}
function New-ItemProperty {
    [CmdletBinding()] param([string]$Path, [string]$Name, $Value, [string]$PropertyType, [switch]$Force)
    if (-not $script:FakeReg.ContainsKey($Path)) { throw "Cannot find path '$Path'" }
    if ($PropertyType -eq 'MultiString') { $v = [string[]]@($Value) } elseif ($PropertyType -eq 'DWord') { $v = [int64]$Value } else { $v = "$Value" }
    $script:FakeReg[$Path][$Name] = $v
}
function Remove-ItemProperty {
    [CmdletBinding()] param([string]$Path, [string]$LiteralPath, [string]$Name)
    $p = if ($LiteralPath) { $LiteralPath } else { $Path }
    if (-not ($script:FakeReg.ContainsKey($p) -and $script:FakeReg[$p].Contains($Name))) { throw "No value $Name" }
    $script:FakeReg[$p].Remove($Name)
}
function Remove-Item {
    [CmdletBinding()] param([Parameter(Position = 0, ValueFromPipeline = $true)][string[]]$Path, [string[]]$LiteralPath, [switch]$Force, [switch]$Recurse)
    process {
        foreach ($p in @($LiteralPath | Where-Object { $_ })) {
            if ($p -match '^HK') { $script:FakeReg.Remove($p) } else { Microsoft.PowerShell.Management\Remove-Item -LiteralPath $p -Force:$Force -Recurse:$Recurse -ErrorAction $ErrorActionPreference }
        }
        foreach ($p in @($Path | Where-Object { $_ })) {
            if ($p -match '^HK') { $script:FakeReg.Remove($p) } else { Microsoft.PowerShell.Management\Remove-Item -Path $p -Force:$Force -Recurse:$Recurse -ErrorAction $ErrorActionPreference }
        }
    }
}
function Get-Status([string]$Like) { @($script:Results | Where-Object { $_.Text -like $Like } | ForEach-Object { $_.Status }) }

Assert 'Fake registry: Set-Reg writes, second run is OK' {
    Reset-Reg; Reset-Results; $script:Mode = 'Apply'
    Set-Reg 'HKLM:\SOFTWARE\Test' 'X' 1 'DWord' 'test value'
    Set-Reg 'HKLM:\SOFTWARE\Test' 'X' 1 'DWord' 'test value'
    ((Get-Status 'test value*') -join ',') -eq 'CHANGED,OK' -and $script:FakeReg['HKLM:\SOFTWARE\Test']['X'] -eq 1 }

# Known bug: a planted "DefaultOutboundAction Block" was never reported
$fwPol = 'HKLM:\SOFTWARE\Policies\Microsoft\WindowsFirewall'
$script:FwSetCalls = @()
function Get-NetFirewallProfile {
    @([pscustomobject]@{ Name = 'Domain'; Enabled = 'True'; DefaultInboundAction = 'Block'; DefaultOutboundAction = 'NotConfigured'; LogBlocked = 'True'; NotifyOnListen = 'True' },
      [pscustomobject]@{ Name = 'Public'; Enabled = 'True'; DefaultInboundAction = 'Block'; DefaultOutboundAction = 'Block'; LogBlocked = 'True'; NotifyOnListen = 'True' })
}
function Set-NetFirewallProfile { $script:FwSetCalls += ,@($args) + @($PSBoundParameters.Keys) }
function Get-NetFirewallRule { @() }
function Enable-NetFirewallRule { }
function Disable-NetFirewallRule { }
Reset-Reg; Reset-Results; $script:Mode = 'Apply'; $script:AssumeYes = $true
Set-FakeReg "$fwPol\PublicProfile" 'DefaultOutboundAction' 1
Invoke-Firewall
Assert 'Firewall: outbound Block is a REVIEW with the fix command' {
    @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like '*Set-NetFirewallProfile -Name Public -DefaultOutboundAction Allow*' }).Count -eq 1 }
Assert 'Firewall: outbound Block set by Group Policy is a REVIEW with the fix command' {
    @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like "*Remove-ItemProperty -Path '$fwPol\PublicProfile' -Name DefaultOutboundAction*" }).Count -eq 1 }
Assert 'Firewall: outbound default is never changed by the script' {
    -not @($script:FwSetCalls | Where-Object { "$_" -match 'DefaultOutboundAction' }).Count -and $script:FakeReg["$fwPol\PublicProfile"]['DefaultOutboundAction'] -eq 1 }
Assert 'Firewall: a profile that allows outgoing traffic is OK' { (Get-Status 'Domain firewall allows outgoing*') -contains 'OK' }

# Remote Desktop: a Group Policy value beats the normal setting
$tsPol = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services'
Reset-Reg; Reset-Results; $script:Critical = @('rdp')
Set-FakeReg $tsPol 'fDenyTSConnections' 1
Invoke-RemoteAccess
Assert 'RDP critical but turned off by policy -> REVIEW with the fix, policy untouched' {
    @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like "*Remove-ItemProperty -Path '$tsPol' -Name fDenyTSConnections*" }).Count -eq 1 -and $script:FakeReg[$tsPol]['fDenyTSConnections'] -eq 1 }
Reset-Reg; Reset-Results; $script:Critical = @()
Set-FakeReg $tsPol 'fDenyTSConnections' 0
Invoke-RemoteAccess
Assert 'RDP not needed but turned on by policy -> REVIEW (the normal setting alone does not turn it off)' {
    @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like '*Group Policy turns Remote Desktop ON*' }).Count -eq 1 }

# Security options added in v2: NTLM session security, PrintNightmare, Zerologon (DC only)
Reset-Reg; Reset-Results; $script:Mode = 'Apply'; $script:IsDC = $false; $script:IsServer = $false
Invoke-SecurityOptions
$msv = 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa\MSV1_0'
$ppk = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint'
Assert 'NTLM minimum session security = 537395200 (client and server)' { $script:FakeReg[$msv]['NTLMMinClientSec'] -eq 537395200 -and $script:FakeReg[$msv]['NTLMMinServerSec'] -eq 537395200 }
Assert 'Point and Print: admins only, warnings on' {
    $script:FakeReg[$ppk]['RestrictDriverInstallationToAdministrators'] -eq 1 -and $script:FakeReg[$ppk]['NoWarningNoElevationOnInstall'] -eq 0 -and $script:FakeReg[$ppk]['UpdatePromptSettings'] -eq 0 }
Assert 'Zerologon key not written on a non-DC' { -not $script:FakeReg['HKLM:\SYSTEM\CurrentControlSet\Services\Netlogon\Parameters'].Contains('FullSecureChannelProtection') }
Set-FakeReg $ppk 'NoWarningNoElevationOnInstall' 1
Reset-Results; Invoke-SecurityOptions
Assert 'Planted NoWarningNoElevationOnInstall=1 is fixed; everything else already OK' {
    (Get-Status 'Point and Print: warn and ask for elevation when installing*') -contains 'CHANGED' -and
    -not @($script:Results | Where-Object { $_.Status -in 'CHANGED', 'FAILED' -and $_.Text -notlike 'Point and Print*' }).Count }
Assert 'An empty REG_MULTI_SZ (NullSessionPipes) counts as set: OK on the second run, not rewritten every time' {
    (Get-Status 'SMB server: no pipes open to anonymous users*') -contains 'OK' }
$script:IsDC = $true; Reset-Results; Invoke-SecurityOptions
Assert 'Domain Controller: FullSecureChannelProtection = 1' { $script:FakeReg['HKLM:\SYSTEM\CurrentControlSet\Services\Netlogon\Parameters']['FullSecureChannelProtection'] -eq 1 }
$script:IsDC = $false

# Browsers: password managers off; Firefox Preferences in the documented REG_MULTI_SZ format
$ffk = 'HKLM:\SOFTWARE\Policies\Mozilla\Firefox'
Reset-Reg; Reset-Results
Invoke-Browsers
Assert 'Edge: PasswordManagerEnabled = 0' { $script:FakeReg['HKLM:\SOFTWARE\Policies\Microsoft\Edge']['PasswordManagerEnabled'] -eq 0 }
Set-FakeReg "$ffk\Preferences" 'browser.safebrowsing.malware.enabled' '{"Value": true, "Status": "locked"}'
Set-FakeReg "$ffk\Preferences" 'browser.safebrowsing.phishing.enabled' '{"Value": true, "Status": "locked"}'
Reset-Results; Set-FirefoxSafeBrowsing $ffk
Assert 'Firefox: Preferences is one REG_MULTI_SZ JSON value with both safe-browsing prefs locked' {
    $v = $script:FakeReg[$ffk]['Preferences']; $j = ("$v" | ConvertFrom-Json)
    $v -is [array] -and $j.'browser.safebrowsing.malware.enabled'.Value -eq $true -and $j.'browser.safebrowsing.phishing.enabled'.Status -eq 'locked' }
Assert 'Firefox: the old-format Preferences subkey from v2.0.0 is removed' { -not $script:FakeReg.ContainsKey("$ffk\Preferences") }
Reset-Results; Set-FirefoxSafeBrowsing $ffk
Assert 'Firefox: second run is OK' { ((Get-Status 'Firefox:*') -join ',') -eq 'OK' }
Reset-Reg; Set-FakeReg $ffk 'Preferences' ([string[]]@('{"browser.startup.homepage": {"Value": "https://example.org"}}'))
Reset-Results; Set-FirefoxSafeBrowsing $ffk
Assert 'Firefox: an existing Preferences policy is not overwritten (REVIEW)' { (Last-Status) -eq 'REVIEW' -and "$($script:FakeReg[$ffk]['Preferences'])" -like '*homepage*' }
# Pretend Chrome and Firefox are installed (empty files under a fake Program Files)
$savedPF = $env:ProgramFiles; $env:ProgramFiles = Join-Path $tmp 'pf'
foreach ($exe in 'Google/Chrome/Application/chrome.exe', 'Mozilla Firefox/firefox.exe') {
    $full = Join-Path $env:ProgramFiles $exe
    Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path (Split-Path $full) -Force | Out-Null
    [IO.File]::WriteAllText($full, '')
}
Reset-Reg; Reset-Results; Invoke-Browsers
$env:ProgramFiles = $savedPF
Assert 'Chrome: PasswordManagerEnabled = 0' { $script:FakeReg['HKLM:\SOFTWARE\Policies\Google\Chrome']['PasswordManagerEnabled'] -eq 0 }
Assert 'Firefox: PasswordManagerEnabled = 0 and safe browsing set through Invoke-Browsers' {
    $script:FakeReg[$ffk]['PasswordManagerEnabled'] -eq 0 -and "$($script:FakeReg[$ffk]['Preferences'])" -like '*browser.safebrowsing.phishing.enabled*' }
Assert 'Browsers: nothing FAILED' { -not @($script:Results | Where-Object Status -eq 'FAILED').Count }

# Never take the person running the script out of Administrators
$script:LocalUsers = @(
    [pscustomobject]@{ Name = 'Administrator'; Enabled = $false; SID = [pscustomobject]@{ Value = 'S-1-5-21-1-2-3-500' }; PasswordNeverExpires = $false; UserMayChangePassword = $true; PasswordRequired = $true },
    [pscustomobject]@{ Name = 'alice'; Enabled = $true; SID = [pscustomobject]@{ Value = 'S-1-5-21-1-2-3-1001' }; PasswordNeverExpires = $false; UserMayChangePassword = $true; PasswordRequired = $true },
    [pscustomobject]@{ Name = 'carol'; Enabled = $true; SID = [pscustomobject]@{ Value = 'S-1-5-21-1-2-3-1002' }; PasswordNeverExpires = $false; UserMayChangePassword = $true; PasswordRequired = $true },
    [pscustomobject]@{ Name = 'mallory'; Enabled = $true; SID = [pscustomobject]@{ Value = 'S-1-5-21-1-2-3-1003' }; PasswordNeverExpires = $false; UserMayChangePassword = $true; PasswordRequired = $true })
function Get-LocalUser { param([string]$Name) if ($Name) { $script:LocalUsers | Where-Object Name -eq $Name } else { $script:LocalUsers } }
function Get-LocalGroup { }
function Remove-LocalUser { }
function Get-GroupMembers([string]$Group) {
    if ($Group -notin 'Administrators', 'Administratoren') { return @() }
    foreach ($n in 'alice', 'carol', 'mallory') { [pscustomobject]@{ Short = $n; Full = "PC\$n"; IsLocal = $true; Class = 'User' } }
}
$script:Removed = @()
function Add-LocalGroupMember { }
function Remove-GroupMember([string]$Group, [string]$Member) { $script:Removed += "$Group/$Member" }
$script:AuthAdmins = @('alice'); $script:AuthUsers = @('carol'); $script:Me = 'carol'; $script:NewPassword = 'skip'
$script:Mode = 'Apply'; $script:AssumeYes = $true; Reset-Results
Invoke-Users
Assert 'Users: an unauthorized admin is removed' { $script:Removed -contains 'Administrators/PC\mallory' }
Assert 'Users: the person running the script is never removed from Administrators' {
    $script:Removed -notcontains 'Administrators/PC\carol' -and @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like 'You (PC\carol)*' }).Count -eq 1 }
$script:Me = 'alice'

# Deleting files whose names contain [ ] (common in torrent and media names)
$fdir = Join-Path $tmp 'files'
Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path $fdir -Force | Out-Null
$f1 = Join-Path $fdir 'song [remix].mp3'; $f2 = Join-Path $fdir 'plain.mp3'
[IO.File]::WriteAllText($f1, 'x'); [IO.File]::WriteAllText($f2, 'x')
Remove-FileList @($f1, $f2)
Assert 'Remove-FileList deletes "song [remix].mp3" (not treated as a wildcard)' {
    -not (Microsoft.PowerShell.Management\Test-Path -LiteralPath $f1) -and -not (Microsoft.PowerShell.Management\Test-Path -LiteralPath $f2) }


# --- v2.1.0 additions ---------------------------------------------------------
# Well-known groups are looked up by SID, so a German Windows ("Administratoren") works
function Get-WellKnownName([string]$Sid, [string]$Default) { if ($Sid -eq 'S-1-5-32-544') { 'Administratoren' } elseif ($Sid -eq 'S-1-1-0') { 'Jeder' } else { $Default } }
$script:Removed = @(); $script:Me = 'carol'; $script:AuthAdmins = @('alice'); $script:AuthUsers = @('carol'); Reset-Results
Invoke-Users
Assert 'Users: the Administrators group is found by SID (German name used for the removal)' { $script:Removed -contains 'Administratoren/PC\mallory' }
# put the real function back
. ([scriptblock]::Create(($ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $args[0].Name -eq 'Get-WellKnownName' }, $false))[0].Extent.Text))
Assert 'Get-WellKnownName falls back to the default when the SID cannot be translated' { (Get-WellKnownName 'S-1-5-32-544' 'Administrators') -in 'Administrators', 'Administratoren' -and (Get-WellKnownName 'not-a-sid' 'Fallback') -eq 'Fallback' }
$script:Me = 'alice'

# No README user list: powerful-group members are reported, never removed
function Get-LocalGroup { [pscustomobject]@{ Name = 'x' } }
function Get-GroupMembers([string]$Group) { if ($Group -eq 'Backup Operators') { [pscustomobject]@{ Short = 'mallory'; Full = 'PC\mallory'; IsLocal = $true; Class = 'User'; Sid = '' } } }
$script:Removed = @(); $script:AuthAdmins = @('alice'); $script:AuthUsers = @(); $script:Me = 'alice'; Reset-Results
Invoke-Users
Assert 'Users: with no README user list, group members are reported but not removed' {
    @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like "*PC\mallory*Backup Operators*" }).Count -eq 1 -and $script:Removed.Count -eq 0 }
function Get-LocalGroup { }

# Self-elevation relaunch: every path quoted, every switch passed through
$ra = Get-RelaunchArguments 'C:\My Tools\Harden.ps1' 'Apply' $true 'C:\My Files\readme config.psd1' @('users', 'passwords firewall') $true
Assert 'Relaunch: script path and config path with spaces are quoted' { $ra -contains '"C:\My Tools\Harden.ps1"' -and $ra -contains '"C:\My Files\readme config.psd1"' }
Assert 'Relaunch: -Mode, -Yes, -Quick are passed; -Only is one comma list' {
    ($ra -join ' ') -like '*-Mode Apply*' -and $ra -contains '-Yes' -and $ra -contains '-Quick' -and $ra[$ra.IndexOf('-Only') + 1] -eq '"users,passwords,firewall"' }
$ra2 = Get-RelaunchArguments 'C:\h.ps1' '' $false '' $null $false
Assert 'Relaunch: unused switches are left out' { -not ($ra2 -contains '-Mode' -or $ra2 -contains '-Yes' -or $ra2 -contains '-Config' -or $ra2 -contains '-Only' -or $ra2 -contains '-Quick') }

# Audit policy is read from the language-independent backup CSV
function auditpol.exe {
    $f = ($args | Where-Object { "$_" -like '/file:*' }) -replace '^/file:', ''
    if ($args -contains '/backup') {
        @('Machine Name,Policy Target,Subcategory,Subcategory GUID,Inclusion Setting,Exclusion Setting,Setting Value',
          'PC,System,Anmelden,{0CCE9215-69AE-11D9-BED3-505054503030},Erfolg und Fehler,,3',
          'PC,System,Abmelden,{0CCE9216-69AE-11D9-BED3-505054503030},Erfolg,,1',
          'PC,System,Kontosperrung,{0CCE9217-69AE-11D9-BED3-505054503030},Keine Überwachung,,0') | Set-Content -Path $f
    }
}
$ar = @(Get-AuditPolicyRows)
Assert 'Audit policy: 3 subcategories read by GUID even with German text' { $ar.Count -eq 3 -and $ar[0].Guid -eq '{0CCE9215-69AE-11D9-BED3-505054503030}' }
Assert 'Audit policy: only the success+failure row (value 3) is complete' { @($ar | Where-Object { $_.Value -ne 3 }).Count -eq 2 }
Remove-Item Function:\auditpol.exe

# secedit is exported once per section, not once per check
$script:ExportCount = 0
$secOrig = ${function:secedit.exe}
function secedit.exe { if ($args -contains '/export') { $script:ExportCount++ }; & $secOrig @args }
$script:SecCache = $null; $script:Mode = 'Audit'; Reset-Results
Invoke-UserRights; Invoke-UserRights
Assert 'secedit: two reads in one section cost one export (cached)' { $script:ExportCount -eq 1 }
$script:ExportCount = 0; $script:SecCache = $null; $script:Mode = 'Apply'; $script:AssumeYes = $true
Set-SecPolicy 'System Access' ([ordered]@{ MinimumPasswordLength = 14 }) 'SECURITYPOLICY' 'test' | Out-Null
Assert 'secedit: after an apply the cache is refreshed and shows the new value' { (Get-SecPolicyCached)['System Access']['MinimumPasswordLength'] -eq '14' }
$script:SecCache = $null
$script:FakePolicy['System Access']['MinimumPasswordLength'] = '12'
Remove-Item Function:\secedit.exe
function secedit.exe { & $secOrig @args }

# Scheduled tasks: Microsoft's own .vbs/.bat tasks are not "suspicious", planted ones are
Assert 'Task: Server Manager CleanupOldPerfLogs (cscript .vbs in System32) is not suspicious' {
    -not (Test-SuspiciousTask '\Microsoft\Windows\Server Manager\' '%systemroot%\system32\cscript.exe /B /nologo %systemroot%\system32\calluxxprovider.vbs $(Arg0)') }
Assert 'Task: a task hidden under \Microsoft\ that runs from C:\Windows\Temp is suspicious' {
    Test-SuspiciousTask '\Microsoft\Windows\Foo\' 'C:\Windows\Temp\run.bat' }
Assert 'Task: a .ps1 task outside \Microsoft\ is suspicious' { Test-SuspiciousTask '\' 'powershell.exe -ep bypass -File C:\Users\Public\a.ps1' }

# Firewall: README ports are opened BEFORE the profiles are switched on (a Remote Desktop session would otherwise be cut)
$script:Order = @()
function Get-NetFirewallProfile { @([pscustomobject]@{ Name = 'Domain'; Enabled = 'False'; DefaultInboundAction = 'Block'; DefaultOutboundAction = 'Allow'; LogBlocked = 'True'; NotifyOnListen = 'True' }) }
function Set-NetFirewallProfile { $script:Order += 'profile' }
function Get-NetFirewallRule { param($DisplayGroup, $Name, $Direction, $Action, $Enabled)
    if ($Name -eq 'RemoteDesktop-UserMode-In-TCP') { [pscustomobject]@{ Name = 'RemoteDesktop-UserMode-In-TCP'; Enabled = 'False'; DisplayGroup = 'Bureau a distance' } } }
function Enable-NetFirewallRule { $script:Order += 'rule:' + (@($args | ForEach-Object { $_ }) -join ',') }
Reset-Reg; Reset-Results; $script:Mode = 'Apply'; $script:Critical = @('rdp'); Invoke-Firewall
Assert 'Firewall: the Remote Desktop rule is found by its language-independent name' { ($script:Order -join ' ') -like '*rule:*RemoteDesktop-UserMode-In-TCP*' }
Assert 'Firewall: critical rules are enabled before the profile is turned on' { $script:Order.Count -ge 2 -and $script:Order[0] -like 'rule:*' -and $script:Order[1] -eq 'profile' }
$script:Critical = @()

# Remote Desktop: never switch it off from inside an RDP session without an explicit yes
$ts = 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server'
$savedSession = $env:SESSIONNAME
$env:SESSIONNAME = 'RDP-Tcp#3'; Reset-Reg; Reset-Results; $script:AssumeYes = $true; $script:Mode = 'Apply'; $script:Critical = @()
Set-FakeReg $ts 'fDenyTSConnections' 0
Invoke-RemoteAccess
Assert 'RDP: with -Yes inside an RDP session, Remote Desktop is NOT turned off' { $script:FakeReg[$ts]['fDenyTSConnections'] -eq 0 -and @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like '*connected through Remote Desktop*' }).Count -eq 1 }
$env:SESSIONNAME = 'Console'; Reset-Reg; Reset-Results
Set-FakeReg $ts 'fDenyTSConnections' 0
Invoke-RemoteAccess
Assert 'RDP: from the console, with -Yes and not in the README, it is turned off' { $script:FakeReg[$ts]['fDenyTSConnections'] -eq 1 }
$env:SESSIONNAME = $savedSession

# One-pass file walker: finds nested files, skips excluded folders and (on any OS) does not loop
$wroot = Join-Path $tmp 'walk'
foreach ($d in 'a/b', 'AppData/Local/Microsoft/x', 'keep') { Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path (Join-Path $wroot $d) -Force | Out-Null }
foreach ($f in 'top.mp3', 'a/b/deep.mp3', 'AppData/Local/Microsoft/x/skip.mp3', 'keep/k.txt') { [IO.File]::WriteAllText((Join-Path $wroot $f), 'x') }
$walked = @(Get-FilesOnePass @($wroot) '(?i)\\AppData\\Local\\Microsoft\\|/AppData/Local/Microsoft/' | ForEach-Object { $_.Name } | Sort-Object)
Assert 'Get-FilesOnePass: finds nested files and skips the excluded folder' { ($walked -join ',') -eq 'deep.mp3,k.txt,top.mp3' }


# --- v2.2.0 additions (second audit) ---------------------------------------------
# Defender's own services run from ProgramData: they must never be offered for disabling
$dv = Get-ServicePathVerdict '"C:\ProgramData\Microsoft\Windows Defender\Platform\4.18.2403.7-0\MsMpEng.exe"'
Assert 'Service path: WinDefend (ProgramData\Microsoft\Windows Defender\Platform) is trusted, not "suspicious"' { $dv.Kind -eq 'trusted' -and -not $dv.Unquoted }
Assert 'Service path: svchost group is trusted and quoted-free' { $v = Get-ServicePathVerdict 'C:\WINDOWS\system32\svchost.exe -k netsvcs -p'; $v.Kind -eq 'trusted' -and -not $v.Unquoted }
Assert 'Service path: unquoted Program Files path with spaces is flagged, with the exe and arguments split' {
    $v = Get-ServicePathVerdict 'C:\Program Files\Vuln Service\svc.exe -run'; $v.Unquoted -and $v.Exe -eq 'C:\Program Files\Vuln Service\svc.exe' -and $v.Rest -eq ' -run' }
Assert 'Service path: a quoted path with spaces is not flagged' { -not (Get-ServicePathVerdict '"C:\Program Files\Vuln Service\svc.exe" -run').Unquoted }
Assert 'Service path: an unquoted path with spaces OUTSIDE Program Files and Windows is flagged too' { (Get-ServicePathVerdict 'C:\My Tools\svc.exe').Unquoted }
Assert 'Service path: a program in a user folder is suspicious' { (Get-ServicePathVerdict 'C:\Users\Public\svc.exe').Kind -eq 'suspicious' -and (Get-ServicePathVerdict 'C:\ProgramData\evil\a.exe').Kind -eq 'suspicious' }
Assert 'Service path: cmd /c as the service program is suspicious even though cmd.exe is in Windows' { (Get-ServicePathVerdict 'C:\Windows\System32\cmd.exe /c C:\x\a.bat').Kind -eq 'suspicious' }
Assert 'Service path: a third-party service in its own folder is "unusual" (listed, not disabled by default logic)' { (Get-ServicePathVerdict 'D:\Apps\foo\foo.exe').Kind -eq 'unusual' }
Assert 'Service path: empty path gives none' { (Get-ServicePathVerdict '').Kind -eq 'none' }

# Writable service folders: Users with Modify is a finding, Users with Read and Execute is not
# SecurityIdentifier does not work off Windows, so a fake identity answers Translate() with its SID
function New-FakeIdentity([string]$Sid) { $o = [pscustomobject]@{ Sid = $Sid }; $o | Add-Member ScriptMethod Translate { param($t) [pscustomobject]@{ Value = $this.Sid } }; $o }
$sidUsers = New-FakeIdentity 'S-1-5-32-545'; $sidAdmins = New-FakeIdentity 'S-1-5-32-544'
function New-FakeAce($Sid, $Rights, $Type = 'Allow') { [pscustomobject]@{ IdentityReference = $Sid; FileSystemRights = [System.Security.AccessControl.FileSystemRights]$Rights; AccessControlType = $Type } }
Assert 'ACL: Users with Modify can change the file -> flagged' { Test-WritableByUsers ([pscustomobject]@{ Access = @((New-FakeAce $sidAdmins 'FullControl'), (New-FakeAce $sidUsers 'Modify')) }) }
Assert 'ACL: Users with Read and Execute only -> fine' { -not (Test-WritableByUsers ([pscustomobject]@{ Access = @((New-FakeAce $sidAdmins 'FullControl'), (New-FakeAce $sidUsers 'ReadAndExecute')) }) ) }
Assert 'ACL: a Deny entry for Users is not a finding' { -not (Test-WritableByUsers ([pscustomobject]@{ Access = @((New-FakeAce $sidUsers 'FullControl' 'Deny')) })) }
Assert 'ACL: Everyone with WriteData -> flagged' { Test-WritableByUsers ([pscustomobject]@{ Access = @((New-FakeAce (New-FakeIdentity 'S-1-1-0') 'WriteData')) }) }

# hosts file lines
Assert 'hosts: comments, blanks and localhost lines are normal' { -not ('', '# 127.0.0.1 bank.com', '127.0.0.1 localhost', '::1     localhost', '127.0.0.1 localhost # loopback' | Where-Object { Test-HostsLineSuspicious $_ }) }
Assert 'hosts: a redirected website is suspicious (also with a trailing comment)' { (Test-HostsLineSuspicious '10.0.0.5 windowsupdate.microsoft.com') -and (Test-HostsLineSuspicious '1.2.3.4 www.bank.com # x') -and (Test-HostsLineSuspicious '127.0.0.1 localhost bank.com') }

# A failing sub-step must not stop the steps after it (one bad COM object used to end the whole backdoors section)
$script:Mode = 'Audit'; Reset-Results; $script:StepRan = $false
Invoke-SafeStep 'first' { throw 'boom' }
Invoke-SafeStep 'second' { $script:StepRan = $true }
Assert 'Invoke-SafeStep: an error is a FAILED result and the next step still runs' { $script:StepRan -and @($script:Results | Where-Object { $_.Status -eq 'FAILED' -and $_.Text -like 'first stopped early*' }).Count -eq 1 }

# One typed admin name must stay an array (+= glued "alice" and "carol" into "alicecarol")
$script:AuthAdmins = 'alice'; $script:AuthUsers = ''; $script:Critical = 'rdp'; $script:Me = 'carol'
Complete-ReadmeInfo
Assert 'README: a single typed name is still a list, and the logged-in user is appended as its own entry' { $script:AuthAdmins.Count -eq 2 -and $script:AuthAdmins[0] -eq 'alice' -and $script:AuthAdmins[1] -eq 'carol' }
$script:AuthAdmins = @('alice'); $script:AuthUsers = @('carol'); $script:Critical = @(); $script:Me = 'alice'

# Config files with odd content
$odd = Join-Path $tmp 'odd [1].psd1'
[IO.File]::WriteAllText($odd, "@{ AuthorizedAdmins = 'alice'; AuthorizedUsers = @('John Smith', 'carol'); EnableLockout = `$false; InstallUpdates = 'maybe'; NewPassword = 12345 }")
Import-ReadmeConfig $odd
Assert 'Config: one string, a name with a space, $false for EnableLockout, a bad InstallUpdates and a numeric password all load' {
    $script:AuthAdmins.Count -eq 1 -and $script:AuthUsers -contains 'John Smith' -and $script:EnableLockout -eq 'no' -and $script:InstallUpdates -eq 'ask' -and $script:NewPassword -eq '12345' }
[IO.File]::WriteAllText($odd, "@{ CriticalServices = 'rdp IIS' }")
$script:EnableLockout = 'yes'; $script:InstallUpdates = 'ask'; $script:NewPassword = ''
Import-ReadmeConfig $odd
Assert 'Config: missing keys leave the defaults; critical keywords are lower-cased and split' { $script:AuthAdmins.Count -eq 0 -and $script:AuthUsers.Count -eq 0 -and ($script:Critical -join ',') -eq 'rdp,iis' -and $script:EnableLockout -eq 'yes' }
[IO.File]::WriteAllText($odd, "@('alice','bob')")
Assert 'Config: a file that is not a hashtable is an error the caller reports (not a crash)' { try { Import-ReadmeConfig $odd; $false } catch { "$($_.Exception.Message)".Length -gt 0 } }
[IO.File]::WriteAllText($odd, "@{ AuthorizedAdmins = @('alice',) }")
Assert 'Config: a trailing comma is an error the caller reports (not a crash)' { try { Import-ReadmeConfig $odd; $false } catch { $true } }
$script:AuthAdmins = @('alice'); $script:AuthUsers = @('carol'); $script:Critical = @()


# Services: one Get-Service for the whole catalog; refused Set-Service falls back to the registry Start value
function Set-ItemProperty { param($Path, $LiteralPath, $Name, $Value, $Type)
    $p = if ($LiteralPath) { $LiteralPath } else { $Path }
    if (-not $script:FakeReg.ContainsKey($p)) { throw "Cannot find path '$p'" }
    $script:FakeReg[$p][$Name] = $Value }
$script:GsCalls = 0; $script:SvcSet = @{}
function New-FakeService($Name, $Status, $Start) { [pscustomobject]@{ Name = $Name; DisplayName = $Name; Status = $Status; StartType = $Start } }
function Get-Service { param($Name) $script:GsCalls++
    @((New-FakeService 'RemoteRegistry' 'Running' 'Automatic'), (New-FakeService 'Spooler' 'Running' 'Automatic'), (New-FakeService 'WinDefend' 'Stopped' 'Disabled'),
      (New-FakeService 'EventLog' 'Running' 'Automatic'), (New-FakeService 'NTDS' 'Running' 'Automatic')) | Where-Object { -not $Name -or $_.Name -eq $Name } }
function Set-Service { param($Name, $StartupType) $script:SvcSet[$Name] = "$StartupType" }
function Stop-Service { }
function Start-Service { }
Reset-Reg; Reset-Results; $script:Mode = 'Apply'; $script:AssumeYes = $true; $script:Critical = @('print'); $script:IsDC = $false
Invoke-Services
Assert 'Services: the whole catalog costs one Get-Service call' { $script:GsCalls -eq 1 }
Assert 'Services: Remote Registry is disabled, the README-critical Print Spooler is kept' { $script:SvcSet['RemoteRegistry'] -eq 'Disabled' -and -not $script:SvcSet.ContainsKey('Spooler') }
Assert 'Services: a disabled Defender service is switched back on' { $script:SvcSet['WinDefend'] -eq 'Automatic' }
function Set-Service { throw 'Access is denied' }
Set-FakeReg 'HKLM:\SYSTEM\CurrentControlSet\Services\mpssvc' 'Start' 4
Set-ServiceStartMode 'mpssvc' 'Automatic'
Assert 'Set-ServiceStartMode: a refused Set-Service falls back to the registry Start value (2 = Automatic)' { $script:FakeReg['HKLM:\SYSTEM\CurrentControlSet\Services\mpssvc']['Start'] -eq 2 }
Assert 'Set-ServiceStartMode: no service key and a refusal -> the error is thrown' { try { Set-ServiceStartMode 'nosuchsvc' 'Disabled'; $false } catch { $true } }
$script:Critical = @()

# Cached logons: "4 or fewer" - lower values are left alone, higher ones are lowered
$wlk = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
Reset-Reg; Reset-Results; Set-FakeReg $wlk 'CachedLogonsCount' '2'; Invoke-SecurityOptions
Assert 'Security: CachedLogonsCount 2 stays 2 (never raised to 4)' { $script:FakeReg[$wlk]['CachedLogonsCount'] -eq '2' }
Reset-Reg; Reset-Results; Set-FakeReg $wlk 'CachedLogonsCount' '10'; Invoke-SecurityOptions
Assert 'Security: CachedLogonsCount 10 is lowered to 4' { $script:FakeReg[$wlk]['CachedLogonsCount'] -eq '4' }
Assert 'Security: SMBv1 is switched off in the registry too' { $script:FakeReg['HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters']['SMB1'] -eq 0 }
function Get-ExecutionPolicy { 'RemoteSigned' }
function bcdedit.exe { 'nx    OptIn' }
Reset-Reg; Reset-Results; Invoke-Misc
Assert 'Misc: WPAD is turned off in both the Internet Settings key and the policy key' {
    $script:FakeReg['HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings\WinHttp']['DisableWpad'] -eq 1 -and $script:FakeReg['HKLM:\SOFTWARE\Policies\Microsoft\Windows\WinHttp']['DisableWpad'] -eq 1 }
Assert 'Misc: LLMNR off and nothing FAILED (the Registry:: provider paths of other users do not exist off Windows)' { $script:FakeReg['HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient']['EnableMulticast'] -eq 0 -and -not @($script:Results | Where-Object { $_.Status -eq 'FAILED' -and $_.Text -notlike '*HKEY_USERS*' }).Count }


# Hacking-tool names: real tools match, ordinary documents do not (with -Yes they would be deleted)
Assert 'Tool names: nc.exe, mimikatz_x64.exe, john.exe, hashcat.exe, hydra.exe, xmrig.zip, cain.exe are tools' {
    -not @('nc.exe', 'mimikatz_x64.exe', 'john.exe', 'john-the-ripper-1.9.zip', 'hashcat.exe', 'hydra.exe', 'xmrig-6.zip', 'cain.exe', 'psexec64.exe', 'my-backdoor.ps1' | Where-Object { -not (Test-ToolFileName $_) }).Count }
Assert 'Tool names: john_smith_taxes.zip, hydration.py, johnny.zip, determiner.zip, cainsville.zip, miner.py are NOT tools' {
    -not @('john_smith_taxes.zip', 'hydration.py', 'johnny.zip', 'determiner.zip', 'cainsville.zip', 'notes.py', 'minerals.zip' | Where-Object { Test-ToolFileName $_ }).Count }
$wroot2 = Join-Path $tmp 'walk2'
Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path (Join-Path $wroot2 'x') -Force | Out-Null
foreach ($f in 'a.MP3', 'x/b.txt', 'x/c.log', 'x/d.dat') { [IO.File]::WriteAllText((Join-Path $wroot2 $f), 'x') }
Assert 'Get-FilesOnePass -Extensions: only the wanted extensions are handed on (case-insensitive), nothing else is kept in memory' {
    (@(Get-FilesOnePass @($wroot2) $null @('.mp3', '.txt') | ForEach-Object { $_.Name } | Sort-Object) -join ',') -eq 'a.MP3,b.txt' }
Assert 'Get-FilesOnePass: an unreadable or missing root is skipped without an error' { @(Get-FilesOnePass @((Join-Path $tmp 'does-not-exist')) $null).Count -eq 0 }


# Firewall: custom inbound rules use two bulk filter queries, not one WMI call per rule
$script:Bulk = 0; $script:Piped = 0
$fwRules = @(
    [pscustomobject]@{ Name = 'r1'; InstanceID = 'r1'; DisplayName = 'Nice app'; DisplayGroup = $null },
    [pscustomobject]@{ Name = 'r2'; InstanceID = 'r2'; DisplayName = 'Backdoor'; DisplayGroup = $null },
    [pscustomobject]@{ Name = 'r3'; InstanceID = 'r3'; DisplayName = 'Allow everything'; DisplayGroup = $null })
function Get-NetFirewallRule { param($DisplayGroup, $Name, $Direction, $Action, $Enabled) if ($Action -eq 'Allow') { $fwRules } }
function Get-NetFirewallApplicationFilter { param([Parameter(ValueFromPipeline = $true)]$InputObject, [switch]$All)
    process { if ($All) { $script:Bulk++; [pscustomobject]@{ InstanceID = 'r1'; Program = 'C:\Program Files\Nice\nice.exe' }; [pscustomobject]@{ InstanceID = 'r2'; Program = 'C:\Users\Public\nc.exe' }; [pscustomobject]@{ InstanceID = 'r3'; Program = 'Any' } } else { $script:Piped++ } } }
function Get-NetFirewallPortFilter { param([Parameter(ValueFromPipeline = $true)]$InputObject, [switch]$All)
    process { if ($All) { $script:Bulk++; [pscustomobject]@{ InstanceID = 'r1'; LocalPort = '8080'; Protocol = 'TCP' }; [pscustomobject]@{ InstanceID = 'r2'; LocalPort = '4444'; Protocol = 'TCP' }; [pscustomobject]@{ InstanceID = 'r3'; LocalPort = 'Any'; Protocol = 'Any' } } else { $script:Piped++ } } }
$script:Disabled = @(); function Disable-NetFirewallRule { param($Name) $script:Disabled += $Name }
function Get-NetFirewallProfile { @([pscustomobject]@{ Name = 'Domain'; Enabled = 'True'; DefaultInboundAction = 'Block'; DefaultOutboundAction = 'Allow'; LogBlocked = 'True'; NotifyOnListen = 'True' }) }
Reset-Reg; Reset-Results; $script:Mode = 'Apply'; $script:AssumeYes = $true; $script:Critical = @()
Invoke-Firewall
Assert 'Firewall: 3 custom rules cost 2 bulk filter queries and no per-rule queries' { $script:Bulk -eq 2 -and $script:Piped -eq 0 }
Assert 'Firewall: the netcat-path rule and the allow-everything rule are disabled, the normal app rule is only listed' {
    ($script:Disabled -contains 'r2') -and ($script:Disabled -contains 'r3') -and ($script:Disabled -notcontains 'r1') }

# Timing: every section is timed and the slowest ones show in the summary
function Invoke-FakeSlow { Start-Sleep -Milliseconds 30 }
$realSections = $Sections; $Sections = @(@{ Id = 'fake'; Title = 'Fake section'; Fn = 'Invoke-FakeSlow' })
$script:StartTime = Get-Date; $script:Timings = New-Object System.Collections.Generic.List[object]
Invoke-Section 'fake'
$Sections = $realSections
Assert 'Timing: Invoke-Section records the section id and its seconds' { $script:Timings.Count -eq 1 -and $script:Timings[0].Section -eq 'fake' -and $script:Timings[0].Seconds -ge 0 }
Assert 'Timing: a section that throws is still timed and reported FAILED' {
    function Invoke-FakeBroken { throw 'x' }
    $Sections = @(@{ Id = 'broken'; Title = 'Broken'; Fn = 'Invoke-FakeBroken' }); Reset-Results; Invoke-Section 'broken'
    $Sections = $realSections
    $script:Timings.Count -eq 2 -and @($script:Results | Where-Object Status -eq 'FAILED').Count -eq 1 }


# DHCP server role: audit log on, scopes and the options that redirect clients are listed
$script:DhcpAudit = $false
function Get-Service { param($Name) if ($Name -eq 'DHCPServer') { New-FakeService 'DHCPServer' 'Running' 'Automatic' } }
function Get-DhcpServerAuditLog { [pscustomobject]@{ Enable = $script:DhcpAudit } }
function Set-DhcpServerAuditLog { param($Enable) $script:DhcpAudit = [bool]$Enable }
function Get-DhcpServerv4Scope { [pscustomobject]@{ ScopeId = '10.0.0.0'; Name = 'LAN'; StartRange = '10.0.0.10'; EndRange = '10.0.0.200'; State = 'Active' } }
function Get-DhcpServerv4OptionValue { param($ScopeId) if ($ScopeId) { [pscustomobject]@{ OptionId = 6; Name = 'DNS Servers'; Value = @('6.6.6.6') } } else { [pscustomobject]@{ OptionId = 3; Name = 'Router'; Value = @('10.0.0.1') } } }
Reset-Results; $script:Mode = 'Apply'; $script:AssumeYes = $true; $script:Critical = @('dhcp'); $script:IsDC = $false; $script:HasAD = $false
Invoke-Roles
Assert 'DHCP: audit logging is switched on' { $script:DhcpAudit }
Assert 'DHCP: the planted DNS server option (006) and the router option (003) are reported' {
    @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like 'DHCP option 6*6.6.6.6*' }).Count -eq 1 -and @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like 'DHCP option 3*' }).Count -eq 1 }
Assert 'DHCP: the scope is listed for checking against the README' { @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like 'DHCP scope 10.0.0.0*' }).Count -eq 1 }
$script:Critical = @()

# Cleared event logs are reported (event 1102 in Security, 104 in System)
function Get-WinEvent { param($FilterHashtable, $MaxEvents)
    if ($FilterHashtable.LogName -eq 'Security') { [pscustomobject]@{ TimeCreated = [datetime]'2026-03-01 10:00'; Id = 1102 } } else { throw 'No events were found that match the specified selection criteria.' } }
$cl = @(Get-LogClearedEvents)
Assert 'Cleared logs: a Security 1102 event is found, a System log without 104 is not an error' { $cl.Count -eq 1 -and $cl[0].Log -eq 'Security' -and $cl[0].Id -eq 1102 }
Remove-Item Function:\Get-WinEvent


# Defender: switches outside the policy keys, exclusions (the scoring client's own is kept), third-party antivirus
$script:RemovedEx = @()
function Get-Service { param($Name) if ($Name -eq 'WinDefend') { New-FakeService 'WinDefend' 'Running' 'Automatic' } }
function Get-MpPreference { [pscustomobject]@{ DisableRealtimeMonitoring = $false; DisableBehaviorMonitoring = $false; DisableIOAVProtection = $false; PUAProtection = 1; MAPSReporting = 2; SubmitSamplesConsent = 1
    EnableNetworkProtection = 1; ExclusionPath = @('C:\Users\Public\tools', 'C:\CyberPatriot\CCSClient.exe'); ExclusionExtension = @(); ExclusionProcess = @('evil.exe') } }
function Remove-MpPreference { param($ExclusionPath, $ExclusionExtension, $ExclusionProcess) $script:RemovedEx += @($ExclusionPath, $ExclusionExtension, $ExclusionProcess | Where-Object { $_ }) }
function Set-MpPreference { }
function Get-MpComputerStatus { [pscustomobject]@{ IsTamperProtected = $true; AntivirusSignatureAge = 0 } }
function Update-MpSignature { }
function Get-CimInstance { param([Parameter(Position = 0)]$ClassName, $Namespace) if ($ClassName -eq 'AntiVirusProduct') { [pscustomobject]@{ displayName = 'Windows Defender' }; [pscustomobject]@{ displayName = 'ContosoAV' } } }
Reset-Reg; Reset-Results; $script:Mode = 'Apply'; $script:AssumeYes = $true
Set-FakeReg 'HKLM:\SOFTWARE\Microsoft\Windows Defender' 'DisableAntiSpyware' 1
Invoke-Defender
Assert 'Defender: DisableAntiSpyware = 1 outside the policy key is removed' { -not $script:FakeReg['HKLM:\SOFTWARE\Microsoft\Windows Defender'].Contains('DisableAntiSpyware') }
Assert 'Defender: a planted exclusion is removed, the CyberPatriot client exclusion is kept' {
    $script:RemovedEx -contains 'C:\Users\Public\tools' -and $script:RemovedEx -contains 'evil.exe' -and $script:RemovedEx -notcontains 'C:\CyberPatriot\CCSClient.exe' }
Assert 'Defender: a registered third-party antivirus is reported (Defender itself is not)' {
    @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like '*ContosoAV*' }).Count -eq 1 -and @($script:Results | Where-Object { $_.Text -like '*Another antivirus*Windows Defender*' }).Count -eq 0 }
Remove-Item Function:\Get-CimInstance


# --- Backdoors section end to end, with a fake registry, fake tasks, fake services and a real hosts file ---------------
$savedRoot = $env:SystemRoot; $savedDrive = $env:SystemDrive; $savedPD = $env:ProgramData
$env:SystemRoot = Join-Path $tmp 'win'; $env:SystemDrive = Join-Path $tmp 'sysdrive'; $env:ProgramData = Join-Path $tmp 'pd'
$hostsDir = Join-Path $env:SystemRoot 'System32/drivers/etc'
Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path $hostsDir -Force | Out-Null
Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path (Join-Path $env:SystemDrive 'Users') -Force | Out-Null
$hostsFile = Join-Path $hostsDir 'hosts'
Set-Content -Path $hostsFile -Value @('# Copyright (c) Microsoft', '127.0.0.1 localhost # loopback', '', '10.9.9.9 windowsupdate.microsoft.com')
function Get-ChildItem {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$Path, [string]$LiteralPath, [switch]$Directory, [switch]$File, [switch]$Force, [switch]$Recurse, [string]$Filter)
    $p = if ($LiteralPath) { $LiteralPath } else { $Path }
    if ($p -match '^HK') {
        foreach ($k in @($script:FakeReg.Keys | Where-Object { $_ -like "$p\*" -and ($_.Substring($p.Length + 1) -notmatch '\\') })) {
            $o = [pscustomobject]@{ PSChildName = $k.Substring($p.Length + 1); PSPath = $k; Vals = $script:FakeReg[$k] }
            $o | Add-Member ScriptMethod GetValue { param($n) if ($this.Vals.Contains($n)) { $this.Vals[$n] } else { $null } }
            $o
        }
        return
    }
    Microsoft.PowerShell.Management\Get-ChildItem @PSBoundParameters
}
function Get-ScheduledTask { @(
    [pscustomobject]@{ TaskPath = '\'; TaskName = 'Updater'; Actions = @([pscustomobject]@{ Execute = 'powershell.exe'; Arguments = '-w hidden -enc SQBFAFgA' }) },
    [pscustomobject]@{ TaskPath = '\Microsoft\Windows\Defrag\'; TaskName = 'ScheduledDefrag'; Actions = @([pscustomobject]@{ Execute = '%windir%\system32\defrag.exe'; Arguments = '-c -h' }) }) }
function Unregister-ScheduledTask { param($TaskName, $TaskPath, $Confirm) $script:TaskGone += $TaskName }
function Export-ScheduledTask { 'xml' }
function Get-CimInstance { param([Parameter(Position = 0)]$ClassName, $Namespace)
    if ($ClassName -eq 'Win32_Service') {
        @([pscustomobject]@{ Name = 'WinDefend'; DisplayName = 'Microsoft Defender Antivirus Service'; PathName = '"C:\ProgramData\Microsoft\Windows Defender\Platform\4.18.2403.7-0\MsMpEng.exe"' },
          [pscustomobject]@{ Name = 'WdNisSvc'; DisplayName = 'Defender Network Inspection'; PathName = '"C:\ProgramData\Microsoft\Windows Defender\Platform\4.18.2403.7-0\NisSrv.exe"' },
          [pscustomobject]@{ Name = 'evilsvc'; DisplayName = 'Evil'; PathName = 'C:\Users\Public\evil.exe' },
          [pscustomobject]@{ Name = 'vulnsvc'; DisplayName = 'Vulnerable'; PathName = 'C:\Program Files\Vuln Service\svc.exe -run' },
          [pscustomobject]@{ Name = 'NTDS'; DisplayName = 'AD DS'; PathName = 'C:\Program Files\Some Path\x.exe' }) } }
function Get-Acl { param($LiteralPath, $ErrorAction) [pscustomobject]@{ Access = @((New-FakeAce $sidUsers 'Modify')) } }
function Get-NetTCPConnection { @([pscustomobject]@{ LocalPort = 4444; LocalAddress = '0.0.0.0'; OwningProcess = 99999 }) }
function Get-Process { param($Id) [pscustomobject]@{ ProcessName = 'nc' } }
$script:StoppedPids = @(); function Stop-Process { param($Id) $script:StoppedPids += $Id }
$script:TaskGone = @(); $script:SvcSet = @{}
function Set-Service { param($Name, $StartupType) $script:SvcSet[$Name] = "$StartupType" }
Reset-Reg; Reset-Results; $script:Mode = 'Apply'; $script:AssumeYes = $true; $script:IsDC = $true
Set-FakeReg 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' 'Updater' 'powershell.exe -w hidden -enc SQBFAFgA'
Set-FakeReg 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' 'OneDrive' '"C:\Program Files\Microsoft OneDrive\OneDrive.exe" /background'
Set-FakeReg 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\sethc.exe' 'Debugger' 'C:\Windows\System32\cmd.exe'
Set-FakeReg 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\utilman.exe' 'Debugger' 'C:\Windows\System32\cmd.exe'
Set-FakeReg 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' 'Taskman' 'C:\Users\Public\tm.exe'
Set-FakeReg 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' 'Userinit' 'C:\Windows\system32\userinit.exe,'
Set-FakeReg 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\SpecialAccounts\UserList' 'ghost' 0
Set-FakeReg 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' 'Security Packages' ([string[]]@('kerberos', 'mimilib'))
Set-FakeReg 'HKLM:\SYSTEM\CurrentControlSet\Services\vulnsvc' 'ImagePath' 'C:\Program Files\Vuln Service\svc.exe -run'
Invoke-Backdoors
Assert 'Backdoors: nothing FAILED (every step ran to the end)' { -not @($script:Results | Where-Object { $_.Status -eq 'FAILED' }).Count }
Assert 'Backdoors: the suspicious Run entry is deleted, OneDrive stays' { -not $script:FakeReg['HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run'].Contains('Updater') -and $script:FakeReg['HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run'].Contains('OneDrive') }
Assert 'Backdoors: Debugger hijacks are removed in both the 64-bit and the Wow6432Node Image File Execution Options' {
    -not $script:FakeReg['HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\sethc.exe'].Contains('Debugger') -and
    -not $script:FakeReg['HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\utilman.exe'].Contains('Debugger') }
Assert 'Backdoors: Winlogon Taskman is removed; a hidden account list and the mimilib LSA package are reported' {
    -not $script:FakeReg['HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'].Contains('Taskman') -and
    @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like '*SpecialAccounts*ghost*' }).Count -eq 1 -and @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like '*mimilib*' }).Count -eq 1 }
Assert 'Backdoors: the planted task is deleted, the Microsoft defrag task is not' { $script:TaskGone -contains 'Updater' -and $script:TaskGone -notcontains 'ScheduledDefrag' }
Assert 'Backdoors: Defender services (ProgramData\Microsoft\Windows Defender) are NOT disabled; the Public\evil.exe service is' {
    $script:SvcSet['evilsvc'] -eq 'Disabled' -and -not $script:SvcSet.ContainsKey('WinDefend') -and -not $script:SvcSet.ContainsKey('WdNisSvc') }
Assert 'Backdoors: the unquoted service path is quoted in the registry' { $script:FakeReg['HKLM:\SYSTEM\CurrentControlSet\Services\vulnsvc']['ImagePath'] -eq '"C:\Program Files\Vuln Service\svc.exe" -run' }
Assert 'Backdoors: on a Domain Controller an NTDS path is never rewritten' { @($script:Results | Where-Object { $_.Text -like '*Quoted the path of service NTDS*' }).Count -eq 0 }
Assert 'Backdoors: a writable service folder is reported' { @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like '*ordinary users can change*' }).Count -eq 1 }
Assert 'Backdoors: the redirected hosts line is commented out, the loopback line is kept, the file is backed up' {
    $h = Get-Content -LiteralPath $hostsFile; ($h -contains '127.0.0.1 localhost # loopback') -and ($h -contains '# disabled by harden.ps1: 10.9.9.9 windowsupdate.microsoft.com') -and (Microsoft.PowerShell.Management\Test-Path -LiteralPath (Join-Path $BackupDir 'hosts')) }
Assert 'Backdoors: a netcat listener is stopped' { $script:StoppedPids -contains 99999 }
Reset-Results; $script:Mode = 'Audit'
Set-FakeReg 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' 'Updater' 'powershell.exe -w hidden -enc SQBFAFgA'
Set-FakeReg 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\sethc.exe' 'Debugger' 'C:\Windows\System32\cmd.exe'
$script:TaskGone = @(); $script:StoppedPids = @(); $script:SvcSet = @{}
Invoke-Backdoors
Assert 'Backdoors: Audit mode changes nothing (registry, tasks, services, processes)' {
    $script:FakeReg['HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run'].Contains('Updater') -and $script:FakeReg['HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\sethc.exe'].Contains('Debugger') -and
    $script:TaskGone.Count -eq 0 -and $script:StoppedPids.Count -eq 0 -and $script:SvcSet.Count -eq 0 }
$script:IsDC = $false
Remove-Item Function:\Get-CimInstance
$env:SystemRoot = $savedRoot; $env:SystemDrive = $savedDrive; $env:ProgramData = $savedPD


# One file that cannot be deleted must not stop the others
$gdir = Join-Path $tmp 'gone'; Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path $gdir -Force | Out-Null
$g1 = Join-Path $gdir 'a.mp3'; $g3 = Join-Path $gdir 'c.mp3'; [IO.File]::WriteAllText($g1, 'x'); [IO.File]::WriteAllText($g3, 'x')
$threw = $false; try { Remove-FileList @($g1, (Join-Path $gdir 'missing.mp3'), $g3) } catch { $threw = "$($_.Exception.Message)" -like '1 of 3*' }
Assert 'Remove-FileList: a file that cannot be deleted is reported at the end, the other files are still deleted' { $threw -and -not (Microsoft.PowerShell.Management\Test-Path -LiteralPath $g1) -and -not (Microsoft.PowerShell.Management\Test-Path -LiteralPath $g3) }


# LocalAccountTokenFilterPolicy: only a planted 1 is changed, never when the README lists WinRM
$sysk = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
Reset-Reg; Reset-Results; $script:Mode = 'Apply'; $script:Critical = @(); Set-FakeReg $sysk 'LocalAccountTokenFilterPolicy' 1; Invoke-SecurityOptions
Assert 'Security: a planted LocalAccountTokenFilterPolicy = 1 is set back to 0' { $script:FakeReg[$sysk]['LocalAccountTokenFilterPolicy'] -eq 0 }
Reset-Reg; Reset-Results; $script:Critical = @('winrm'); Set-FakeReg $sysk 'LocalAccountTokenFilterPolicy' 1; Invoke-SecurityOptions
Assert 'Security: with WinRM in the README the value 1 is kept and reported' { $script:FakeReg[$sysk]['LocalAccountTokenFilterPolicy'] -eq 1 -and @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like 'LocalAccountTokenFilterPolicy*' }).Count -eq 1 }
Reset-Reg; Reset-Results; $script:Critical = @(); Invoke-SecurityOptions
Assert 'Security: a clean system gets no LocalAccountTokenFilterPolicy value written' { -not $script:FakeReg[$sysk].Contains('LocalAccountTokenFilterPolicy') }


# Windows Home / no secedit: the password numbers go through "net accounts", complexity is left for a human, nothing crashes
$secGood = ${function:secedit.exe}
function secedit.exe { throw 'The term secedit.exe is not recognized as a name of a cmdlet, function, script file, or executable program.' }
$script:NetArgs = @(); $global:LASTEXITCODE = 0
function net.exe { $script:NetArgs += ,@($args); $global:LASTEXITCODE = 0; if ($args.Count -eq 1 -and $args[0] -eq 'accounts') { 'Minimum password length: 0' } }
$script:SecCache = $null; $script:Mode = 'Apply'; $script:AssumeYes = $true; $script:EnableLockout = 'yes'; Reset-Results
Invoke-Passwords
Assert 'No secedit: the password policy is set with net accounts (history 24, max 90, min 1, length 12, lockout 5/30/30)' {
    $call = @($script:NetArgs | Where-Object { $_.Count -gt 1 -and $_[0] -eq 'accounts' })[0]
    "$call" -like '*/uniquepw:24*/maxpwage:90*/minpwage:1*/minpwlen:12*/lockoutthreshold:5*/lockoutduration:30*/lockoutwindow:30*' }
Assert 'No secedit: complexity is a REVIEW for the human, and there is no FAILED' {
    @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like '*complexity*' }).Count -eq 1 -and -not @($script:Results | Where-Object Status -eq 'FAILED').Count }
$script:SecCache = $null; Reset-Results; Invoke-UserRights
Assert 'No secedit: user rights say "could not check" (REVIEW) instead of claiming they look normal' { @($script:Results | Where-Object { $_.Status -eq 'REVIEW' -and $_.Text -like 'Cannot read the user rights*' }).Count -eq 1 -and -not @($script:Results | Where-Object Status -eq 'OK').Count }
$script:SecCache = $null; Reset-Results; $script:NetArgs = @(); $script:Mode = 'Audit'
Invoke-Passwords
Assert 'No secedit, Audit mode: net accounts is only read, never set' { -not @($script:NetArgs | Where-Object { $_.Count -gt 1 }).Count -and @($script:Results | Where-Object Status -eq 'WOULD').Count -eq 1 }
Remove-Item Function:\net.exe; Remove-Item Function:\secedit.exe
function secedit.exe { & $secGood @args }
$script:SecCache = $null; $script:Mode = 'Apply'


# Group membership fallback (net localgroup) on a German Windows: the closing line is not a member
$gm = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $args[0].Name -eq 'Get-GroupMembers' }, $false)[0].Extent.Text -replace 'function Get-GroupMembers', 'function Get-GroupMembersReal'
. ([scriptblock]::Create($gm))
function Get-LocalGroupMember { throw 'Failed to compare two elements in the array (orphaned SID)' }
function net.exe { @('Aliasname     Administratoren', 'Kommentar', '', 'Mitglieder', '', '-------------------------------------------------------------------------------', 'Administrator', 'PC\alice', ('Der Befehl wurde erfolgreich ausgef' + [char]0xFC + 'hrt.'), '') }
$gmem = @(Get-GroupMembersReal 'Administratoren')
Assert 'Group members (net localgroup fallback): members are listed, the localized "command completed" line is not one of them' {
    $gmem.Count -eq 2 -and $gmem[0].Short -eq 'Administrator' -and $gmem[1].Short -eq 'alice' }
Remove-Item Function:\net.exe; Remove-Item Function:\Get-LocalGroupMember


# RDP left on although the README does not list it: NLA is still required
$rdpk = 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp'
$env:SESSIONNAME = 'RDP-Tcp#3'; Reset-Reg; Reset-Results; $script:Critical = @(); $script:AssumeYes = $true; $script:Mode = 'Apply'
Set-FakeReg $ts 'fDenyTSConnections' 0; Set-FakeReg $rdpk 'UserAuthentication' 0
Invoke-RemoteAccess
Assert 'RDP left on (inside an RDP session): Network Level Authentication is switched on' { $script:FakeReg[$rdpk]['UserAuthentication'] -eq 1 }
$env:SESSIONNAME = 'Console'; Reset-Reg; Reset-Results; Set-FakeReg $ts 'fDenyTSConnections' 0; Invoke-RemoteAccess
Assert 'RDP turned off from the console: no NLA change is made' { $script:FakeReg[$ts]['fDenyTSConnections'] -eq 1 -and -not (($script:FakeReg[$rdpk]) -and $script:FakeReg[$rdpk].Contains('UserAuthentication')) }
$env:SESSIONNAME = $savedSession

Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
[Console]::WriteLine('')
[Console]::WriteLine("Windows logic tests: $pass passed, $fail failed")
if ($fail -gt 0) { exit 1 }
