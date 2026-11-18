# Windows Server checklist (2016 / 2019 / 2022)

Windows Server 2022 is in **Round 2, the State round and the Semifinals** this season.

This page is complete on its own and covers the same ground as the [Windows 10/11](windows-10-11.md), [Linux Mint](linux-mint.md) and [Debian](debian.md) checklists, plus the **server roles** that make servers harder (Active Directory, DNS, IIS, FTP, DHCP, file shares). Where a step says "same as Windows 10/11", the commands are the same; that checklist just explains them in more detail.

**How to use this page:** work top to bottom. On a Domain Controller, users and policy live in Active Directory and Group Policy — the local tools do nothing. The script `scripts/windows/Harden.ps1` detects servers and Domain Controllers automatically.

---

## 0. Before you touch anything

### 0.1 Read the README twice
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

Servers usually have **critical services** (AD, DNS, IIS, FTP, file shares) and forbidden software. Write every one down before you change anything. See [Reading the README](../start-here/reading-the-readme.md).

### 0.2 Take a snapshot
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**Clicking:** In VMware: **VM → Snapshot → Take Snapshot…**, name it "start".

> [!TIP]
> Take another snapshot whenever the score goes up a lot. If a GPO or service change breaks something, **VM → Snapshot → Revert**; the scoring engine keeps the points you already earned.

### 0.3 Open PowerShell as Administrator
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**Clicking:** **Start → Windows PowerShell → Run as Administrator** (Server Core: you are already at an admin prompt).

**Typing:**
```powershell
whoami /groups | Select-String 'S-1-5-32-544'    # prints the Administrators line = you are elevated
$PSVersionTable.PSVersion                         # 5.1 on 2016-2022
```

### 0.4 Open the Scoring Report
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

Double-click **Scoring Report** on the desktop and keep it open in a browser tab. On Server Core, note the score from the report file instead.

### 0.5 Answer the forensics questions first
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** Open each `Forensics Question N.txt` on the desktop, find the answer, type it after `ANSWER:` and save. Do this **before** deleting users, files or services — the evidence is often one of them.

**Typing (the usual tools):**
```powershell
Get-ChildItem C:\ -Recurse -Filter '*secret*' -ErrorAction SilentlyContinue     # find a file by name
Select-String -Path C:\Users\*\* -Pattern 'password' -List -ErrorAction SilentlyContinue
Get-FileHash C:\path\to\file -Algorithm SHA256
certutil -decode encoded.txt decoded.bin                                          # decode base64
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624} -MaxEvents 20         # logons
```

More techniques: [Forensics questions guide](../guides/forensics-questions.md).

> [!WARNING]
> Answers must be **exact**: spelling, capitals, and full paths when asked. Don't delete the `ANSWER:` line.

---

## 1. Is this a Domain Controller?

### 1.1 Find out what kind of server it is
- [ ] Done

**Script:** 🔎 The script detects a Domain Controller by itself (it prints the Role at the top); still list the installed roles so you know what's there.

**Why it matters:** On a **Domain Controller** (DC), users and password rules live in **Active Directory** and **Group Policy**, not on the local computer. If you change the local settings on a DC, nothing happens.

**Clicking:** **Server Manager → Dashboard**. If **AD DS** appears in the left list, it's a Domain Controller. **Server Manager → Local Server** also shows **Domain:** if the computer is in a domain.

**Typing:**
```powershell
(Get-CimInstance Win32_OperatingSystem).ProductType    # 1 = workstation, 2 = DOMAIN CONTROLLER, 3 = server
Get-WindowsFeature | Where-Object Installed | Select-Object Name, DisplayName     # every installed role
```

| ProductType | Users are in | Password policy is in |
|---|---|---|
| **2 (Domain Controller)** | Active Directory Users and Computers (`dsa.msc`) | **Default Domain Policy** (Group Policy, `gpmc.msc`) |
| **3 (member or standalone server)** | Local Users and Groups (`lusrmgr.msc`) | Local Security Policy (`secpol.msc`) |

The `*-AD*`, `*-GPO` and `*-DnsServer*` commands on this page come with the AD DS and DNS roles, so they work on a Domain Controller. On other servers they fail unless those tools are installed; use the "Standalone / member server" steps there.

### 1.2 Fast path: run the hardening script
- [ ] Done

**What:** After the forensics questions are answered, run `Harden.ps1`: Audit mode first, then Apply mode. The commands are in [Windows 10/11 step 1.2](windows-10-11.md#12-fast-path-run-the-hardening-script). Put every critical service from the README into the config (keywords like `ad`, `dns`, `iis`, `ftp`, `smb`, `rdp`).

**Why it matters:** The script detects servers and Domain Controllers by itself. On a DC it works on the **domain** users, the Default Domain Policy and the DNS zones, and it **never** disables Active Directory, DNS, Netlogon, Kerberos or the other services in 6.2.

**Check it worked:** The top of the output says `Role: Domain Controller` or `Role: Server`. The Scoring Report went up. Every line in `C:\harden-toolkit\findings-*.txt` is a job for you.

Now skip every step marked **Script: ✅** below (on the website, press **Tick the script's ✅ steps** at the top of the page). Do the 🔎 and ✋ steps.

> [!WARNING]
> - Any `FAILED` line in the summary: do that step by hand.
> - If the score **drops**, undo the change from `C:\harden-toolkit\backups\` (see [Using the scripts](../start-here/using-the-scripts.md)).
> - The Windows script **hasn't been tested on a real Windows image yet**. Always run Audit first.

---

## 2. Users and groups

### 2.1 Standalone / member server
- [ ] Done

**Script:** 🔎 The script does part of Windows 10/11 section 2; follow the Script lines there for what's left.

Same as [Windows 10/11 section 2](windows-10-11.md#2-users-and-groups).

### 2.2 Domain Controller: domain users
- [ ] Done

**Script:** ✅ Done by the script (`users` section).

**Clicking:** **Win + R** → `dsa.msc` (**Active Directory Users and Computers**). Users are usually in the **Users** folder, but check **every OU** (folder). Turn on **View → Advanced Features** to see everything.
- Delete a user: right-click → **Delete**.
- Disable a user: right-click → **Disable Account**.
- New user: right-click the folder → **New → User**.

**Typing:**
```powershell
Get-ADUser -Filter * -Properties Enabled, LastLogonDate | Format-Table SamAccountName, Enabled, DistinguishedName -AutoSize
Remove-ADUser -Identity mallory
New-ADUser -Name erin -SamAccountName erin -AccountPassword (Read-Host -AsSecureString "Password") -Enabled $true
Disable-ADAccount -Identity Guest
```

> [!CAUTION]
> **Never delete or change these built-in accounts:** `Administrator` (unless the README says so), `krbtgt` (Active Directory breaks without it), and computer accounts (names ending in `$`). Disable `Guest`.

### 2.3 Domain Controller: powerful groups
- [ ] Done

**Script:** 🔎 The script removes users who aren't README admins from these groups and adds README admins to Domain Admins (asks first); check for nested groups and anyone the README puts there on purpose.

Check the members of each group. Remove anyone the README doesn't say should be an admin.

| Group | Can… |
|---|---|
| **Domain Admins** | Control every computer in the domain |
| **Enterprise Admins** | Control the whole forest |
| **Schema Admins** | Change the structure of AD |
| **Administrators** (Builtin folder) | Control the Domain Controllers |
| **Account Operators** | Create and change most users |
| **Backup Operators** | Read every file, log on to DCs |
| **Server Operators** | Log on to DCs, change services |
| **Print Operators** | Load drivers on DCs |
| **DnsAdmins** | Can make the DNS server run any program (easy path to domain admin) |
| **Group Policy Creator Owners** | Create Group Policies |

**Typing:**
```powershell
foreach ($g in 'Domain Admins','Enterprise Admins','Schema Admins','Administrators','Account Operators','Backup Operators','Server Operators','Print Operators','DnsAdmins','Group Policy Creator Owners') {
  "--- $g"; (Get-ADGroupMember $g -ErrorAction SilentlyContinue).SamAccountName }
Remove-ADGroupMember -Identity 'Domain Admins' -Members bob -Confirm:$false
Add-ADGroupMember -Identity 'Domain Admins' -Members alice
Get-ADGroupMember 'Domain Admins' -Recursive | Select-Object SamAccountName   # also shows people hidden inside a nested group
```

> [!CAUTION]
> Some members are there by default: leave them. **Administrators** contains the groups **Domain Admins** and **Enterprise Admins** and the built-in **Administrator**; **Domain Admins**, **Enterprise Admins** and **Schema Admins** contain **Administrator**. Remove only *people* (and planted groups) the README doesn't list as admins.

### 2.4 Domain Controller: risky account settings
- [ ] Done

**Script:** ✅ Done by the script (`users` section).

**Clicking:** in `dsa.msc`, double-click a user → **Account** tab → **Account options**. These should all be **unticked**:
- Password never expires
- Store password using reversible encryption
- Do not require Kerberos preauthentication (lets attackers crack the password offline)
- Password not required (not shown here; use PowerShell)

**Typing:**
```powershell
Get-ADUser -Filter 'Enabled -eq $true' -Properties PasswordNeverExpires, PasswordNotRequired, AllowReversiblePasswordEncryption, DoesNotRequirePreAuth |
  Where-Object { $_.PasswordNeverExpires -or $_.PasswordNotRequired -or $_.AllowReversiblePasswordEncryption -or $_.DoesNotRequirePreAuth } |
  Format-Table SamAccountName, PasswordNeverExpires, PasswordNotRequired, AllowReversiblePasswordEncryption, DoesNotRequirePreAuth
Set-ADUser bob -PasswordNeverExpires $false -PasswordNotRequired $false -AllowReversiblePasswordEncryption $false
Set-ADAccountControl bob -DoesNotRequirePreAuth $false
```

### 2.5 Strong passwords
- [ ] Done

**Script:** 🔎 The script resets every README user's password except yours only if you put NewPassword in the config or type one when asked; otherwise do it by hand.

```powershell
Set-ADAccountPassword -Identity bob -Reset -NewPassword (Read-Host -AsSecureString "New password")
```

### 2.6 Standalone / member server: local accounts
- [ ] Done

**Script:** 🔎 The script does the same checks as Windows 10/11 section 2 on the local accounts; read its REVIEW lines.

**Typing:**
```powershell
Get-LocalUser | Format-Table Name, Enabled, PasswordRequired, PasswordLastSet, LastLogon
Get-LocalGroupMember Administrators | Format-Table Name, ObjectClass, PrincipalSource
net localgroup Guests                                              # should be empty
Get-LocalUser | Where-Object { -not $_.PasswordRequired -and $_.Enabled }   # accounts that can log in with no password
```
Disable `Guest`, remove people from **Administrators** who are not README admins, and delete accounts the README doesn't list:
```powershell
Disable-LocalUser -Name Guest
Remove-LocalUser -Name mallory
Add-LocalGroupMember -Group Administrators -Member alice
```

> [!CAUTION]
> Keep at least one working administrator (the built-in `Administrator` or yourself) before removing anyone else from **Administrators**, or you cannot undo the change.

---

## 3. Password and lockout policy

### 3.1 Standalone / member server
- [ ] Done

**Script:** 🔎 The script does Windows 10/11 3.1 and most of 3.2; set "Allow Administrator account lockout" yourself.

Same as [Windows 10/11 section 3](windows-10-11.md#3-account-policies-passwords-and-lockout).

### 3.2 Domain Controller: edit the Default Domain Policy
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**Clicking:**
1. **Win + R** → `gpmc.msc` (**Group Policy Management**).
2. Open **Forest → Domains → (your domain) → Group Policy Objects**.
3. Right-click **Default Domain Policy → Edit**.
4. Go to **Computer Configuration → Policies → Windows Settings → Security Settings → Account Policies**.
5. Set **Password Policy** and **Account Lockout Policy** with the same values as [Windows 10/11 section 3](windows-10-11.md#3-account-policies-passwords-and-lockout) (history 24, max age 90, min age 1, length 12, complexity on, reversible off; lockout 5 / 30 / 30).
6. Close the editor and run `gpupdate /force`.

**Check it worked:**
```powershell
Get-ADDefaultDomainPasswordPolicy
net accounts /domain
```

> [!NOTE]
> `Get-ADFineGrainedPasswordPolicy -Filter *` lists **fine-grained password policies**. These override the domain policy for some users. A planted weak one is a sneaky problem.

---

## 4. Audit policy, user rights and security options

### 4.1 Standalone / member server
- [ ] Done

**Script:** 🔎 The script does Windows 10/11 4.1 and 4.3; still check User Rights Assignment (4.2) by hand.

Same as [Windows 10/11 section 4](windows-10-11.md#4-local-policies).

### 4.2 Domain Controller: Default Domain Controllers Policy
- [ ] Done

**Script:** 🔎 The script sets many of these on the DC's own registry and local policy but doesn't edit the Default Domain Controllers Policy; set them in gpmc.msc so Group Policy can't undo them.

On a DC, these come from the **Default Domain Controllers Policy** GPO. In `gpmc.msc`, right-click it → **Edit** → **Computer Configuration → Policies → Windows Settings → Security Settings → Local Policies** (Audit Policy, User Rights Assignment, Security Options). Use the tables in the Windows 10/11 checklist, plus these DC settings:

**Back up every GPO before you edit one** (to undo: `Restore-GPO -Name 'Default Domain Controllers Policy' -Path C:\gpo-backup`):
```powershell
New-Item -ItemType Directory -Path C:\gpo-backup -Force | Out-Null
Backup-GPO -All -Path C:\gpo-backup
```

| Security Option | Set to |
|---|---|
| Domain controller: LDAP server signing requirements | **Require signing** |
| Domain controller: LDAP server channel binding token requirements | **Always** |
| Domain controller: Allow server operators to schedule tasks | **Disabled** |
| Domain controller: Refuse machine account password changes | **Disabled** |
| Domain member: Digitally encrypt or sign secure channel data (always) | **Enabled** |
| Network security: LDAP client signing requirements | **Negotiate signing** |

**User rights on a DC are different.** Use these rows instead of the Windows 10/11 ones:

| User right (on a DC) | Should be |
|---|---|
| Access this computer from the network | Administrators, **Authenticated Users**, **ENTERPRISE DOMAIN CONTROLLERS** (remove Everyone) |
| Allow log on locally | Administrators. Removing the Operator groups is fine. Never add Users or Domain Users |
| Allow log on through Remote Desktop Services | Administrators |
| Deny access to this computer from the network | Guests |

> [!CAUTION]
> A GPO change on a DC applies to **every computer in the domain** and is copied to every other DC. Removing **Authenticated Users** or **ENTERPRISE DOMAIN CONTROLLERS** from "Access this computer from the network", or adding a big group to a **Deny** right, stops users logging on and computers getting Group Policy. If the score drops or logons break, restore the backup.

Detailed audit settings are under **Security Settings → Advanced Audit Policy Configuration**. Set the account logon, account management, logon/logoff, policy change, privilege use, DS access and system categories to **Success and Failure**.

### 4.3 Look for planted bad Group Policies
- [ ] Done

**Script:** 🔎 On a DC the script lists every GPO, newest first (10 on screen, all of them in the findings file); open each one and look for planted settings.

**Why:** An attacker can create or change a GPO to turn off the firewall, add an admin, or run a script on every computer.

**Clicking:** In `gpmc.msc`, click each GPO → **Settings** tab (it shows a report). Look for anything that weakens security. Check the **Scope** tab to see where it's linked.

**Typing:**
```powershell
Get-GPO -All | Sort-Object ModificationTime -Descending | Format-Table DisplayName, ModificationTime
Get-GPOReport -All -ReportType Html -Path C:\gpo-report.html; Start-Process C:\gpo-report.html
```

### 4.4 Domain Controller: Zerologon protection
- [ ] Done

**Script:** 🔎 On a Domain Controller the script sets `FullSecureChannelProtection` to 1 (`security` section); check the "Allow vulnerable Netlogon secure channel connections" policy yourself.

**Why it matters:** Zerologon (CVE-2020-1472) lets anyone on the network take over a Domain Controller without a password. Windows updates since February 2021 always block it, but a planted policy can let chosen accounts use the weak connection again, and an un-updated image is wide open.

**Clicking:** In the **Default Domain Controllers Policy** (4.2) → **Security Options** → **Domain controller: Allow vulnerable Netlogon secure channel connections** must be **Not Defined** (no accounts listed). Install updates too (5.3).

**Typing:**
```powershell
New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\Netlogon\Parameters' -Name FullSecureChannelProtection -Value 1 -PropertyType DWord -Force
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\Netlogon\Parameters' | Format-List FullSecureChannelProtection, RequireSignOrSeal, RequireStrongKey
```
**Check it worked:** `FullSecureChannelProtection` shows `1`. `RequireSignOrSeal` and `RequireStrongKey` are normally `1` too; if one of them is missing, that is fine, it follows the policy default.

---

## 5. Defender, firewall and updates

### 5.1 Microsoft Defender
- [ ] Done

**Script:** 🔎 The script does part of Windows 10/11 section 5 and offers to install Defender if it's missing; turn on Tamper Protection (Server 2022) and run a scan yourself.

Same as [Windows 10/11 section 5](windows-10-11.md#5-microsoft-defender-antivirus). If Defender isn't installed: **Server Manager → Add Roles and Features → Features → Microsoft Defender Antivirus** (called **Windows Defender Features** on Server 2016), or `Install-WindowsFeature Windows-Defender`, then restart. Server 2016 and 2019 don't show **Tamper Protection** in the Defender settings; skip that part there.

### 5.2 Firewall
- [ ] Done

**Script:** 🔎 The script turns the firewall on for every profile and never disables the built-in DC rule groups; still review the custom inbound rules (Windows 10/11 6.2).

Same as [Windows 10/11 section 6](windows-10-11.md#6-firewall).

> [!CAUTION]
> On a Domain Controller, **don't disable** the built-in rule groups **Active Directory Domain Services**, **DNS Service**, **Kerberos Key Distribution Center**, **Netlogon Service** or **DFS Replication**. Clients need them.

### 5.3 Windows Update
- [ ] Done

**Script:** 🔎 The script installs updates only if InstallUpdates is 'yes' (or you answer yes); otherwise install them here by hand.

**Server Manager → Local Server → Windows Update** (or **Settings → Update & Security**). On Server Core: run `sconfig` and choose **Install updates**.

### 5.4 IE Enhanced Security Configuration
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**Server Manager → Local Server → IE Enhanced Security Configuration** must be **On** for Administrators and Users.

---

## 6. Services

### 6.1 Turn off what the README doesn't need
- [ ] Done

**Script:** 🔎 The script disables the risky services the README doesn't list (asks first; WinRM and Remote Desktop default to No); decide those yourself.

Same list as [Windows 10/11 section 8](windows-10-11.md#8-services), plus:
- **Print Spooler**: disable on Domain Controllers unless this is the print server (PrintNightmare).
- **Windows Remote Management (WinRM)**: Server Manager uses it, so keep it on servers unless the README says otherwise, and lock it down (section 8).

Windows Server has no **Security Center** (`wscsvc`) service, so skip that name in Windows 10/11 step 8.2.

### 6.2 Never touch these on a Domain Controller
- [ ] Done

**Script:** 🔎 The script never changes these services on a Domain Controller, but doesn't check they're running; run the check command.

| Service | Name |
|---|---|
| Active Directory Domain Services | `NTDS` |
| DNS Server | `DNS` |
| Kerberos Key Distribution Center | `Kdc` |
| Netlogon | `Netlogon` |
| DFS Replication | `DFSR` |
| Windows Time | `W32Time` |
| Active Directory Web Services | `ADWS` |
| Intersite Messaging | `IsmServ` |

```powershell
Get-Service NTDS, DNS, Kdc, Netlogon, DFSR, W32Time, ADWS, IsmServ | Format-Table Name, Status, StartType
```
All should be **Running** and **Automatic**.

### 6.3 Print Spooler: PrintNightmare fixes
- [ ] Done

**Script:** ✅ Done by the script (`security` section sets the three registry values below; the `services` section offers to turn off the Print Spooler when the README doesn't need printing).

**Why it matters:** PrintNightmare (CVE-2021-34527) lets a normal user install a "printer driver" that runs as SYSTEM. If the spooler must keep running, make sure only admins can install drivers.

**Clicking:** `gpedit.msc` (on a DC: the **Default Domain Controllers Policy** in `gpmc.msc`) → **Computer Configuration → Administrative Templates → Printers**:
- **Limits print driver installation to Administrators**: **Enabled**.
- **Point and Print Restrictions**: **Enabled**, and both "When installing drivers for a new connection" and "When updating drivers for an existing connection" set to **Show warning and elevation prompt**.

**Typing:**
```powershell
$pp = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint'
if (-not (Test-Path $pp)) { New-Item -Path $pp -Force | Out-Null }
New-ItemProperty -Path $pp -Name RestrictDriverInstallationToAdministrators -Value 1 -PropertyType DWord -Force
New-ItemProperty -Path $pp -Name NoWarningNoElevationOnInstall -Value 0 -PropertyType DWord -Force
New-ItemProperty -Path $pp -Name UpdatePromptSettings -Value 0 -PropertyType DWord -Force
Get-Service Spooler | Format-Table Name, Status, StartType     # Disabled on a DC unless it's the print server
```
**Check it worked:** `Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint'` shows `RestrictDriverInstallationToAdministrators : 1` and the other two `0`.

---

## 7. Roles and features

### 7.1 Remove roles and features that aren't needed
- [ ] Done

**Script:** 🔎 The script removes SMBv1, Telnet, TFTP, PowerShell 2.0, SNMP, Simple TCP/IP and (if your config doesn't list ftp) the IIS FTP server (asks first), and asks about IIS with default No; decide other roles yourself.

**Clicking:** **Server Manager → Manage → Remove Roles and Features**. Untick unneeded **features**: Telnet Client, TFTP Client, SMB 1.0/CIFS File Sharing Support, Windows PowerShell 2.0 Engine, SNMP Service, Simple TCP/IP Services. Remove **roles** only if the README clearly doesn't need them (e.g. Web Server (IIS) on a plain DC).

**Typing:**
```powershell
Get-WindowsFeature | Where-Object Installed | Format-Table Name, DisplayName
Uninstall-WindowsFeature -Name Telnet-Client, TFTP-Client, FS-SMB1, PowerShell-V2, Simple-TCPIP
Uninstall-WindowsFeature -Name SNMP-Service      # only if the README doesn't need SNMP
```
Restart once when it says a restart is needed (SMBv1 removal needs one).

> [!CAUTION]
> **Never** remove **AD DS**, **DNS Server**, or any role the README mentions.

---

## 8. Remote access

### 8.1 Remote Desktop and Remote Assistance
- [ ] Done

**Script:** 🔎 The script does part of Windows 10/11 section 10 (Remote Assistance off, RDP off or NLA on); still check who is in Remote Desktop Users.

Same as [Windows 10/11 section 10](windows-10-11.md#10-remote-access). Servers often **need** RDP; if so, keep it on with Network Level Authentication, and control who's in **Remote Desktop Users**.

### 8.2 Lock down WinRM
- [ ] Done

**Script:** 🔎 The script sets the WinRM policies (no Basic authentication, no unencrypted traffic); run the winrm command to confirm.

```powershell
winrm get winrm/config/service       # AllowUnencrypted = false, Basic = false
```
Or with `gpedit.msc` → **Administrative Templates → Windows Components → Windows Remote Management (WinRM) → WinRM Service**: **Allow Basic authentication: Disabled**, **Allow unencrypted traffic: Disabled**.

---

## 9. Critical server roles (only if the README lists them)

### 9.1 IIS web server
- [ ] Done

**Script:** 🔎 If your config lists iis, the script turns off directory browsing, hides version headers, turns on logging and fixes LocalSystem app pools; you still check authentication, request filtering and web shells.

**Clicking:** **Win + R** → `inetmgr` (IIS Manager). For the server **and each site**:
- **Directory Browsing** → **Disable** (Actions pane).
- **HTTP Response Headers** → remove **X-Powered-By**.
- **Request Filtering** → check nothing dangerous is allowed. **Edit Feature Settings** → untick **Allow unlisted file name extensions** only if the site still works afterwards.
- **Logging** → enabled.
- **Authentication** → **Basic Authentication** disabled unless the site uses HTTPS and needs it. **Anonymous Authentication** only if the site is public.
- **Application Pools** → **Advanced Settings → Identity**: should be **ApplicationPoolIdentity**, not **LocalSystem**.
- Look in the site folder (`C:\inetpub\wwwroot` or wherever **Basic Settings** points) for web shells: `.aspx`, `.asp` or `.php` files you don't recognise, e.g. `cmd.aspx` or `shell.aspx`.

```powershell
Import-Module WebAdministration      # if this fails: Install-WindowsFeature Web-Scripting-Tools
Get-Website | Format-Table Name, State, PhysicalPath
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter system.webServer/directoryBrowse -Name enabled -Value $false
Remove-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter system.webServer/httpProtocol/customHeaders -Name . -AtElement @{name='X-Powered-By'}
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter system.webServer/security/requestFiltering -Name removeServerHeader -Value $true   # Server 2019/2022 only
Get-ChildItem C:\inetpub -Recurse -Include *.aspx,*.asp,*.php | Select-String -Pattern 'cmd.exe|Process.Start|eval\(|exec\(' | Select-Object Path -Unique
```
If the X-Powered-By header is already gone, that line may print an error; that's fine.

### 9.2 IIS FTP server
- [ ] Done

**Script:** 🔎 If your config lists ftp, the script turns off anonymous FTP (asks first) and warns if SSL isn't required; you still do authorization rules, user isolation and logging.

In `inetmgr`, click the FTP site:
- **FTP Authentication** → **Anonymous Authentication: Disabled** (unless the README needs anonymous FTP).
- **FTP Authorization Rules** → no "Allow All Users / Anonymous Read, Write" unless needed.
- **FTP SSL Settings** → **Require SSL connections** (only if a certificate is selected).
- **FTP User Isolation** → isolate users (so they can't see each other's files).
- **FTP Logging** → enabled.

```powershell
Import-Module WebAdministration
Get-Website | Where-Object { $_.Bindings.Collection.protocol -contains 'ftp' } | Format-Table Name, PhysicalPath   # your FTP site names
Set-ItemProperty 'IIS:\Sites\Default FTP Site' -Name ftpServer.security.authentication.anonymousAuthentication.enabled -Value $false   # use your site's name from the line above
```

### 9.3 DNS server
- [ ] Done

**Script:** 🔎 The script blocks zone transfers (asks first) and sets secure-only updates on AD-integrated zones; you still check the records and non-AD zones.

**Clicking:** **Win + R** → `dnsmgmt.msc`. For each **Forward Lookup Zone**, right-click → **Properties**:
- **General → Dynamic updates:** **Secure only** (for AD-integrated zones).
- **Zone Transfers:** untick **Allow zone transfers**, or choose **Only to the following servers** if the README mentions a secondary DNS server.

Look through the records for anything suspicious, e.g. a record for `update.microsoft.com` or `www.bank.com` pointing to a strange IP.

**Typing:**
```powershell
Get-DnsServerZone | Format-Table ZoneName, ZoneType, DynamicUpdate, SecureSecondaries, IsDsIntegrated
Set-DnsServerPrimaryZone -Name corp.local -SecureSecondaries NoTransfer -DynamicUpdate Secure   # change corp.local to your zone name
Get-DnsServerResourceRecord -ZoneName corp.local | Format-Table HostName, RecordType, RecordData
```
`-DynamicUpdate Secure` works only when **IsDsIntegrated** is `True`. For a zone that isn't, use `-DynamicUpdate None` (unless the README needs dynamic updates).

### 9.4 Active Directory
- [ ] Done

**Script:** 🔎 The script offers to turn on the AD Recycle Bin and lists unconstrained delegation; you still do Protected Users, SYSVOL scripts and the machine account quota.

- **AD Recycle Bin:** **Active Directory Administrative Center (`dsac.exe`)** → click the domain → **Enable Recycle Bin…** (it can't be turned off later, which is fine).
- **Protected Users group:** admins in it get extra protection. Add only if the README doesn't forbid it.
- **Logon scripts in SYSVOL:** look in `C:\Windows\SYSVOL\domain\scripts` and `C:\Windows\SYSVOL\domain\Policies\*\Machine\Scripts` / `User\Scripts` for scripts you don't recognise.
- **Unconstrained delegation:** `Get-ADComputer -Filter 'TrustedForDelegation -eq $true'`. Only DCs should be listed.
- **Who can add computers:** `Get-ADObject (Get-ADDomain).DistinguishedName -Properties ms-DS-MachineAccountQuota`. Setting it to 0 stops normal users joining computers (optional).

### 9.5 DHCP server
- [ ] Done

**Script:** 🔎 If the DHCP Server role is running, the script turns on DHCP audit logging and lists every scope and the router/DNS options (003, 006...) as REVIEW lines; you compare them with the README.

`dhcpmgmt.msc`: check the scopes and reservations against the README, and make sure **Enable DHCP audit logging** is ticked (server → **Properties**). Look at **Scope Options** too: a planted **006 DNS Servers** or **003 Router** pointing at a strange IP sends every client to the attacker.

```powershell
Get-DhcpServerv4Scope | Format-Table ScopeId, Name, StartRange, EndRange, State
Get-DhcpServerv4Scope | Get-DhcpServerv4Reservation          # every reservation
Get-DhcpServerv4OptionValue                                  # server options (006 = DNS servers, 003 = router)
Get-DhcpServerv4Scope | Get-DhcpServerv4OptionValue          # options set on each scope
Set-DhcpServerAuditLog -Enable $true
Get-DhcpServerAuditLog
```

### 9.6 File server shares
- [ ] Done

**Script:** 🔎 If your config lists smb, the script removes Everyone's write access from shares (asks first); if it doesn't, it offers to stop sharing every non-built-in share. You still check the other share and NTFS permissions.

**Clicking:** `fsmgmt.msc` → **Shares**. For each share the README needs: **Properties → Share Permissions** shouldn't give **Everyone: Full Control**, and on the **Security** tab (NTFS), only the right groups should have **Modify / Full control**.

```powershell
Get-SmbShare | ForEach-Object { "--- $($_.Name) $($_.Path)"; Get-SmbShareAccess $_.Name | Format-Table AccountName, AccessRight }
Grant-SmbShareAccess -Name Data -AccountName 'Authenticated Users' -AccessRight Read -Force   # "Data" = your share; use Change only if the README says users must save files here
Revoke-SmbShareAccess -Name Data -AccountName Everyone -Force
Get-SmbServerConfiguration | Format-List EnableSMB1Protocol, RequireSecuritySignature   # want False and True
```
On a Domain Controller, leave **NETLOGON** and **SYSVOL** alone.

### 9.7 Turn off SSL 3.0, TLS 1.0 and TLS 1.1
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**Why it matters:** These old encryption versions have known breaks. Websites (IIS), FTP over SSL, Remote Desktop and LDAPS should all use TLS 1.2 or newer. Server 2016-2022 still allow TLS 1.0 and 1.1 unless you turn them off.

**Typing:**
```powershell
foreach ($p in 'SSL 2.0', 'SSL 3.0', 'TLS 1.0', 'TLS 1.1') {
  $k = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\$p\Server"
  if (-not (Test-Path $k)) { New-Item -Path $k -Force | Out-Null }
  New-ItemProperty -Path $k -Name Enabled -Value 0 -PropertyType DWord -Force | Out-Null
  New-ItemProperty -Path $k -Name DisabledByDefault -Value 1 -PropertyType DWord -Force | Out-Null }
```
This changes only what the server *accepts* (the `Server` keys), not how the server connects out, so programs on it that talk to the internet keep working. Restart the server once (near the end, after saving your work) so every service picks it up.

**Check it worked:** `Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.0\Server'` shows `Enabled : 0`. Then open the website / connect with RDP to make sure the critical services still work, and refresh the Scoring Report: if it stops updating, undo this step.

> [!CAUTION]
> Very old programs (for example an old SQL Server or FTP server) may only speak TLS 1.0. If a README service stops working after the restart, set `Enabled` back to `1` for the version it needs and restart again.

---

## 10. Prohibited software and files

### 10.1 Installed programs that break the rules
- [ ] Done

**Script:** 🔎 The script compares installed programs with its prohibited list; check anything it says it skipped.

**Typing:**
```powershell
$keys = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
Get-ItemProperty $keys | Where-Object DisplayName |
  Select-Object DisplayName, DisplayVersion, InstallDate | Sort-Object DisplayName
Get-AppxPackage -AllUsers | Select-Object Name, PackageFullName      # Store-style apps (Server 2019+)
```
Uninstall with **Settings → Apps → Installed apps** (Server 2022 with Desktop Experience), **Server Manager → Remove Roles and Features** (roles), or the program's own uninstaller:
```powershell
Get-AppxPackage -AllUsers -Name '*Xbox*' | Remove-AppxPackage -AllUsers
```
On **Server Core** there is no Store and no games; the list is short and usually empty.

### 10.2 Games and consumer apps
- [ ] Done

**Script:** 🔎 The script removes the games and consumer apps it recognises; check its REVIEW lines.

**Typing:**
```powershell
Get-AppxPackage -AllUsers | Where-Object { $_.Name -match 'Solitaire|Minesweeper|Xbox|ZuneMusic|ZuneVideo|SkypeApp|People' } |
  Select-Object Name
Get-AppxPackage -AllUsers | Where-Object { $_.Name -match 'Solitaire|Minesweeper|Xbox' } | Remove-AppxPackage -AllUsers
Get-WindowsFeature | Where-Object { $_.Installed -and $_.Name -match 'DesktopExperience' }   # the desktop itself is a feature
```
Don't remove **Desktop Experience** unless the README says the server is headless: it takes Explorer with it.

### 10.3 Media and other prohibited files
- [ ] Done

**Script:** 🔎 The script searches every folder on the fixed disks (not Windows or Program Files) for media, `.torrent`, password lists and packet captures and lists them for you; it deletes media only if you say yes.

**Typing:**
```powershell
Get-ChildItem C:\Users, C:\Temp, C:\inetpub -Recurse -ErrorAction SilentlyContinue -Include *.mp3,*.mp4,*.avi,*.mkv,*.wav,*.flac,*.mov |
  Select-Object FullName, Length
Get-ChildItem C:\Users, C:\Temp -Recurse -ErrorAction SilentlyContinue -Include *password*,*.pcap,*.kdbx,*creditcard* |
  Select-Object FullName
```
Delete only what the README forbids **after** the forensics questions are answered.

### 10.4 Hacking tools and odd executables in user folders
- [ ] Done

**Script:** 🔎 The script looks for the common tool names and for executables in the temp folders; open each hit before deleting it.

**Typing:**
```powershell
Get-ChildItem C:\ -Recurse -ErrorAction SilentlyContinue -Include nmap.exe,nc.exe,ncat.exe,netcat.exe,hydra.exe,john.exe,hashcat.exe,mimikatz.exe,psexec.exe,procdump.exe |
  Select-Object FullName, Length
Get-ChildItem $env:TEMP, C:\Users\Public, C:\Windows\Temp -Recurse -Filter *.exe -ErrorAction SilentlyContinue |
  Select-Object FullName, Length, LastWriteTime
```
The Sysinternals tools (`psexec`, `procdump`) are legitimate on some images; only remove them when the README forbids them.

> [!WARNING]
> Check the forensics questions first: a planted tool is sometimes the answer to one.

---

## 11. Backdoors and persistence

### 11.1 Scheduled tasks
- [ ] Done

**Script:** 🔎 The script lists every non-Microsoft task and deletes the suspicious ones (asks first; Microsoft's own tasks are only flagged when they run from a user folder); read the rest yourself.

**Typing:**
```powershell
Get-ScheduledTask | Where-Object State -ne Disabled |
  Select-Object TaskPath, TaskName, State | Sort-Object TaskPath
Get-ScheduledTask | ForEach-Object { $a = $_.Actions | Where-Object Execute
  if ($a -and $a.Execute -notmatch 'C:\\Windows\\') { [pscustomobject]@{ Task="$($_.TaskPath)$($_.TaskName)"; Run=$a.Execute; Args=$a.Arguments } } } |
  Format-List
```
A task whose action is `powershell -enc ...`, `cmd /c` with a base64 blob, or a program in `C:\Users\Public` or `C:\Temp` is a backdoor:
```powershell
Disable-ScheduledTask -TaskName 'Updater' -TaskPath '\'
Unregister-ScheduledTask -TaskName 'Updater' -TaskPath '\' -Confirm:$false
```

### 11.2 Services that don't come from Windows
- [ ] Done

**Script:** 🔎 The script lists services whose binary is outside `C:\Windows` and `C:\Program Files`, offers to disable the ones in user folders (asking first), adds quotes to unquoted paths with spaces, and reports service programs or folders that ordinary users can change.

**Typing:**
```powershell
Get-CimInstance Win32_Service | Where-Object { $_.PathName -and $_.PathName -notmatch 'C:\\Windows\\' } |
  Select-Object Name, DisplayName, State, StartMode, PathName | Format-Table -Wrap
Get-CimInstance Win32_Service | Where-Object { $_.PathName -match 'Temp|Users\\Public|ProgramData' } |
  Select-Object Name, PathName
```
Remove one with `sc.exe delete <name>` (or `Remove-Service` on PowerShell 6+), after stopping it.

### 11.3 Run keys, startup folders and Winlogon
- [ ] Done

**Script:** 🔎 The script empties the suspicious Run/RunOnce values and repairs `Shell`/`Userinit`; check the backups it made.

**Typing:**
```powershell
$run = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
       'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce',
       'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
       'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'
Get-ItemProperty $run -ErrorAction SilentlyContinue | Format-List
Get-ChildItem "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\StartUp" -ErrorAction SilentlyContinue
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' | Format-List Shell, Userinit, Taskman
```
`Shell` must be `explorer.exe` and `Userinit` must be `C:\Windows\system32\userinit.exe,`. Anything else runs at every logon.

### 11.4 WMI event subscriptions
- [ ] Done

**Script:** 🔎 The script lists WMI command-line and script consumers and offers to remove each one with its filter and binding (asks first); it does not list plain event filters, so run the first command below too.

**What:** A WMI subscription can run a command whenever something happens (a logon, a file change) and is invisible in Task Manager.

**Typing:**
```powershell
Get-CimInstance -Namespace root\subscription -ClassName __EventFilter | Select-Object Name, Query
Get-CimInstance -Namespace root\subscription -ClassName CommandLineEventConsumer | Select-Object Name, CommandLineTemplate
Get-CimInstance -Namespace root\subscription -ClassName __FilterToConsumerBinding
```
A normal server has none of these. Remove a planted one:
```powershell
Get-CimInstance -Namespace root\subscription -ClassName __EventFilter -Filter "Name='Updater'" | Remove-CimInstance
```

### 11.5 Hidden and password-less local accounts
- [ ] Done

**Script:** 🔎 The script lists local accounts that aren't in the README (it removes them only if you say yes), turns automatic logon off and deletes a stored `DefaultPassword`, and lists accounts hidden from the logon screen (`SpecialAccounts`); the `reg query` for hidden account names is still yours.

**Typing:**
```powershell
Get-LocalUser | Select-Object Name, Enabled, PasswordRequired, Description
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' | Format-List AutoAdminLogon, DefaultUserName, DefaultPassword
reg query "HKLM\SAM\SAM\Domains\Account\Users\Names"        # every account name, including ones hidden from the tools
```
`AutoAdminLogon = 1` with a stored `DefaultPassword` is a free login for anyone at the console.

### 11.6 The hosts file
- [ ] Done

**Script:** 🔎 The script comments out every unusual hosts line (asks first; `backdoors` section); if the Scoring Report doesn't give the points, delete those lines completely.

**Typing:**
```powershell
Get-Content C:\Windows\System32\drivers\etc\hosts
```
Only comment lines and `127.0.0.1 localhost` are normal. A line pointing a website or an update server at another address is a redirect attack: delete it.

---

## 12. Logging and auditing

### 12.1 Event log size and retention
- [ ] Done

**Script:** 🔎 The script raises the Security, Application, System and PowerShell log sizes and reports a Security or System log that was cleared (events 1102 and 104); it does not look for other emptied logs.

**What:** A cleared or tiny log means no evidence, and a planted script can clear it again. Scoring engines check the log size and that auditing is on.

**Typing:**
```powershell
Get-WinEvent -ListLog Security, System, Application, 'Microsoft-Windows-PowerShell/Operational' |
  Format-Table LogName, MaximumSizeInBytes, RecordCount, IsEnabled
wevtutil sl Security /ms:1000000000          # ~1 GB for Security
Get-WinEvent -ListLog * -ErrorAction SilentlyContinue | Where-Object { $_.IsEnabled -and $_.RecordCount -eq 0 } |
  Select-Object LogName                         # logs that were emptied
```

### 12.2 Audit policy is really on
- [ ] Done

**Script:** 🔎 On every Windows computer the script sets all audit subcategories to Success and Failure through `auditpol` (`audit` section); check the output below for any that a planted GPO turns back off.

**Typing:**
```powershell
auditpol /get /category:*
```
For **Account Logon**, **Account Management**, **Logon/Logoff**, **Policy Change**, **Privilege Use** and **System**, at least **Success and Failure** should be set (not "No Auditing"). A planted GPO can turn them off; check with:
```powershell
auditpol /get /category:* | Select-String 'No Auditing'
```

### 12.3 PowerShell logging
- [ ] Done

**Script:** ✅ Done by the script (`audit` section: script block logging, module logging and command lines in process-creation events).

**Typing:**
```powershell
$k = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging'
New-Item -Path $k -Force | Out-Null
New-ItemProperty -Path $k -Name EnableScriptBlockLogging -Value 1 -PropertyType DWord -Force
Get-ItemProperty $k | Format-List EnableScriptBlockLogging
```
Every PowerShell block then lands in **Microsoft-Windows-PowerShell/Operational** (event 4104), which is where you look for what a planted task actually ran.

---

## 13. Network and protocol hardening

### 13.1 SMB signing, SMBv1 and NTLM
- [ ] Done

**Script:** ✅ The script turns SMBv1 off (`features` section, and the `SMB1` registry value in `security`) and requires SMB signing, NTLMv2 only and no LM hashes (`security` section).

**Typing:**
```powershell
Get-SmbServerConfiguration | Format-List EnableSMB1Protocol, RequireSecuritySignature, EnableSecuritySignature, RestrictNamedPipeAccess
Set-SmbServerConfiguration -EnableSMB1Protocol $false -RequireSecuritySignature $true -EnableSecuritySignature $true -Force
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' | Format-List LmCompatibilityLevel, NoLMHash, RestrictAnonymous
```
`LmCompatibilityLevel` should be `5` (NTLMv2 only, refuse LM and NTLM). `NoLMHash` should be `1`.

### 13.2 LLMNR, NetBIOS and WPAD
- [ ] Done

**Script:** 🔎 The script turns off LLMNR, WPAD and NetBIOS over TCP/IP (`misc` section); on a Domain Controller it asks about NetBIOS with default No.

**Why:** LLMNR, NetBIOS name resolution and WPAD let anyone on the network answer "where is that server?" and collect hashes.

**Typing:**
```powershell
$dns = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient'
New-Item -Path $dns -Force | Out-Null
New-ItemProperty -Path $dns -Name EnableMulticast -Value 0 -PropertyType DWord -Force      # LLMNR off
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Services\NetBT\Parameters\Interfaces' |
  ForEach-Object { Set-ItemProperty $_.PSPath -Name NetbiosOptions -Value 2 }              # NetBIOS over TCP/IP off
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WinHttp' -ErrorAction SilentlyContinue | Format-List DisableWpad
```
Set **DisableWpad = 1** under that key (create it if needed). On a Domain Controller, don't disable DNS client services — only LLMNR/NetBIOS/WPAD resolution.

### 13.3 Remote access left open
- [ ] Done

**Script:** 🔎 The script turns off Remote Assistance and checks RDP/NLA (section 8); review WinRM listeners yourself.

**Typing:**
```powershell
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' | Format-List fDenyTSConnections
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' | Format-List UserAuthentication, SecurityLayer
winrm enumerate winrm/config/listener                 # listeners that should not exist
```

---

## 14. Final checks

- [ ] Every critical role still works (e.g. `nslookup corp.local` with your domain name for DNS, open the website for IIS)
- [ ] On a DC: `dcdiag /q` prints no errors (no output = good)
- [ ] Scoring Report shows **no penalties**
- [ ] Forensics answers saved
- [ ] Final snapshot
