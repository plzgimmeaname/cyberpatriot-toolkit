"""Practice-image catalog for the Rampart range.

An "image" is a virtual-machine disk plus the facts needed to run the hardening
script inside it (OS family, login). CyberPatriot does NOT publish public
download URLs: coaches get the practice images from the competition portal. So
this catalog is a list of *sources you own*:

  * "url"   - an HTTPS address (your file server, NAS, or a link a mentor sent),
              optionally protected by an archive password. A SHA-256 is always
              verified when one is given.
  * "local" - a disk image, .zip, .ova or .tar.gz already on the range host.

Images added from the Practice range page are stored in
<data>/images.local.json and merged with the catalog file, so the page can take
a pasted link without editing JSON by hand. Nothing is downloaded until you
press Pull (or "Download & boot"). The base disk is never modified: providers.py
makes a throw-away overlay for every run.

Archive passwords are used once, in memory, and never written to disk.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

DISK_SUFFIXES = (".qcow2", ".vmdk", ".vhdx", ".vhd", ".raw", ".img", ".qcow")
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".ova", ".7z", ".rar")
FAMILIES = {"windows", "linux", "freebsd"}
SCRIPTS = {"linux": "scripts/linux/harden.sh", "windows": "scripts/windows/Harden.ps1", "freebsd": "scripts/freebsd/harden.sh"}
EXTRACTORS = ("7z", "7zz", "7za", "unar")


class CatalogError(RuntimeError):
    """Something the person running the range can fix (wrong path, bad checksum...)."""


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    return hash_file(path, "sha256", chunk)


def hash_file(path: Path, algo: str, chunk: int = 1 << 20) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


# hex length -> algorithm. A download page may give any of these.
HASH_BY_LENGTH = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}
HASH_LABELS = {"md5": "MD5", "sha1": "SHA-1", "sha256": "SHA-256", "sha512": "SHA-512"}


def parse_checksum(text: str) -> tuple[str, str] | None:
    """Understand whatever was pasted from a download page or a tool.

    Accepts a bare hash (any case, with spaces or colons between bytes), `sha256:HASH`,
    `SHA256 (file) = HASH`, `HASH  *file.zip` (sha256sum / md5sum output) and the
    PowerShell `Get-FileHash` table. The algorithm comes from the label when there is
    one, otherwise from the length (32 = MD5, 40 = SHA-1, 64 = SHA-256, 128 = SHA-512).
    Returns (algorithm, lowercase hex), or None for an empty string. Raises
    CatalogError when it cannot be a checksum, so a typo is caught before a long download.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    label = None
    found = re.search(r"\b(md5|sha-?1|sha-?256|sha-?512)\b", raw, re.I)
    if found:
        label = found.group(1).lower().replace("-", "")
    candidate = None
    patterns = (
        r"(?<![0-9A-Za-z])[0-9a-fA-F]{32,128}(?![0-9A-Za-z])",          # a bare hash
        r"(?<![0-9A-Za-z])(?:[0-9a-fA-F]{2}[: ]){15,63}[0-9a-fA-F]{2}(?![0-9A-Za-z])",  # byte pairs, openssl style
    )
    for pattern in patterns:
        for match in re.finditer(pattern, raw):
            squeezed = re.sub(r"[ :]", "", match.group(0))
            if len(squeezed) in HASH_BY_LENGTH:
                candidate = squeezed.lower()
                break
        if candidate:
            break
    if candidate is None:
        raise CatalogError(
            "that does not look like a checksum: paste the MD5 (32), SHA-1 (40), SHA-256 (64) or SHA-512 (128) "
            "hexadecimal characters from the download page"
        )
    algo = HASH_BY_LENGTH[len(candidate)]
    if label and label != algo:
        raise CatalogError(f"the checksum is labelled {HASH_LABELS[label]} but has the length of a {HASH_LABELS[algo]}")
    return algo, candidate


def source_checksum(source: dict) -> tuple[str, str] | None:
    """The checksum stored for an image: `checksum` ("sha256:HEX") or the older `sha256` field."""
    value = source.get("checksum") or source.get("sha256")
    if not value:
        return None
    try:
        return parse_checksum(str(value))
    except CatalogError:
        return None


def expand(path: str, base: Path | None = None) -> Path:
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    if not p.is_absolute() and base is not None:
        p = base / p
    return p.resolve()


def clean_id(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]", "-", text).strip(".-")
    return value[:48] or "image"


def guess_family(text: str) -> str:
    """Best guess from a file name or URL, so the page can preselect the OS."""
    t = text.lower()
    if "freebsd" in t:
        return "freebsd"
    if re.search(r"windows|win10|win11|win-1[01]|server-?(2016|2019|2022)", t):
        return "windows"
    return "linux"


def validate_entry(entry: object, index: int = 0) -> dict:
    if not isinstance(entry, dict):
        raise CatalogError(f"images[{index}] is not an object")
    for key in ("id", "name", "family", "script"):
        if not entry.get(key):
            raise CatalogError(f'images[{index}] is missing "{key}"')
    if not all(c.isalnum() or c in "-_." for c in str(entry["id"])):
        raise CatalogError(f'image id "{entry["id"]}" may only use letters, numbers, dot, dash and underscore')
    if entry["family"] not in FAMILIES:
        raise CatalogError(f'image {entry["id"]}: family must be one of {sorted(FAMILIES)}')
    if entry["script"] not in SCRIPTS:
        raise CatalogError(f'image {entry["id"]}: script must be one of {sorted(SCRIPTS)}')
    source = entry.get("source") or {}
    if source.get("kind") not in {"local", "url"}:
        raise CatalogError(f'image {entry["id"]}: source.kind must be "local" or "url"')
    if source.get("kind") == "url" and not source.get("url"):
        raise CatalogError(f'image {entry["id"]}: source.url is required for a url source')
    if source.get("kind") == "url" and not re.match(r"^https?://", str(source["url"])):
        raise CatalogError(f'image {entry["id"]}: only http:// and https:// links can be pulled')
    if source.get("kind") == "local" and not source.get("path"):
        raise CatalogError(f'image {entry["id"]}: source.path is required for a local source')
    for field in ("checksum", "sha256"):
        if source.get(field):
            try:
                parse_checksum(str(source[field]))
            except CatalogError as exc:
                raise CatalogError(f'image {entry["id"]}: source.{field}: {exc}') from exc
    return entry


def load_catalog(path: Path) -> list[dict]:
    if not path.exists():
        raise CatalogError(f"catalog not found: {path} (copy images.example.json to images.json, or add an image from the page)")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise CatalogError(f"catalog is not valid JSON: {exc}") from exc
    images = data.get("images")
    if not isinstance(images, list):
        raise CatalogError('catalog has no "images" list')
    seen: set[str] = set()
    out = []
    for i, entry in enumerate(images):
        validate_entry(entry, i)
        if entry["id"] in seen:
            raise CatalogError(f'duplicate image id "{entry["id"]}"')
        seen.add(entry["id"])
        out.append(entry)
    return out


def list_files(dest: Path) -> list[Path]:
    return [p for p in dest.rglob("*") if p.is_file()]


def pick_disk(files: list[Path], wanted: str | None) -> Path:
    if wanted:
        for f in files:
            if f.name == wanted or str(f).endswith(wanted):
                return f
        raise CatalogError(f'the archive has no file named "{wanted}"')
    disks = sorted(
        (f for f in files if f.suffix.lower() in DISK_SUFFIXES and f.stat().st_size > 1024 * 1024),
        key=lambda f: f.stat().st_size,
        reverse=True,
    )
    if not disks:
        raise CatalogError("no disk image (*.qcow2, *.vmdk, *.vhdx, *.raw) found in the archive")
    return disks[0]


def disk_format(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return {"qcow2": "qcow2", "qcow": "qcow2", "vmdk": "vmdk", "vhdx": "vhdx", "vhd": "vpc", "raw": "raw", "img": "raw"}.get(ext, "qcow2")


def _eta(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    if seconds >= 3600:
        return f"{seconds // 3600} h {seconds % 3600 // 60} min"
    if seconds >= 60:
        return f"{seconds // 60} min"
    return f"{seconds} s"


def gib(n: float) -> str:
    return f"{n / (1 << 30):.1f} GiB" if n >= (1 << 30) else f"{n / (1 << 20):.0f} MiB"


class Progress:
    """Throttled progress for long steps: percent for the bar, a sentence for the card, a line in the pull log."""

    def __init__(self, update, log, phase: str):
        self.update, self.log, self.phase = update, log, phase
        self.started = time.time()
        self._last = 0.0
        self._last_pct = -1

    def tick(self, pct: float | None, text: str, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last < 1.0:
            return
        self._last = now
        shown = int(pct) if pct is not None else None
        self.update(shown, f"{self.phase}: {text} · {int(now - self.started)}s")
        if shown is not None and shown // 10 != self._last_pct // 10:
            self._last_pct = shown
            self.log(f"{self.phase} {shown}% ({text})")


def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path, progress: "Progress | None" = None) -> None:
    root = dest.resolve()
    infos = zf.infolist()
    for member in infos:
        target = (dest / member.filename).resolve()
        if not str(target).startswith(str(root)):
            raise CatalogError(f"archive member escapes the folder: {member.filename}")
    total = sum(i.file_size for i in infos) or 1
    done = 0
    for member in infos:  # streamed: a multi-GB disk never sits in memory, and the card shows how far it got
        target = dest / member.filename
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, target.open("wb") as out:
            while True:
                block = src.read(1 << 20)
                if not block:
                    break
                out.write(block)
                done += len(block)
                if progress is not None:
                    progress.tick(done * 100 / total, f"{gib(done)} of {gib(total)}")


def _safe_extract_tar(tf: tarfile.TarFile, dest: Path) -> None:
    root = dest.resolve()
    for member in tf.getmembers():
        target = (dest / member.name).resolve()
        if not str(target).startswith(str(root)):
            raise CatalogError(f"archive member escapes the folder: {member.name}")
        if member.issym() or member.islnk():
            raise CatalogError(f"archive contains a link, refusing to extract: {member.name}")
    tf.extractall(dest)


def _check_zip_members(zf: zipfile.ZipFile, dest: Path) -> None:
    """Refuse paths that escape the folder and symbolic links, before any external tool touches the archive."""
    root = dest.resolve()
    for member in zf.infolist():
        if not str((dest / member.filename).resolve()).startswith(str(root)):
            raise CatalogError(f"archive member escapes the folder: {member.filename}")
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise CatalogError(f"archive contains a link, refusing to extract: {member.filename}")


def _extract_with_unzip(zf: zipfile.ZipFile, archive: Path, dest: Path, password: str, log, progress: "Progress | None") -> None:
    """Password-protected ZIPs: the system `unzip` is native speed; Python's own decryption manages ~2 MB/s."""
    unzip = shutil.which("unzip")
    assert unzip
    _check_zip_members(zf, dest)
    total = sum(i.file_size for i in zf.infolist()) or 1
    log(f"unpacking {archive.name} with unzip (password supplied)")
    # The password is visible in `ps` on this computer while it runs, like the 7-Zip path.
    proc = subprocess.Popen([unzip, "-o", "-q", "-P", password, str(archive), "-d", str(dest)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    holder: dict = {}
    reader = threading.Thread(target=lambda: holder.setdefault("out", proc.communicate()[0]), daemon=True)
    reader.start()
    while reader.is_alive():
        reader.join(1.0)
        if progress is not None:
            written = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
            progress.tick(min(written * 100 / total, 99), f"{gib(written)} of {gib(total)}")
    output = (holder.get("out") or "").strip()
    if proc.returncode != 0:
        if proc.returncode == 82 or "password" in output.lower():  # Info-ZIP: 82 = bad password
            raise CatalogError("wrong unzip password")
        raise CatalogError(f"unzip failed ({proc.returncode}): {output.splitlines()[-1] if output else 'no output'}")


def _extractor() -> str | None:
    for name in EXTRACTORS:
        found = shutil.which(name)
        if found:
            return found
    return None


def _extract_with_7z(archive: Path, dest: Path, password: str | None, log, progress: "Progress | None" = None) -> None:
    tool = _extractor()
    if not tool:
        raise CatalogError(
            f"{archive.name} needs 7-Zip to unpack (AES encryption, .7z or .rar). Install it with "
            "'sudo apt install 7zip' (or 7zip-full) and press Pull again. Never hand this file to a "
            "site you do not trust."
        )
    dest.mkdir(parents=True, exist_ok=True)
    name = Path(tool).name
    if name == "unar":
        cmd = [tool, "-f", "-o", str(dest)]
        if password:
            cmd += ["-p", password]
    else:
        cmd = [tool, "x", "-y", f"-o{dest}"]
        if password:
            # 7-Zip has no stdin password option; this is visible in `ps` for a moment.
            cmd += [f"-p{password}"]
    cmd.append(str(archive))
    log(f"unpacking {archive.name} with {name}" + (" (password supplied)" if password else ""))
    # No percentage from the tool, so show how much has been written so far.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    holder: dict = {}
    reader = threading.Thread(target=lambda: holder.setdefault("out", proc.communicate()[0]), daemon=True)
    reader.start()
    while reader.is_alive():
        reader.join(1.0)
        if progress is not None:
            written = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
            progress.tick(None, f"{gib(written)} written")
    result = type("R", (), {"returncode": proc.returncode, "stdout": holder.get("out") or "", "stderr": ""})
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0 or re.search(r"wrong password|password is incorrect|Cannot open encrypted", output, re.I):
        raise CatalogError(f"unpacking failed ({result.returncode}): {output.splitlines()[-1] if output else 'no output'}")
    # A wrong password can "succeed" with an empty tree on some extractors.
    if not list_files(dest):
        raise CatalogError("unpacking produced no files - the archive password is probably wrong")


def extract_archive(archive: Path, dest: Path, password: str | None, log, progress: "Progress | None" = None) -> list[Path]:
    """Unpack .zip/.tar/.ova/.7z/.rar, decrypting with `password` when needed."""
    dest.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            encrypted = any(i.flag_bits & 0x1 for i in infos)
            aes = any(i.compress_type == 99 for i in infos)  # WinZip AES marker
            if (encrypted or aes) and not password:
                raise CatalogError("this archive is password protected: paste the unzip password and try again")
            if aes:
                log("this ZIP uses AES encryption; stdlib cannot read it, using 7-Zip")
                _extract_with_7z(archive, dest, password, log, progress)
                return list_files(dest)
            if encrypted and shutil.which("unzip"):
                _extract_with_unzip(zf, archive, dest, password, log, progress)
                return list_files(dest)
            if encrypted:
                log("unzip was not found: using Python's slow built-in decryption (about 2 MB/s). Install unzip or 7-Zip for big images.")
                zf.setpassword(password.encode())
            try:
                _safe_extract_zip(zf, dest, progress)
            except RuntimeError as exc:
                if "password" in str(exc).lower():
                    raise CatalogError("wrong unzip password") from exc
                raise
            return list_files(dest)
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            _safe_extract_tar(tf, dest)
        return list_files(dest)
    # .7z / .rar / anything else: one of the external extractors knows it.
    _extract_with_7z(archive, dest, password, log, progress)
    return list_files(dest)


class Catalog:
    """Images on disk plus the state of each pull, kept in <data>/state.json."""

    def __init__(self, catalog_path: Path, data_dir: Path):
        self.path = Path(catalog_path).resolve()
        self.base = self.path.parent
        self.data = data_dir.resolve()
        self.images_dir = self.data / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data / "images-state.json"
        self.local_file = self.data / "images.local.json"
        self.base_entries: list[dict] = []
        if self.path.exists():
            self.base_entries = load_catalog(self.path)
        self.added: list[dict] = self._load_added()
        self.entries: list[dict] = list(self.base_entries)
        known = {e["id"] for e in self.entries}
        for entry in self.added:
            if entry["id"] in known:
                continue
            self.entries.append(entry)
            known.add(entry["id"])
        try:
            self.state = json.loads(self.state_file.read_text())
        except (OSError, json.JSONDecodeError):
            self.state = {}
        # A pull cannot survive the agent closing: do not leave it saying "pulling" forever.
        for image_id, st in list(self.state.items()):
            if st.get("state") == "pulling":
                self.save_state(
                    image_id,
                    state="error",
                    detail="the agent was closed during this download; press Pull again (the finished part is reused)",
                    error="interrupted",
                )

    # -- queries ------------------------------------------------------------
    def _load_added(self) -> list[dict]:
        """Images added from the page. A broken file must not stop the agent."""
        try:
            data = json.loads(self.local_file.read_text()).get("images", [])
        except (OSError, json.JSONDecodeError):
            return []
        out = []
        for i, entry in enumerate(data):
            try:
                out.append(validate_entry(entry, i))
            except CatalogError:
                continue
        return out

    def add_image(self, entry: dict) -> dict:
        """Remember an image added from the page (persisted in the data folder)."""
        entry = validate_entry(entry)
        with_ids = {e["id"] for e in self.entries}
        if entry["id"] in with_ids:
            raise CatalogError(f'there is already an image with the id "{entry["id"]}"')
        self.added.append(entry)
        tmp = self.local_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"images": self.added}, indent=2))
        tmp.replace(self.local_file)
        self.entries.append(entry)
        return entry

    def remove_image(self, image_id: str) -> int:
        """Delete an image's downloaded files (they are many GB) and forget it. Returns the bytes freed."""
        entry = self.get(image_id)
        if entry is None:
            raise CatalogError(f"no image called {image_id}")
        folder = self.image_dir(image_id)
        freed = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.exists() else 0
        shutil.rmtree(folder, ignore_errors=True)
        self.state.pop(image_id, None)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, sort_keys=True))
        tmp.replace(self.state_file)
        if entry in self.added:  # added from the page: forget it; a catalog-file image stays listed, just not downloaded
            self.added.remove(entry)
            self.entries.remove(entry)
            tmp = self.local_file.with_suffix(".tmp")
            tmp.write_text(json.dumps({"images": self.added}, indent=2))
            tmp.replace(self.local_file)
        return freed

    def get(self, image_id: str) -> dict | None:
        for entry in self.entries:
            if entry["id"] == image_id:
                return entry
        return None

    def image_dir(self, image_id: str) -> Path:
        return self.images_dir / image_id

    def state_of(self, image_id: str) -> dict:
        return self.state.get(image_id, {"state": "missing", "progress": 0, "detail": ""})

    def save_state(self, image_id: str, **fields) -> None:
        cur = dict(self.state_of(image_id))
        cur.update(fields)
        self.state[image_id] = cur
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, sort_keys=True))
        tmp.replace(self.state_file)

    def base_disk(self, image_id: str) -> Path | None:
        st = self.state_of(image_id)
        if st.get("state") != "ready" or not st.get("disk"):
            return None
        p = Path(st["disk"])
        return p if p.exists() else None

    def describe(self, entry: dict) -> dict:
        st = self.state_of(entry["id"])
        source = entry.get("source", {})
        return {
            "id": entry["id"],
            "name": entry["name"],
            "family": entry["family"],
            "osName": entry.get("osName", ""),
            "script": entry["script"],
            "notes": entry.get("notes", ""),
            "sourceKind": source.get("kind"),
            "sourceLabel": source.get("url") or source.get("path"),
            "checksum": bool(source_checksum(source)),
            "checksumAlgo": HASH_LABELS[source_checksum(source)[0]] if source_checksum(source) else "",
            "checksumVerified": st.get("checksumVerified", ""),
            "guest": {k: v for k, v in (entry.get("guest") or {}).items() if k != "password"},
            "state": st.get("state", "missing"),
            "progress": int(st.get("progress", 0)),
            "detail": st.get("detail", ""),
            "disk": st.get("disk"),
            "sizeBytes": st.get("sizeBytes"),
            "pulledAt": st.get("pulledAt"),
            "addedFromPage": any(e["id"] == entry["id"] for e in self.added),
        }

    # -- pulling ------------------------------------------------------------
    def pull(self, image_id: str, log, cancel=None, password: str | None = None) -> Path:
        """Make the base disk ready. Safe to call when it is already ready."""
        entry = self.get(image_id)
        if entry is None:
            raise CatalogError(f"no image called {image_id}")
        existing = self.base_disk(image_id)
        if existing:
            log(f"image {image_id} is already ready: {existing}")
            return existing

        source = entry["source"]
        dest = self.image_dir(image_id)
        dest.mkdir(parents=True, exist_ok=True)
        self.save_state(image_id, state="pulling", progress=0, detail="starting", error="", checksumVerified="")

        try:
            archive: Path
            if source["kind"] == "local":
                src = expand(source["path"], self.base)
                if not src.exists():
                    raise CatalogError(f"local source does not exist: {src}")
                log(f"using local source {src.name}")
                archive = src
                wanted = source_checksum(source)
                if wanted:
                    self.save_state(image_id, state="pulling", progress=0, detail=f"verifying {HASH_LABELS[wanted[0]]}")
                    actual = hash_file(src, wanted[0])
                    if actual != wanted[1]:
                        raise CatalogError(
                            f"checksum mismatch ({HASH_LABELS[wanted[0]]}): expected {wanted[1]}, got {actual}. "
                            "The file is not the one the checksum belongs to - do not boot it."
                        )
                    log(f"checksum verified ({HASH_LABELS[wanted[0]]})")
                    self.save_state(image_id, checksumVerified=HASH_LABELS[wanted[0]])
            else:
                url = source["url"]
                name = source.get("fileName") or Path(urllib.parse.urlparse(url).path).name or f"{image_id}.img"
                archive = dest / Path(name).name
                self._download(url, archive, image_id, source_checksum(source), log, cancel)

            disk = archive
            if archive.name.lower().endswith(ARCHIVE_SUFFIXES):
                extract_dir = dest / "unpacked"
                if not (extract_dir / ".complete").exists():
                    # Unpack beside the final folder and rename when finished, so an interrupted
                    # unpack is never mistaken for a complete one.
                    partial = dest / "unpacked.part"
                    shutil.rmtree(partial, ignore_errors=True)
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    log(f"unpacking {archive.name}")
                    progress = Progress(
                        lambda pct, text: self.save_state(image_id, state="pulling", progress=pct if pct is not None else 100, detail=text),
                        log,
                        "unpacking",
                    )
                    self.save_state(image_id, state="pulling", progress=0, detail="unpacking")
                    extract_archive(archive, partial, password, log, progress)
                    partial.rename(extract_dir)
                    (extract_dir / ".complete").write_text(_now())
                disk = pick_disk(list_files(extract_dir), (entry.get("disk") or {}).get("file"))

            fmt = (entry.get("disk") or {}).get("format") or disk_format(disk)
            if fmt != "qcow2":
                disk = self._convert_to_qcow2(disk, dest, log, image_id)
                fmt = "qcow2"
            size = disk.stat().st_size
            self.save_state(
                image_id,
                state="ready",
                progress=100,
                detail=f"{disk.name} ({size // (1024 * 1024)} MiB, {fmt})",
                disk=str(disk),
                format=fmt,
                sizeBytes=size,
                pulledAt=_now(),
                error="",
            )
            log(f"image {image_id} ready: {disk} ({size // (1024 * 1024)} MiB)")
            return disk
        except Exception as exc:
            self.save_state(image_id, state="error", detail=str(exc), error=str(exc))
            raise

    def _download(self, url: str, target: Path, image_id: str, checksum: tuple[str, str] | None, log, cancel) -> None:
        label = HASH_LABELS[checksum[0]] if checksum else ""
        if target.exists():
            # A finished download from an earlier try (the rename below is atomic): never fetch it twice.
            if checksum and hash_file(target, checksum[0]) != checksum[1]:
                log(f"the file from an earlier try does not match the {label}: downloading it again")
                target.unlink()
            else:
                log(f"already downloaded{f' and the {label} matches' if checksum else ''}: {target.name}")
                if checksum:
                    self.save_state(image_id, checksumVerified=label)
                return
        part = target.with_suffix(target.suffix + ".part")
        log(f"downloading {urllib.parse.urlparse(url).netloc}{urllib.parse.urlparse(url).path}")
        attempts = 0
        while True:
            try:
                self._fetch(url, part, image_id, log, cancel)
                break
            except CatalogError:
                raise
            except (urllib.error.URLError, OSError, http.client.HTTPException, TimeoutError) as exc:
                attempts += 1
                kept = part.stat().st_size if part.exists() else 0
                if attempts > 6:
                    raise CatalogError(
                        f"download failed after {attempts} tries: {exc}. The {gib(kept)} already downloaded is kept: press Pull to continue."
                    ) from exc
                wait = min(2 ** attempts, 30)
                log(f"connection problem ({exc}); retrying in {wait}s and continuing from {gib(kept)} (try {attempts} of 6)")
                self.save_state(image_id, detail=f"connection problem, retrying in {wait}s (kept {gib(kept)})")
                deadline = time.time() + wait
                while time.time() < deadline:
                    if cancel is not None and cancel.is_set():
                        raise CatalogError("cancelled")
                    time.sleep(0.5)
        if checksum:
            self.save_state(image_id, progress=100, detail=f"verifying {label}")
            log(f"verifying {label} of {gib(part.stat().st_size)}")
            actual = hash_file(part, checksum[0])
            if actual != checksum[1]:
                part.unlink(missing_ok=True)
                raise CatalogError(
                    f"checksum mismatch ({label}): expected {checksum[1]}, got {actual}. "
                    "The file is damaged or was replaced - it was deleted, do not boot it."
                )
            log(f"checksum verified ({label})")
            self.save_state(image_id, checksumVerified=label)
        elif str(target.name).lower().endswith(ARCHIVE_SUFFIXES):
            log("no checksum given for this image: the download was NOT verified")
        part.replace(target)

    def _fetch(self, url: str, part: Path, image_id: str, log, cancel) -> None:
        """One HTTP request, continuing a partly downloaded file when the server allows it."""
        start = part.stat().st_size if part.exists() else 0
        headers = {"User-Agent": "rampart-range/1.1"}
        if start:
            headers["Range"] = f"bytes={start}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and start:  # what we hold does not fit the file on the server any more
                part.unlink(missing_ok=True)
                raise OSError("the partial file did not match the server; starting again") from exc
            raise
        with response:
            length = int(response.headers.get("Content-Length") or 0)
            if start and response.status == 206:
                mode, done = "ab", start
                total = start + length if length else 0
                log(f"resuming at {gib(start)}")
            else:
                mode, done = "wb", 0  # no resume support (or a fresh download)
                total = length
            self._check_space(part, total, url)
            began, began_done, last_note = time.time(), done, 0.0
            with part.open(mode) as out:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise CatalogError("cancelled")
                    block = response.read(1 << 20)
                    if not block:
                        break
                    out.write(block)
                    done += len(block)
                    now = time.time()
                    if now - last_note >= 1.0:
                        last_note = now
                        rate = (done - began_done) / max(now - began, 0.001)
                        left = f" · about {_eta((total - done) / rate)} left" if total and rate > 0 else ""
                        size = f"{gib(done)} of {gib(total)}" if total else gib(done)
                        pct = int(done * 100 / total) if total else 0
                        self.save_state(image_id, progress=min(pct, 99), detail=f"downloading {size} · {gib(rate)}/s{left}")
            if total and done < total:
                raise OSError(f"the connection closed early ({gib(done)} of {gib(total)})")
        log(f"downloaded {gib(done)}")

    def _check_space(self, part: Path, total: int, url: str) -> None:
        """Say so before a 40 GB download fails halfway on a full disk."""
        if not total:
            return
        archive = url.lower().split("?")[0].endswith(ARCHIVE_SUFFIXES)
        needed = int(total * (2.3 if archive else 1.3))
        free = shutil.disk_usage(part.parent).free + (part.stat().st_size if part.exists() else 0)
        if free < needed:
            raise CatalogError(
                f"not enough free disk space: this image needs about {gib(needed)} (download, unpacked copy and converted disk) "
                f"and only {gib(free)} is free in {part.parent}. Free some space or use --data to keep images on another drive."
            )

    def _convert_to_qcow2(self, disk: Path, dest: Path, log, image_id: str = "") -> Path:
        qemu_img = shutil.which("qemu-img")
        if not qemu_img:
            raise CatalogError(
                "this image is not qcow2 and qemu-img is not installed. Install QEMU "
                "(macOS: brew install qemu; Debian/Ubuntu: sudo apt install qemu-utils) or convert the disk yourself."
            )
        target = dest / (disk.stem + ".qcow2")
        if target.exists():
            return target
        partial = target.with_suffix(".qcow2.part")
        partial.unlink(missing_ok=True)
        log(f"converting {disk.name} -> {target.name} (one time, can take many minutes for a large image)")
        progress = Progress(
            lambda pct, text: self.save_state(image_id, state="pulling", progress=pct if pct is not None else 0, detail=text),
            log,
            "converting to qcow2",
        )
        self.save_state(image_id, state="pulling", progress=0, detail="converting to qcow2")
        proc = subprocess.Popen(
            [qemu_img, "convert", "-p", "-O", "qcow2", str(disk), str(partial)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        tail = ""
        buffer = ""
        assert proc.stdout is not None
        while True:
            char = proc.stdout.read(1)
            if not char:
                break
            if char in "\r\n":
                found = re.search(r"\(([\d.]+)/100%\)", buffer)
                if found:
                    pct = float(found.group(1))
                    progress.tick(pct, f"{pct:.0f}%")
                elif buffer.strip():
                    tail = buffer.strip()
                buffer = ""
            else:
                buffer += char
        proc.stdout.close()
        proc.wait()
        if proc.returncode != 0:
            partial.unlink(missing_ok=True)
            raise CatalogError(f"qemu-img convert failed: {tail or 'exit code ' + str(proc.returncode)}")
        partial.rename(target)
        return target


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
