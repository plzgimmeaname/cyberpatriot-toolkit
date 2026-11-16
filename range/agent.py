#!/usr/bin/env python3
"""Rampart Range agent - runs CyberPatriot practice images on this computer
and reports to the website's Practice range page (site/src/pages/range.astro).

    python3 range/agent.py --catalog range/images.json

The agent listens on 127.0.0.1 only, needs a bearer token (generated on first
run and stored in the data folder), and never lets the browser choose a command:
the browser can only pick an image id and audit/apply.

Endpoints (JSON):
    GET    /api/health                 version + what this host can do
    GET    /api/images                 catalog with pull state
    POST   /api/images/{id}/pull       download / unpack / verify (one at a time)
    GET    /api/runs                   every run, newest first
    POST   /api/runs                   {imageId, mode, config}
    GET    /api/runs/{id}              state, summary, error
    GET    /api/runs/{id}/log?offset=  live log tail
    GET    /api/runs/{id}/logs         the per-kind log files (03-apps-installed...)
    GET    /api/runs/{id}/findings     findings-*.json
    POST   /api/runs/{id}/stop         cancel and power off
    DELETE /api/runs/{id}              forget a finished run (deletes its folder)

No third-party packages: Python 3.9+ standard library only. SSH, scp and QEMU
are external programs (see range/README.md).
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import queue
import re
import secrets
import shutil
import socket
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import catalog as catalog_mod
import screen as screen_mod  # noqa: E402
import providers  # noqa: E402
import runner  # noqa: E402

VERSION = "1.0.0"
MAX_BODY = 1 << 20
MAX_LOG_BYTES = 2 << 20


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_id(image_id: str) -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"[^A-Za-z0-9_.-]", "-", image_id)[:40]


def counts(results: list[dict]) -> dict:
    out = {"OK": 0, "CHANGED": 0, "WOULD": 0, "SKIPPED": 0, "REVIEW": 0, "FAILED": 0}
    for item in results:
        status = item.get("status")
        if status in out:
            out[status] += 1
    return out


class Range:
    """Everything the HTTP layer is allowed to do."""

    def __init__(self, args: argparse.Namespace):
        self.repo = Path(args.repo).resolve()
        self.data = Path(os.path.expanduser(args.data)).resolve()
        self.data.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.data / "runs"
        self.runs_dir.mkdir(exist_ok=True)
        self.catalog = catalog_mod.Catalog(Path(args.catalog), self.data)
        self.lock = threading.RLock()
        self.runs: dict[str, dict] = {}
        self.cancels: dict[str, threading.Event] = {}
        self.active: str | None = None
        self.job = queue.Queue()
        self.jobs: set[str] = set()
        self.sessions: dict[str, dict] = {}
        self.session_cancels: dict[str, threading.Event] = {}
        self.sessions_file = self.data / "sessions.json"
        self.screen_cache: dict[str, tuple[int, bytes]] = {}
        self.vnc_secrets: dict[str, str] = {}
        self._load()
        self._load_sessions()
        threading.Thread(target=self._worker, daemon=True, name="range-worker").start()

    # -- persistence -------------------------------------------------------
    def _load(self) -> None:
        path = self.data / "runs.json"
        try:
            for entry in json.loads(path.read_text()):
                if entry.get("id") and (self.runs_dir / entry["id"]).is_dir():
                    if entry.get("state") in {"queued", "preparing", "running", "stopping"}:
                        entry["state"] = "interrupted"
                        entry["error"] = "the agent stopped while this run was going; start it again"
                    self.runs[entry["id"]] = entry
        except (OSError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        with self.lock:
            path = self.data / "runs.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(list(self.runs.values()), indent=2, sort_keys=True))
            tmp.replace(path)

    # -- job queue (one image at a time: a laptop cannot boot five at once) --
    def _worker(self) -> None:
        while True:
            fn, args = self.job.get()
            try:
                fn(*args)
            except Exception:  # never kill the worker
                traceback.print_exc()
            finally:
                self.job.task_done()

    def submit(self, fn, *args) -> None:
        self.job.put((fn, args))

    # -- images --------------------------------------------------------------
    def images(self) -> list[dict]:
        return [self.catalog.describe(entry) for entry in self.catalog.entries]

    def pull(self, image_id: str, password: str | None = None, then=None) -> dict:
        if self.catalog.get(image_id) is None:
            raise KeyError(image_id)
        with self.lock:
            if image_id in self.jobs:
                return {"ok": True, "detail": "already being pulled"}
            self.jobs.add(image_id)
        log_path = self.catalog.image_dir(image_id) / "pull.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        def write(text: str) -> None:
            line = f"{datetime.now().strftime('%H:%M:%S')} {text}\n"
            with log_path.open("a") as fh:
                fh.write(line)

        def work() -> None:
            try:
                self.catalog.pull(image_id, write, password=password)
                if then is not None:
                    then()
            except catalog_mod.CatalogError as exc:
                write(f"ERROR {exc}")
            except Exception as exc:  # unexpected: still show it in the UI
                write(f"ERROR {exc}\n{traceback.format_exc()}")
                self.catalog.save_state(image_id, state="error", detail=str(exc))
            finally:
                with self.lock:
                    self.jobs.discard(image_id)

        self.submit(work)
        return {"ok": True, "detail": "started"}

    def add_image(self, body: dict) -> dict:
        """Take a pasted download link (+ optional unzip password) from the page."""
        url = str(body.get("url") or "").strip()
        if not re.match(r"^https?://", url):
            raise ValueError("paste a full http:// or https:// link to the image (ZIP, OVA, qcow2...)")
        name = str(body.get("name") or "").strip()
        stem = Path(urlparse(url).path).stem
        if not name:
            name = stem or "practice image"
        family = str(body.get("family") or "").lower()
        if family not in {"windows", "linux", "freebsd"}:
            family = catalog_mod.guess_family(f"{name} {url}")
        script = "windows" if family == "windows" else ("freebsd" if family == "freebsd" else "linux")
        base = catalog_mod.clean_id(stem or name)
        with self.lock:
            taken = {entry["id"] for entry in self.catalog.entries}
        image_id = base
        counter = 2
        while image_id in taken:
            image_id = f"{base}-{counter}"
            counter += 1

        guest: dict = {"user": str(body.get("user") or ("Administrator" if family == "windows" else "student"))}
        if family == "windows":
            guest["passwordEnv"] = "RAMPART_WIN_PASSWORD"
            if body.get("winrmPort"):
                guest["winrmPort"] = int(body["winrmPort"])
            if body.get("desktopOnly") or not os.environ.get("RAMPART_WIN_PASSWORD"):
                guest["desktopOnly"] = True
        else:
            key = str(body.get("keyFile") or "").strip()
            if key:
                guest["keyFile"] = key
            else:
                # A stock image has no key installed: it can still be booted and used from the live desktop.
                guest["desktopOnly"] = True
        entry: dict = {
            "id": image_id,
            "name": name,
            "family": family,
            "osName": str(body.get("osName") or ""),
            "script": script,
            "source": {"kind": "url", "url": url},
            "guest": guest,
            "notes": "Added from the Practice range page.",
        }
        checksum = str(body.get("sha256") or "").strip().lower()
        if checksum:
            entry["source"]["sha256"] = checksum
        if body.get("diskFile"):
            entry["disk"] = {"file": str(body["diskFile"])}
        self.catalog.add_image(entry)

        password = str(body.get("password") or "")
        boot = bool(body.get("boot"))
        log_path = self.catalog.image_dir(image_id) / "pull.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a") as fh:
            fh.write(f"{datetime.now().strftime('%H:%M:%S')} added from the page: {url}\n")
        then = (lambda: self.boot_image(image_id)) if boot else None
        self.pull(image_id, password or None, then)
        return {"id": image_id, "image": self.catalog.describe(entry)}

    # -- booted VMs (sessions) ----------------------------------------------
    def _session_log(self, sid: str, text: str) -> None:
        path = self.data / "sessions" / f"{sid}.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as fh:
            fh.write(f"{datetime.now().strftime('%H:%M:%S')} {text}\n")

    def _save_sessions(self) -> None:
        with self.lock:
            tmp = self.sessions_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(list(self.sessions.values()), indent=2, sort_keys=True))
            tmp.replace(self.sessions_file)

    def _load_sessions(self) -> None:
        try:
            data = json.loads(self.sessions_file.read_text())
        except (OSError, json.JSONDecodeError):
            return
        for entry in data:
            if not entry.get("id"):
                continue
            if entry.get("state") in {"booting", "running", "stopping"}:
                if entry.get("runtime"):
                    providers.force_stop(entry["runtime"])
                entry["state"] = "interrupted"
                entry["detail"] = "the agent was closed while this VM was booted; the VM was shut down"
            self.sessions[entry["id"]] = entry

    def boot_image(self, image_id: str, desktop_only: bool = False) -> dict:
        image = self.catalog.get(image_id)
        if image is None:
            raise KeyError(image_id)
        desktop_only = bool(desktop_only or (image.get("guest") or {}).get("desktopOnly"))
        if self.catalog.base_disk(image_id) is None:
            raise ValueError("pull the image before booting it")
        with self.lock:
            for session in self.sessions.values():
                if session["imageId"] == image_id and session["state"] in {"booting", "running"}:
                    return {"id": session["id"], "reused": True}
            sid = "vm-" + datetime.now().strftime("%H%M%S") + "-" + secrets.token_hex(2) + "-" + catalog_mod.clean_id(image_id)
            self.sessions[sid] = {
                "id": sid,
                "imageId": image_id,
                "imageName": image.get("name", image_id),
                "state": "booting",
                "startedAt": now(),
                "stoppedAt": None,
                "detail": "starting the hypervisor",
                "provider": None,
                "runtime": None,
                "console": None,
                "host": None,
                "port": None,
                "desktopOnly": bool(desktop_only),
            }
            self.session_cancels[sid] = threading.Event()
        self._save_sessions()
        self.submit(self._boot_worker, sid, image)
        return {"id": sid, "reused": False}

    def _boot_worker(self, sid: str, image: dict) -> None:
        session = self.sessions[sid]
        provider = None
        runtime = None
        cancel = self.session_cancels[sid]
        log = lambda text: self._session_log(sid, text)  # noqa: E731
        run_dir = self.data / "sessions" / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            base = self.catalog.base_disk(image["id"])
            if base is None:
                raise RuntimeError("the image was removed from the data folder; pull it again")
            if session.get("desktopOnly"):
                # Stock CyberPatriot images have no SSH key or WinRM: boot them anyway and just show the desktop.
                image = {**image, "guest": {**(image.get("guest") or {}), "waitForGuest": False}}
            provider = providers.for_image(image)
            ok, why = provider.available()
            log(f"provider: {provider.name} ({why})")
            if not ok:
                raise providers.ProviderError(f"{provider.name} is not usable: {why}")
            session["provider"] = provider.name
            with self.lock:
                session["detail"] = f"booting with {provider.name}"
            self._save_sessions()
            def early(rt: dict) -> None:
                # QEMU is up but the guest is still booting: show the desktop now, and remember the
                # runtime so a failed boot still shuts the VM down.
                nonlocal runtime
                password = rt.pop("vncPassword", None)
                if password:
                    self.vnc_secrets[sid] = password  # memory only: never written to sessions.json
                runtime = rt
                with self.lock:
                    session["runtime"] = rt
                self._save_sessions()

            if provider.name == "qemu":
                runtime = provider.start(image, base, run_dir, log, cancel, early=early)
            else:
                runtime = provider.start(image, base, run_dir, log, cancel)
            runtime.pop("vncPassword", None)
            with self.lock:
                session.update(
                    state="running",
                    runtime=runtime,
                    console=runtime.get("console"),
                    host=runtime.get("host") or "127.0.0.1",
                    port=runtime.get("port") or runtime.get("sshPort") or runtime.get("winrmPort"),
                    detail="booted - the VM is waiting for you",
                )
            self._save_sessions()
            log("VM is up. Use Run audit to harden it, or connect to it yourself.")
        except Exception as exc:
            state = "stopped" if cancel.is_set() else "failed"
            with self.lock:
                session.update(state=state, detail=str(exc) if state == "failed" else "stopped before it finished booting")
            log(f"{state.upper()}: {exc}")
            if runtime is not None and provider is not None:
                try:
                    provider.stop(runtime, log)
                except Exception as stop_exc:
                    log(f"cleanup: {stop_exc}")
            self._save_sessions()
        finally:
            with self.lock:
                self.session_cancels.pop(sid, None)

    def stop_session(self, sid: str) -> dict:
        with self.lock:
            session = self.sessions.get(sid)
            if session is None:
                raise KeyError(sid)
            cancel = self.session_cancels.get(sid)
            runtime = session.get("runtime")
            provider = providers.by_name(session.get("provider"))
            session["state"] = "stopping"
        if cancel is not None:
            cancel.set()
        log = lambda text: self._session_log(sid, text)  # noqa: E731
        if runtime and provider:
            try:
                provider.stop(runtime, log)
            except Exception as exc:
                log(f"stopping: {exc}")
        with self.lock:
            session.update(state="stopped", stoppedAt=now(), detail="stopped")
            session["runtime"] = None
            self.vnc_secrets.pop(sid, None)
        self._save_sessions()
        return {"ok": True}

    def reset_session(self, sid: str) -> dict:
        """Power off the VM, delete its overlay and boot the original image again."""
        with self.lock:
            session = self.sessions.get(sid)
        if session is None:
            raise KeyError(sid)
        image = self.catalog.get(session["imageId"])
        if image is None:
            raise KeyError(session["imageId"])
        self.stop_session(sid)
        deadline = time.time() + 15
        while sid in self.session_cancels and time.time() < deadline:
            time.sleep(0.1)
        with self.lock:
            self.sessions.pop(sid, None)
        shutil.rmtree(self.data / "sessions" / sid, ignore_errors=True)
        (self.data / "sessions" / f"{sid}.log").unlink(missing_ok=True)
        self._save_sessions()
        return {"reset": True, **self.boot_image(image["id"], bool(session.get("desktopOnly")))}

    def _reap_dead(self, sid: str) -> None:
        """A QEMU that crashed or was killed must not stay listed as running."""
        session = self.sessions[sid]
        runtime = session.get("runtime") or {}
        pidfile = Path(runtime.get("pidfile") or "")
        if session.get("provider") != "qemu" or session["state"] != "running" or not pidfile.exists():
            return
        try:
            os.kill(int(pidfile.read_text().strip()), 0)
        except ProcessLookupError:
            with self.lock:
                session.update(state="stopped", stoppedAt=now(), detail="the VM process ended (shut down or crashed)", runtime=None)
                self.vnc_secrets.pop(sid, None)
            self._session_log(sid, "the QEMU process is gone")
            self._save_sessions()
        except (ValueError, OSError):
            pass

    def public_session(self, sid: str) -> dict:
        self._reap_dead(sid)
        session = self.sessions[sid]
        out = {k: v for k, v in session.items() if k != "runtime"}
        console = session.get("console")
        out["consoleAvailable"] = bool(console and Path(console).exists())
        out["screenAvailable"] = session.get("provider") == "qemu" and bool((session.get("runtime") or {}).get("monitor"))
        out["desktopAvailable"] = bool(
            session.get("provider") == "qemu"
            and session["state"] in {"running", "booting"}
            and (session.get("runtime") or {}).get("vncWsPort")
            and sid in self.vnc_secrets
        )
        out["canRun"] = session["state"] == "running" and not session.get("desktopOnly")
        return out

    def session_desktop(self, sid: str) -> dict:
        """What the page's noVNC viewer needs: a loopback WebSocket address and the one-time password."""
        with self.lock:
            session = self.sessions.get(sid)
            if session is None:
                raise KeyError(sid)
            runtime = session.get("runtime") or {}
            port = runtime.get("vncWsPort")
            password = self.vnc_secrets.get(sid)
        if session.get("provider") != "qemu" or not port or not password or session["state"] != "running":
            raise ValueError("this VM has no live desktop: it needs the qemu provider and to be fully booted")
        return {"host": "127.0.0.1", "port": port, "password": password, "path": ""}

    def sessions_public(self) -> list[dict]:
        with self.lock:
            ids = list(self.sessions)
        return sorted((self.public_session(sid) for sid in ids), key=lambda s: s["startedAt"], reverse=True)

    def session_screen(self, sid: str) -> bytes:
        with self.lock:
            session = self.sessions.get(sid)
            runtime = dict(session["runtime"]) if session and session.get("runtime") else None
            provider_name = session.get("provider") if session else None
        if session is None:
            raise KeyError(sid)
        if runtime is None or provider_name != "qemu":
            raise ValueError("this VM has no live screen: frames come from QEMU, so boot it with the qemu provider")
        frame = providers.qemu_screendump(runtime)
        if frame is None:
            raise ValueError("QEMU did not return a frame yet (the guest may still be booting)")
        stamp = frame.stat().st_mtime_ns
        cached = self.screen_cache.get(str(frame))
        if cached and cached[0] == stamp:
            return cached[1]
        png = screen_mod.ppm_to_png(frame.read_bytes())
        self.screen_cache[str(frame)] = (stamp, png)
        return png

    def session_console(self, sid: str, offset: int) -> dict:
        with self.lock:
            session = self.sessions.get(sid)
        if session is None:
            raise KeyError(sid)
        console = session.get("console") or ""
        path = Path(console) if console else None
        source = "console"
        if path is None or not path.exists():
            path = self.data / "sessions" / f"{sid}.log"
            source = "agent"
        if not path.exists():
            return {"offset": 0, "size": 0, "text": "", "source": source}
        size = path.stat().st_size
        if offset > size:
            offset = 0
        with path.open("rb") as fh:
            fh.seek(offset)
            chunk = fh.read(131072)
        return {"offset": offset + len(chunk), "size": size, "text": chunk.decode("utf-8", "replace"), "source": source}

    # -- runs --------------------------------------------------------------
    def start_run(self, body: dict) -> dict:
        image_id = str(body.get("imageId") or "")
        image = self.catalog.get(image_id)
        if image is None:
            raise ValueError("unknown image")
        mode = str(body.get("mode") or "audit").lower()
        if mode not in {"audit", "apply"}:
            raise ValueError("mode must be audit or apply")
        if body.get("mode") == "apply" and not body.get("confirmApply"):
            raise ValueError("apply needs confirmApply: true (it changes the VM)")
        if self.catalog.base_disk(image_id) is None:
            raise ValueError("this image is not pulled yet")
        session_id = str(body.get("sessionId") or "") or None
        if session_id:
            with self.lock:
                session = self.sessions.get(session_id)
            if session is None or session["imageId"] != image_id:
                raise ValueError("that booted VM belongs to a different image")
            if session["state"] != "running":
                raise RuntimeError("that booted VM is not running any more; boot the image again")
        with self.lock:
            if self.active:
                raise RuntimeError("a run is already going; wait for it to finish")
            rid = run_id(image_id)
            run_dir = self.runs_dir / rid
            run_dir.mkdir(parents=True)
            config = body.get("config") or {}
            if not isinstance(config, dict):
                raise ValueError("config must be an object")
            record = {
                "id": rid,
                "imageId": image_id,
                "imageName": image.get("name", image_id),
                "family": image.get("family"),
                "mode": mode,
                "state": "queued",
                "startedAt": now(),
                "finishedAt": None,
                "error": None,
                "summary": None,
                "provider": None,
                "sessionId": session_id,
                "readme": {
                    "admins": runner.clean_names(config.get("admins")),
                    "users": runner.clean_names(config.get("users")),
                    "critical": [c.lower() for c in runner.clean_names(config.get("critical"))],
                },
            }
            self.runs[rid] = record
            self.cancels[rid] = threading.Event()
            self.active = rid
        self._save()
        self.submit(self._execute, rid, image, record, config, mode, session_id)
        return {"id": rid}

    def _write_log(self, rid: str, text: str) -> None:
        path = self.runs_dir / rid / "log.txt"
        with self.lock:
            with path.open("a") as fh:
                fh.write(f"{datetime.now().strftime('%H:%M:%S')} {text}\n")

    def _set(self, rid: str, **fields) -> None:
        with self.lock:
            self.runs[rid].update(fields)
        self._save()

    def _execute(self, rid: str, image: dict, record: dict, config: dict, mode: str, session_id: str | None = None) -> None:
        run_dir = self.runs_dir / rid
        cancel = self.cancels[rid]
        provider = None
        runtime = None
        owns_vm = session_id is None
        log = lambda text: self._write_log(rid, text)  # noqa: E731
        try:
            if session_id:
                with self.lock:
                    session = self.sessions.get(session_id)
                    runtime = dict(session["runtime"]) if session and session.get("runtime") else None
                    provider_name = session.get("provider") if session else None
                if runtime is None:
                    raise RuntimeError("the booted VM is no longer running")
                provider = providers.by_name(provider_name)
                self._set(rid, state="preparing", provider=provider_name)
                log("using the VM already booted for this image: it is not restarted and stays running afterwards")
                log(f"mode: {mode.upper()}   image: {image.get('name')}   script: {image['script']}")
            else:
                base = self.catalog.base_disk(image["id"])
                if base is None:
                    raise RuntimeError("the image disappeared from the data folder; pull it again")
                provider = providers.for_image(image)
                ok, why = provider.available()
                self._set(rid, state="preparing", provider=provider.name)
                log(f"provider: {provider.name} ({why})")
                if not ok:
                    raise providers.ProviderError(f"{provider.name} is not usable: {why}")
                log(f"mode: {mode.upper()}   image: {image.get('name')}   script: {image['script']}")
                runtime = provider.start(image, base, run_dir, log, cancel)
            self._set(rid, state="running")
            result = runner.run_script(image, runtime, self.repo, run_dir, config, mode, log, cancel)
            findings = result.get("findings")
            if findings:
                (run_dir / "findings.json").write_text(json.dumps(findings, indent=2))
                summary = counts(findings.get("results", []))
                self._set(rid, summary=summary, state="done", error=None)
                log("summary: " + ", ".join(f"{k} {v}" for k, v in summary.items()))
            else:
                self._set(rid, state="done", error="the script finished but no findings file came back")
                log("no findings file came back - check the log above")
            if result.get("exitCode") not in (0, None):
                log(f"the script finished with exit code {result['exitCode']}")
        except runner.RunnerError as exc:
            log(f"ERROR {exc}")
            self._set(rid, state="failed", error=str(exc))
        except providers.ProviderError as exc:
            log(f"ERROR {exc}")
            self._set(rid, state="failed", error=str(exc))
        except Exception as exc:
            log(f"ERROR {exc}\n{traceback.format_exc()}")
            self._set(rid, state="failed", error=str(exc))
        finally:
            if runtime is not None and provider is not None and owns_vm:
                try:
                    provider.stop(runtime, log)
                except Exception as exc:
                    log(f"cleanup: {exc}")
            self._set(rid, finishedAt=now())
            if self.runs[rid]["state"] in {"queued", "preparing", "running"}:
                self._set(rid, state="done" if self.runs[rid].get("summary") else "failed")
            with self.lock:
                self.cancels.pop(rid, None)
                if self.active == rid:
                    self.active = None

    def stop_run(self, rid: str) -> dict:
        ev = self.cancels.get(rid)
        if not ev:
            raise KeyError(rid)
        ev.set()
        self._set(rid, state="stopping")
        return {"ok": True}

    def delete_run(self, rid: str) -> dict:
        with self.lock:
            if self.active == rid:
                raise RuntimeError("stop the run before deleting it")
            if rid not in self.runs:
                raise KeyError(rid)
            self.runs.pop(rid)
        shutil.rmtree(self.runs_dir / rid, ignore_errors=True)
        self._save()
        return {"ok": True}

    def log_tail(self, rid: str, offset: int) -> dict:
        path = self.runs_dir / rid / "log.txt"
        size = path.stat().st_size if path.exists() else 0
        if offset > size:
            offset = 0
        with path.open("rb") as fh:
            fh.seek(offset)
            chunk = fh.read(262144)
        return {"offset": offset + len(chunk), "size": size, "text": chunk.decode("utf-8", "replace")}

    def collected_logs(self, rid: str) -> dict:
        run_dir = self.runs_dir / rid
        files: dict[str, str] = {}
        for path in sorted(run_dir.rglob("*.txt")):
            if "collected" not in path.parts:
                continue
            if path.stat().st_size > MAX_LOG_BYTES:
                files[path.name] = f"(too large to show: {path.stat().st_size // 1024} KiB)"
                continue
            try:
                files[path.name] = path.read_text(errors="replace")
            except OSError as exc:
                files[path.name] = f"(could not read: {exc})"
        return {"files": files}

    def findings(self, rid: str) -> dict:
        path = self.runs_dir / rid / "findings.json"
        if not path.exists():
            raise KeyError("findings")
        return json.loads(path.read_text())

    def public_run(self, rid: str) -> dict:
        record = self.runs[rid]
        out = dict(record)
        out["logBytes"] = (self.runs_dir / rid / "log.txt").stat().st_size if (self.runs_dir / rid / "log.txt").exists() else 0
        return out


class Handler(BaseHTTPRequestHandler):
    server_version = f"RampartRange/{VERSION}"
    range: Range
    token: str
    origins: list[str]
    quiet: bool

    def log_message(self, fmt, *args):  # noqa: D401 - keep the console readable
        if not self.quiet:
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # -- helpers -----------------------------------------------------------
    def _cors(self) -> None:
        origin = self.headers.get("Origin", "")
        allowed = False
        if origin:
            if origin in self.origins:
                allowed = True
            elif re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", origin):
                allowed = True
            elif re.match(r"^https://[a-z0-9-]+\.style\.dev$", origin):
                allowed = True
            elif any(origin.startswith(o) for o in self.origins):
                allowed = True
        if allowed:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Max-Age", "600")

    def _send(self, code: int, body, content_type: str = "application/json") -> None:
        if isinstance(body, (dict, list)):
            payload = json.dumps(body).encode()
            content_type = "application/json"
        elif isinstance(body, str):
            payload = body.encode()
        else:
            payload = body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _error(self, code: int, message: str) -> None:
        self._send(code, {"error": message})

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            given = header[7:].strip()
        else:
            given = self.headers.get("X-Range-Token", "")
        return bool(given) and hmac.compare_digest(given, self.token)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise ValueError("request body too large")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("body must be a JSON object")
        return data

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if path == "/api/health":
            self._send(200, {
                "ok": True,
                "version": VERSION,
                "authRequired": True,
                "provider": "loopback" if self.server.server_address[0] in {"127.0.0.1", "::1"} else "network",
            })
            return
        if not self._authorized():
            self._error(401, "missing or wrong token: open the Practice range page and paste the token the agent printed")
            return
        rng = self.range
        try:
            if path == "/api/capabilities":
                self._send(200, {"capabilities": providers.capabilities(), "repo": str(rng.repo), "data": str(rng.data)})
            elif path == "/api/images":
                self._send(200, {"images": rng.images()})
            elif path == "/api/runs":
                with rng.lock:
                    runs = sorted(rng.runs.values(), key=lambda r: r["startedAt"], reverse=True)
                self._send(200, {"runs": runs})
            elif path == "/api/sessions":
                self._send(200, {"sessions": rng.sessions_public()})
            else:
                m = re.match(r"^/api/sessions/([A-Za-z0-9_.-]+)/screen$", path)
                if m:
                    self._send(200, rng.session_screen(m.group(1)), "image/png")
                    return
                m = re.match(r"^/api/sessions/([A-Za-z0-9_.-]+)/desktop$", path)
                if m:
                    self._send(200, rng.session_desktop(m.group(1)))
                    return
                m = re.match(r"^/api/sessions/([A-Za-z0-9_.-]+)/console$", path)
                if m:
                    offset = int(query.get("offset", ["0"])[0] or 0)
                    self._send(200, rng.session_console(m.group(1), max(0, offset)))
                    return
                m = re.match(r"^/api/sessions/([A-Za-z0-9_.-]+)$", path)
                if m:
                    self._send(200, rng.public_session(m.group(1)))
                    return
                m = re.match(r"^/api/runs/([A-Za-z0-9_.-]+)$", path)
                if m:
                    rid = m.group(1)
                    with rng.lock:
                        if rid not in rng.runs:
                            raise KeyError(rid)
                    self._send(200, rng.public_run(rid))
                    return
                m = re.match(r"^/api/runs/([A-Za-z0-9_.-]+)/log$", path)
                if m:
                    offset = int(query.get("offset", ["0"])[0] or 0)
                    self._send(200, rng.log_tail(m.group(1), max(0, offset)))
                    return
                m = re.match(r"^/api/runs/([A-Za-z0-9_.-]+)/logs$", path)
                if m:
                    self._send(200, rng.collected_logs(m.group(1)))
                    return
                m = re.match(r"^/api/runs/([A-Za-z0-9_.-]+)/findings$", path)
                if m:
                    self._send(200, rng.findings(m.group(1)))
                    return
                m = re.match(r"^/api/images/([A-Za-z0-9_.-]+)$", path)
                if m:
                    image = rng.catalog.get(m.group(1))
                    if image is None:
                        raise KeyError(m.group(1))
                    self._send(200, rng.catalog.describe(image))
                    return
                self._error(404, "no such endpoint")
        except KeyError:
            self._error(404, "not found")
        except ValueError as exc:
            self._error(400, str(exc))

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._error(401, "missing or wrong token")
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        rng = self.range
        try:
            if path == "/api/images/add":
                self._send(202, rng.add_image(self._body()))
                return
            if path == "/api/runs":
                self._send(202, rng.start_run(self._body()))
                return
            m = re.match(r"^/api/runs/([A-Za-z0-9_.-]+)/stop$", path)
            if m:
                self._send(200, rng.stop_run(m.group(1)))
                return
            m = re.match(r"^/api/images/([A-Za-z0-9_.-]+)/pull$", path)
            if m:
                self._send(202, rng.pull(m.group(1)))
                return
            m = re.match(r"^/api/images/([A-Za-z0-9_.-]+)/boot$", path)
            if m:
                self._send(202, rng.boot_image(m.group(1), bool(self._body().get("desktopOnly"))))
                return
            m = re.match(r"^/api/sessions/([A-Za-z0-9_.-]+)/reset$", path)
            if m:
                self._send(202, rng.reset_session(m.group(1)))
                return
            m = re.match(r"^/api/sessions/([A-Za-z0-9_.-]+)/stop$", path)
            if m:
                self._send(200, rng.stop_session(m.group(1)))
                return
            self._error(404, "no such endpoint")
        except KeyError as exc:
            self._error(404, f"not found: {exc}")
        except ValueError as exc:
            self._error(400, str(exc))
        except RuntimeError as exc:
            self._error(409, str(exc))
        except Exception as exc:  # keep the server alive, show the reason
            self._error(500, str(exc))

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._authorized():
            self._error(401, "missing or wrong token")
            return
        m = re.match(r"^/api/runs/([A-Za-z0-9_.-]+)$", urlparse(self.path).path.rstrip("/"))
        if not m:
            self._error(404, "no such endpoint")
            return
        try:
            self._send(200, self.range.delete_run(m.group(1)))
        except KeyError:
            self._error(404, "no such run")
        except RuntimeError as exc:
            self._error(409, str(exc))


def token_for(data: Path, wanted: str | None) -> str:
    if wanted:
        return wanted
    path = data / "token"
    if path.exists():
        value = path.read_text().strip()
        if value:
            return value
    value = secrets.token_urlsafe(24)
    path.write_text(value + "\n")
    path.chmod(0o600)
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Rampart Range agent: run practice images, collect the hardening reports.")
    parser.add_argument("--catalog", default=str(HERE / "images.json"), help="image catalog (default: range/images.json)")
    parser.add_argument("--data", default=os.environ.get("RAMPART_DATA", "~/.rampart-range"), help="where downloads and runs are kept")
    parser.add_argument("--repo", default=str(HERE.parent), help="repository root (holds scripts/)")
    parser.add_argument("--host", default="127.0.0.1", help="listen address (default: loopback only)")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--token", default=None, help="bearer token (default: generate once in the data folder)")
    parser.add_argument("--allow-origin", action="append", default=[], help="extra site origin allowed to call the agent")
    parser.add_argument("--print-token", action="store_true", help="print the token and exit")
    parser.add_argument("--quiet", action="store_true", help="no request log")
    args = parser.parse_args(argv)

    data = Path(os.path.expanduser(args.data)).resolve()
    data.mkdir(parents=True, exist_ok=True)
    token = token_for(data, args.token)
    if args.print_token:
        print(token)
        return 0

    origin_arg = args.allow_origin or []
    origins = [
        "https://plzgimmeaname.github.io",
        "http://localhost:4321",
        "http://127.0.0.1:4321",
    ] + origin_arg

    try:
        rng = Range(args)
    except catalog_mod.CatalogError as exc:
        print(f"catalog error: {exc}", file=sys.stderr)
        return 2

    Handler.range = rng
    Handler.token = token
    Handler.origins = origins
    Handler.quiet = args.quiet
    try:
        httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print(f"cannot listen on {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 2

    caps = providers.capabilities()
    print(f"Rampart Range agent {VERSION}")
    print(f"  listening on http://{args.host}:{args.port}")
    print(f"  token:  {token}")
    print(f"  data:   {data}")
    print(f"  images: {args.catalog} ({len(rng.catalog.entries)} in the catalog)")
    if not rng.catalog.entries:
        print("  no images yet: add one from the Practice range page (paste a link + unzip password)")
    print(f"  QEMU: {'yes' if caps['qemu'] else 'no'}   Hyper-V: {'yes' if caps['hyperv'] else 'no'}   ssh: {'yes' if caps['ssh'] else 'no'}")
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        print("  WARNING: listening beyond loopback. Anyone who can reach this port and knows the token can boot images.", file=sys.stderr)
    print("  open the site's Practice range page and paste the token. Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        httpd.server_close()
        with rng.lock:
            active = rng.active
        if active:
            try:
                rng.stop_run(active)
            except KeyError:
                pass
        for session in list(rng.sessions):
            if rng.sessions[session].get("state") in {"booting", "running"}:
                try:
                    rng.stop_session(session)
                except KeyError:
                    pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
