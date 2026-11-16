"""Getting the hardening script into the guest and the reports back out.

Linux / FreeBSD: ssh + scp (key auth, or sshpass when the catalog names an
environment variable that holds the password).

Windows: PowerShell remoting (WinRM). Needs PowerShell on the range host and
WinRM enabled in the Windows template; the password comes from an environment
variable named in the catalog, never from a command line or a file.

Nothing here runs a shell command built from user text: every command is a list
of arguments, and the README names are cleaned before they go into a config file.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

SCRIPTS = {
    "linux": "scripts/linux/harden.sh",
    "freebsd": "scripts/freebsd/harden.sh",
    "windows": "scripts/windows/Harden.ps1",
}
NAME_RE = re.compile(r"[^A-Za-z0-9_.@ \-]+")
SAFE_NAMES = re.compile(r"^[A-Za-z0-9_.@ -]*$")


class RunnerError(RuntimeError):
    """The guest could not be prepared or reached."""


def clean_names(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[\s,;]+", value)
    else:
        parts = [str(v) for v in value]
    out = []
    for part in parts:
        part = NAME_RE.sub("", part).strip()
        if part and part not in out:
            out.append(part)
    return out


def build_config(image: dict, config: dict, dest: Path) -> Path:
    """Write the script's config file. Returns its path."""
    admins = clean_names(config.get("admins"))
    users = clean_names(config.get("users"))
    critical = [c.lower() for c in clean_names(config.get("critical"))]
    mode = (config.get("updates") or "no").lower()
    if mode not in {"yes", "no", "ask"}:
        mode = "no"
    lockout = "yes" if config.get("lockout", True) else "no"
    password = config.get("newPassword") or "skip"
    if password != "skip" and not SAFE_NAMES.match(password):
        raise RunnerError("the new password contains characters the config file format cannot hold; leave it blank and set passwords by hand")

    if image["script"] == "windows":
        def ps_list(items):
            return "@(" + ",".join("'" + i.replace("'", "''") + "'" for i in items) + ")"

        text = (
            "@{\n"
            f"  AuthorizedAdmins   = {ps_list(admins)}\n"
            f"  AuthorizedUsers    = {ps_list(users)}\n"
            f"  CriticalServices   = {ps_list(critical)}\n"
            f"  NewPassword        = '{password.replace(chr(39), chr(39) * 2)}'\n"
            f"  EnableLockout      = '{lockout}'\n"
            f"  InstallUpdates     = '{mode}'\n"
            "}\n"
        )
        path = dest / "rampart-readme.psd1"
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        def sh_list(items):
            return " ".join(items)

        text = (
            "# Written by the Rampart range from the README answers you typed.\n"
            f'AUTHORIZED_ADMINS="{sh_list(admins)}"\n'
            f'AUTHORIZED_USERS="{sh_list(users)}"\n'
            f'CRITICAL_SERVICES="{sh_list(critical)}"\n'
            f'SSH_PASSWORD_AUTH="{config.get("sshPasswordAuth") or "keep"}"\n'
            f'NEW_PASSWORD="{password}"\n'
            f"FULL_UPGRADE=\"{mode}\"\n"
            f'ENABLE_LOCKOUT="{lockout}"\n'
            f'EXTRA_PORTS="{sh_list(clean_names(config.get("extraPorts")))}"\n'
        )
        path = dest / "rampart.conf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o600)
    return path


def _guest(image: dict, runtime: dict) -> dict:
    guest = dict(image.get("guest") or {})
    if image.get("family") == "windows":
        guest.setdefault("host", runtime.get("host") or "127.0.0.1")
        guest.setdefault("port", runtime.get("port") or runtime.get("winrmPort") or 5985)
    else:
        guest.setdefault("host", runtime.get("host") or "127.0.0.1")
        guest.setdefault("port", runtime.get("sshPort") or runtime.get("port") or guest.get("sshPort") or 22)
    return guest


def _ssh(image: dict, runtime: dict) -> tuple[list[str], dict]:
    guest = _guest(image, runtime)
    key = guest.get("keyFile")
    if key:
        key = os.path.expanduser(os.path.expandvars(key))
        if not Path(key).exists():
            raise RunnerError(f"SSH key not found: {key} (guest.keyFile in images.json)")
    pw_env = guest.get("passwordEnv")
    password = os.environ.get(pw_env, "") if pw_env else ""
    if not key and not password:
        raise RunnerError(
            "this image has no guest.keyFile and no guest.passwordEnv. Put your SSH public key "
            "into the template image (that is what makes a range image reusable), or set "
            "guest.passwordEnv to the name of an environment variable that holds the password."
        )
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        "-o", "BatchMode=" + ("yes" if key else "no"),
        "-o", "ConnectTimeout=10",
        "-p", str(guest["port"]),
    ]
    if key:
        cmd += ["-i", key]
    env = dict(os.environ)
    if password and not key:
        cmd = ["sshpass", "-e"] + cmd
        env["SSHPASS"] = password
        if not shutil.which("sshpass"):
            raise RunnerError("password login needs sshpass on the range host (sudo apt install sshpass), or use a key")
    cmd.append(f'{guest.get("user") or "root"}@{guest["host"]}')
    return cmd, env


def _scp(image: dict, runtime: dict) -> tuple[list[str], dict]:
    ssh, env = _ssh(image, runtime)
    # Replace ssh with scp and drop the trailing user@host: it is added per call.
    out = ["scp", "-q", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]
    if "sshpass" in ssh:
        out = ["sshpass", "-e"] + out
    if "-i" in ssh:
        out += ["-i", ssh[ssh.index("-i") + 1]]
    out += ["-P", ssh[ssh.index("-p") + 1]]
    return out, env


def _remote(image: dict, runtime: dict, command: str) -> tuple[list[str], dict]:
    ssh, env = _ssh(image, runtime)
    return ssh + [command], env


def run_script(image: dict, runtime: dict, repo_root: Path, run_dir: Path, config: dict, mode: str, log, cancel=None) -> dict:
    """Run harden.sh / Harden.ps1 inside the guest and collect the reports."""
    collected = run_dir / "collected"
    collected.mkdir(parents=True, exist_ok=True)
    payload = run_dir / "payload"
    payload.mkdir(parents=True, exist_ok=True)
    build_config(image, config, payload)
    script_src = repo_root / SCRIPTS[image["script"]]
    if not script_src.exists():
        raise RunnerError(f"script not found in the repository: {script_src}")
    shutil.copy2(script_src, payload / script_src.name)
    example_conf = script_src.parent / ("config.example.conf" if image["script"] != "windows" else "config.example.psd1")
    if example_conf.exists():
        shutil.copy2(example_conf, payload / example_conf.name)

    if image.get("family") == "windows":
        result = _run_windows(image, runtime, run_dir, payload, conf, mode, log, collected, cancel)
    else:
        result = _run_unix(image, runtime, run_dir, payload, conf, mode, log, collected, cancel)
    result["collected"] = sorted(p.name for p in collected.rglob("*") if p.is_file())
    return result


def _run_unix(image, runtime, run_dir, payload, conf, mode, log, collected, cancel) -> dict:
    guest = _guest(image, runtime)
    scp, env = _scp(image, runtime)
    remote_dir = "/tmp/rampart"
    ssh, senv = _remote(image, runtime, f"rm -rf {remote_dir} && mkdir -p {remote_dir} && chmod 700 {remote_dir}")
    log("preparing /tmp/rampart in the guest")
    _stream(ssh, senv, log, cancel, "prepare")

    log("copying the script and the README config into the guest")
    for name in ("harden.sh", "rampart.conf", "config.example.conf"):
        local = payload / name
        if not local.exists():
            continue
        cmd = scp + [str(local), f'{guest.get("user") or "root"}@{guest["host"]}:{remote_dir}/{name}']
        _run(cmd, env, log, cancel, f"copy {name}", quiet=True)

    flags = "--audit" if mode == "audit" else "--apply --yes"
    if image["script"] == "windows":
        raise RunnerError("internal: window image reached the Unix runner")
    if image.get("family") == "freebsd":
        inner = f"cd {remote_dir} && chmod +x harden.sh && sh harden.sh {flags} --no-color --config {remote_dir}/rampart.conf"
        if guest.get("sudo", True):
            inner = "su -m root -c " + json.dumps(inner)
    else:
        inner = f"cd {remote_dir} && chmod +x harden.sh && bash harden.sh {flags} --no-color --config {remote_dir}/rampart.conf"
        if guest.get("sudo", True):
            inner = "sudo -n " + inner
    ssh, env = _remote(image, runtime, inner)
    log(f"running the script in {mode} mode (output is streamed below)")
    exit_code = _stream(ssh, env, log, cancel, "run")

    log("collecting findings and the per-kind logs from the guest")
    # tar keeps one round trip and every file's name; the script writes to /root/cyberpatriot.
    if guest.get("sudo", True) and image.get("family") != "freebsd":
        pick = "sudo -n sh -c"
    else:
        pick = "sh -c"
    inner = (
        f"{pick} 'cd /root 2>/dev/null || cd /home/{guest.get('user') or 'root'}; "
        "tar czf /tmp/rampart-report.tgz cyberpatriot/logs-* cyberpatriot/findings-* cyberpatriot/harden-*.log 2>/dev/null || true; chmod 644 /tmp/rampart-report.tgz 2>/dev/null || true'"
    )
    ssh, env = _remote(image, runtime, inner)
    _stream(ssh, env, log, cancel, "collect", quiet=True)
    target = collected / "report.tgz"
    scp, env = _scp(image, runtime)
    _run(scp + [f'{guest.get("user") or "root"}@{guest["host"]}:/tmp/rampart-report.tgz', str(target)], env, log, cancel, "download report", quiet=True)
    if target.exists():
        try:
            with tarfile.open(target) as tf:
                tf.extractall(collected)
        except tarfile.TarError as exc:
            log(f"could not unpack the report archive: {exc}")
    findings = _find_findings(collected, log)
    return {"exitCode": exit_code, "findings": findings}


def _run_windows(image, runtime, run_dir, payload, conf, mode, log, collected, cancel) -> dict:
    ps = shutil.which("pwsh") or shutil.which("powershell")
    if not ps:
        raise RunnerError("Windows images need PowerShell on the range host for WinRM remoting")
    guest = _guest(image, runtime)
    user = guest.get("user") or "Administrator"
    pw_env = guest.get("passwordEnv") or "RAMPART_WIN_PASSWORD"
    if not os.environ.get(pw_env):
        raise RunnerError(
            f"set the environment variable {pw_env} on the range host to the guest password "
            "(images.json: guest.passwordEnv names it). It is never written to disk."
        )
    remote = "C:\\rampart"
    script = f"""
$ErrorActionPreference = 'Stop'
$pw = ConvertTo-SecureString $env:{pw_env} -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential('{user}', $pw)
$session = New-PSSession -ComputerName '{guest["host"]}' -Port {guest["port"]} -Credential $cred -Authentication Negotiate
try {{
  Invoke-Command -Session $session -ScriptBlock {{ param($d) if (Test-Path $d) {{ Remove-Item $d -Recurse -Force }}; New-Item -ItemType Directory -Path $d | Out-Null }} -ArgumentList '{remote}'
  $files = @({",".join("'" + str(p) + "'" for p in payload.glob("*"))})
  foreach ($f in $files) {{ Copy-Item -Path $f -Destination '{remote}' -ToSession $session }}
  $mode = '{'Audit' if mode == 'audit' else 'Apply'}'
  $code = Invoke-Command -Session $session -ScriptBlock {{
    param($d, $m)
    Set-Location $d
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $d 'Harden.ps1') -Mode $m -Config (Join-Path $d 'rampart-readme.psd1') -Yes
    exit $LASTEXITCODE
  }} -ArgumentList '{remote}', $mode
  Invoke-Command -Session $session -ScriptBlock {{
    param($d)
    $out = Join-Path $d 'report'
    New-Item -ItemType Directory -Path $out -Force | Out-Null
    Get-ChildItem 'C:\\harden-toolkit' -Filter 'findings-*' | Copy-Item -Destination $out -Force
    Get-ChildItem 'C:\\harden-toolkit' -Directory -Filter 'logs-*' | Copy-Item -Destination $out -Recurse -Force
  }} -ArgumentList '{remote}'
  $dest = '{str(collected).replace(chr(92), chr(92) * 2)}'
  Copy-Item -Path "$remote\\report\\*" -Destination $dest -Recurse -Force -FromSession $session
  Write-Output "RAMPART_EXIT=$code"
}} finally {{
  Remove-PSSession $session -ErrorAction SilentlyContinue
}}
"""
    log("running Harden.ps1 through WinRM (the password comes from an environment variable)")
    exit_code = _run([ps, "-NoProfile", "-NonInteractive", "-Command", script], dict(os.environ), log, cancel, "winrm")
    findings = _find_findings(collected, log)
    return {"exitCode": exit_code, "findings": findings}


def _run(cmd: list[str], env: dict, log, cancel, what: str, quiet: bool = False) -> int:
    if cancel is not None and cancel.is_set():
        raise RunnerError("cancelled")
    log(f"{what}: {' '.join(cmd[:2])} ...")
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    except FileNotFoundError as exc:
        raise RunnerError(f"{what} failed: {exc.strerror} ({cmd[0]})") from exc
    except subprocess.TimeoutExpired as exc:
        raise RunnerError(f"{what} timed out after 10 minutes") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise RunnerError(f"{what} failed ({proc.returncode}): " + (detail[-1] if detail else "no output"))
    return proc.returncode


def _stream(cmd: list[str], env: dict, log, cancel, what: str, quiet: bool = False) -> int:
    if cancel is not None and cancel.is_set():
        raise RunnerError("cancelled")
    try:
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except FileNotFoundError as exc:
        raise RunnerError(f"{what} failed: {exc.strerror} ({cmd[0]})") from exc
    assert proc.stdout is not None
    for line in proc.stdout:
        if cancel is not None and cancel.is_set():
            proc.kill()
            raise RunnerError("cancelled")
        line = line.rstrip()
        if line and not quiet:
            log(line)
    return proc.wait()


def _find_findings(collected: Path, log) -> dict | None:
    candidates = sorted(glob.glob(str(collected / "**" / "findings-*.json"), recursive=True), reverse=True)
    for path in candidates:
        try:
            data = json.loads(Path(path).read_text())
            if isinstance(data, dict) and isinstance(data.get("results"), list):
                log(f"findings JSON collected: {Path(path).name} ({len(data['results'])} results)")
                return data
        except (OSError, json.JSONDecodeError):
            continue
    # Older images ran an older harden.sh: turn its text report into the same shape.
    candidates = sorted(glob.glob(str(collected / "**" / "findings-*.txt"), recursive=True), reverse=True)
    for path in candidates:
        results = []
        for line in Path(path).read_text(errors="replace").splitlines():
            m = re.match(r"^- \[ \] (\w+)\s+\(([^)]+)\)\s+(.*)$", line)
            if m:
                results.append({"status": m.group(1), "section": m.group(2), "text": m.group(3)})
        if results:
            log(f"text report collected: {Path(path).name} ({len(results)} items; run the current script for per-kind logs)")
            return {"tool": "harden.sh", "legacy": True, "results": results}
    log("no findings file came back from the guest")
    return None
