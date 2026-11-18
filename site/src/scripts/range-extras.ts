// Practice range extras: VM tabs, snapshots, a score tracker, a round timer, README paste,
// run comparison and shareable setups. range.ts owns the connection and calls into here.
import { parseReadme, type OS } from './readme';

type Kind = 'info' | 'error' | 'ok';

export interface ExtraSession {
  id: string;
  imageId: string;
  imageName: string;
  state: string;
  provider: string | null;
  desktopAvailable?: boolean;
}

export interface ExtraRun {
  id: string;
  imageName: string;
  mode: string;
  state: string;
  startedAt: string;
}

export interface ExtraCtx {
  api<T>(path: string, init?: RequestInit): Promise<T>;
  message(text: string, kind?: Kind): void;
  sessions(): ExtraSession[];
  runs(): ExtraRun[];
  current(): string | null;
  selectSession(id: string): Promise<void>;
}

const $ = <T extends HTMLElement>(id: string): T | null => document.getElementById(id) as T | null;

function h<K extends keyof HTMLElementTagNameMap>(tag: K, cls = '', text = ''): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text) node.textContent = text;
  return node;
}

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private window: the tools still work for this visit */
  }
}

const pad = (n: number) => String(n).padStart(2, '0');
const clock = (t: number) => {
  const d = new Date(t);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

// ---------------------------------------------------------------------------
// Score tracker
// ---------------------------------------------------------------------------
interface ScoreEntry {
  t: number;
  score: number;
  note: string;
}

const scoreKey = (imageId: string) => `cp:range:score:${imageId}`;

/** Pure: how each logged score moved, and which change caused each drop. */
export function describeScores(entries: ScoreEntry[]): { entry: ScoreEntry; delta: number | null }[] {
  return entries.map((entry, i) => ({ entry, delta: i === 0 ? null : entry.score - entries[i - 1].score }));
}

function chart(entries: ScoreEntry[]): SVGSVGElement {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 300 90');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `Score over time: ${entries.map((e) => e.score).join(', ')}`);
  svg.classList.add('rg-score__chart');
  const max = Math.max(100, ...entries.map((e) => e.score));
  const x = (i: number) => (entries.length === 1 ? 150 : 10 + (i * 280) / (entries.length - 1));
  const y = (v: number) => 80 - (v / max) * 70;
  const line = document.createElementNS(ns, 'polyline');
  line.setAttribute('points', entries.map((e, i) => `${x(i)},${y(e.score)}`).join(' '));
  line.setAttribute('fill', 'none');
  line.setAttribute('stroke', 'var(--sl-color-accent)');
  line.setAttribute('stroke-width', '2');
  svg.append(line);
  entries.forEach((e, i) => {
    const drop = i > 0 && e.score < entries[i - 1].score;
    const dot = document.createElementNS(ns, 'circle');
    dot.setAttribute('cx', String(x(i)));
    dot.setAttribute('cy', String(y(e.score)));
    dot.setAttribute('r', '3.5');
    dot.setAttribute('fill', drop ? 'var(--cp-danger)' : 'var(--sl-color-accent)');
    svg.append(dot);
  });
  return svg;
}

// ---------------------------------------------------------------------------
// Round timer (phases from docs/start-here/round-game-plan.md, minutes of a 4 hour round)
// ---------------------------------------------------------------------------
const PHASES = [
  { start: 0, end: 15, title: 'Read the README and snapshot' },
  { start: 15, end: 45, title: 'Forensics questions' },
  { start: 45, end: 60, title: 'Start updates, run the script' },
  { start: 60, end: 150, title: 'Work the checklist' },
  { start: 150, end: 210, title: 'Backdoors and harder items' },
  { start: 210, end: 230, title: 'Final checks' },
  { start: 230, end: 240, title: 'Last minute: stop changing things' },
];

interface TimerState {
  lengthMin: number;
  startedAt: number | null;
  elapsedMs: number;
}

const timerKey = (imageId: string) => `cp:range:timer:${imageId}`;

/** Pure: which phase a given elapsed time falls in, scaled to the round length. */
export function phaseAt(elapsedMin: number, lengthMin: number): { index: number; title: string } {
  const k = lengthMin / 240;
  const index = PHASES.findIndex((p) => elapsedMin >= p.start * k && elapsedMin < p.end * k);
  return index < 0 ? { index: -1, title: 'Time is up' } : { index, title: PHASES[index].title };
}

function hms(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(total / 3600)}:${pad(Math.floor((total % 3600) / 60))}:${pad(total % 60)}`;
}

// ---------------------------------------------------------------------------
// Run comparison
// ---------------------------------------------------------------------------
interface FindingRow {
  status: string;
  section: string;
  text: string;
}

/** Pure: what changed between two lists of findings. */
export function diffFindings(a: FindingRow[], b: FindingRow[]) {
  const key = (f: FindingRow) => `${f.section}\u0000${f.text}`;
  const am = new Map(a.map((f) => [key(f), f]));
  const bm = new Map(b.map((f) => [key(f), f]));
  const gone = a.filter((f) => !bm.has(key(f)));
  const added = b.filter((f) => !am.has(key(f)));
  const changed = b
    .filter((f) => am.has(key(f)) && am.get(key(f))!.status !== f.status)
    .map((f) => ({ from: am.get(key(f))!.status, row: f }));
  return { gone, added, changed };
}

/** Pure: lines that appear in only one of two log files. */
export function diffLines(a: string, b: string) {
  const lines = (t: string) => t.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const as = new Set(lines(a));
  const bs = new Set(lines(b));
  return { removed: [...as].filter((l) => !bs.has(l)), added: [...bs].filter((l) => !as.has(l)) };
}

function countBy(rows: FindingRow[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of rows) out[row.status] = (out[row.status] ?? 0) + 1;
  return out;
}

// ---------------------------------------------------------------------------
export function initExtras(ctx: ExtraCtx) {
  let timerHandle = 0;

  const currentSession = () => ctx.sessions().find((s) => s.id === ctx.current()) ?? null;

  // ---- VM tabs ------------------------------------------------------------
  function renderTabs(): void {
    const host = $('vm-tabs');
    if (!host) return;
    const live = ctx.sessions().filter((s) => s.state === 'running' || s.state === 'booting');
    host.replaceChildren();
    host.hidden = live.length < 2;
    if (live.length < 2) return;
    for (const session of live) {
      const tab = h('button', `rg-tab${session.id === ctx.current() ? ' is-active' : ''}`);
      tab.type = 'button';
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', String(session.id === ctx.current()));
      tab.append(h('span', 'rg-tab__dot'), document.createTextNode(session.imageName));
      tab.addEventListener('click', () => void ctx.selectSession(session.id));
      host.append(tab);
    }
    host.append(h('span', 'cp-hint', `${live.length} VMs running: each one reserves its own memory (4 GB by default).`));
  }

  // ---- snapshots ----------------------------------------------------------
  interface Snapshot {
    name: string;
    size: string;
    date: string;
  }

  async function loadSnapshots(): Promise<void> {
    const list = $('snap-list');
    const note = $('snap-note');
    const save = $<HTMLButtonElement>('snap-save');
    const session = currentSession();
    if (!list || !note) return;
    list.replaceChildren();
    const usable = Boolean(session && session.provider === 'qemu' && session.state === 'running');
    if (save) save.disabled = !usable;
    if (!usable) {
      note.textContent = 'Snapshots need a running VM that was booted with QEMU.';
      return;
    }
    try {
      const data = await ctx.api<{ snapshots: Snapshot[] }>(`/api/sessions/${session!.id}/snapshots`);
      note.textContent = data.snapshots.length
        ? 'Restore puts the VM back to exactly that moment. Apply saves one for you first.'
        : 'No snapshots yet. Save one before a risky change; Run apply also saves one first.';
      for (const snap of data.snapshots) {
        const row = h('li', 'rg-snap');
        row.append(h('strong', '', snap.name), h('span', 'cp-hint', ` ${snap.size} · ${snap.date}`));
        const restore = h('button', 'cp-btn cp-btn--sm', 'Restore');
        restore.type = 'button';
        restore.addEventListener('click', () => void restoreSnapshot(snap.name));
        const del = h('button', 'cp-btn cp-btn--sm cp-btn--ghost', 'Delete');
        del.type = 'button';
        del.addEventListener('click', () => void deleteSnapshot(snap.name));
        const actions = h('span', 'rg-snap__actions');
        actions.append(restore, del);
        row.append(actions);
        list.append(row);
      }
    } catch (error) {
      note.textContent = error instanceof Error ? error.message : String(error);
    }
  }

  async function saveSnapshot(): Promise<void> {
    const session = currentSession();
    const input = $<HTMLInputElement>('snap-name');
    if (!session || !input) return;
    const name = (input.value.trim() || `checkpoint-${clock(Date.now()).replace(':', '')}`).replace(/\s+/g, '-');
    const save = $<HTMLButtonElement>('snap-save');
    if (save) {
      save.disabled = true;
      save.textContent = 'Saving…';
    }
    try {
      await ctx.api(`/api/sessions/${session.id}/snapshots`, { method: 'POST', body: JSON.stringify({ name }) });
      ctx.message(`Snapshot "${name}" saved.`, 'ok');
      input.value = '';
    } catch (error) {
      ctx.message(error instanceof Error ? error.message : String(error), 'error');
    } finally {
      if (save) save.textContent = 'Save snapshot';
      await loadSnapshots();
    }
  }

  async function restoreSnapshot(name: string): Promise<void> {
    const session = currentSession();
    if (!session) return;
    if (!window.confirm(`Go back to "${name}"? The VM returns to exactly that moment; anything done since is undone.`)) return;
    try {
      await ctx.api(`/api/sessions/${session.id}/snapshots/${encodeURIComponent(name)}/restore`, { method: 'POST', body: '{}' });
      ctx.message(`Back at "${name}". The desktop may take a second to catch up.`, 'ok');
    } catch (error) {
      ctx.message(error instanceof Error ? error.message : String(error), 'error');
    }
  }

  async function deleteSnapshot(name: string): Promise<void> {
    const session = currentSession();
    if (!session) return;
    try {
      await ctx.api(`/api/sessions/${session.id}/snapshots/${encodeURIComponent(name)}`, { method: 'DELETE' });
    } catch (error) {
      ctx.message(error instanceof Error ? error.message : String(error), 'error');
    }
    await loadSnapshots();
  }

  // ---- score tracker ------------------------------------------------------
  function renderScores(): void {
    const session = currentSession();
    const host = $('score-body');
    if (!host) return;
    host.replaceChildren();
    if (!session) return;
    const entries = read<ScoreEntry[]>(scoreKey(session.imageId), []);
    if (entries.length === 0) {
      host.append(h('p', 'cp-hint', 'After each change, read the Scoring Report and log the score here. A drop shows which change caused it.'));
      return;
    }
    const best = Math.max(...entries.map((e) => e.score));
    host.append(h('p', 'rg-score__sum', `Now ${entries[entries.length - 1].score} · best ${best} · ${entries.length} logged`));
    host.append(chart(entries));
    const list = h('ol', 'rg-score__list');
    for (const { entry, delta } of describeScores(entries).reverse()) {
      const row = h('li', delta !== null && delta < 0 ? 'is-drop' : '');
      const move = delta === null ? 'start' : delta > 0 ? `+${delta}` : delta === 0 ? '±0' : `${delta}`;
      row.append(h('strong', '', String(entry.score)), h('span', 'rg-score__move', ` ${move} `), h('span', 'cp-hint', `${clock(entry.t)}${entry.note ? ' · ' + entry.note : ''}`));
      if (delta !== null && delta < 0) {
        row.append(h('p', 'rg-score__warn', `Score dropped${entry.note ? ` after "${entry.note}"` : ''}. Undo that change (or restore a snapshot) and check the report again.`));
      }
      list.append(row);
    }
    host.append(list);
  }

  function addScore(): void {
    const session = currentSession();
    const scoreInput = $<HTMLInputElement>('score-value');
    const noteInput = $<HTMLInputElement>('score-note');
    if (!session || !scoreInput || !noteInput) return;
    const value = Number(scoreInput.value);
    if (scoreInput.value.trim() === '' || !Number.isFinite(value) || value < 0 || value > 1000) {
      ctx.message('Type the score from the Scoring Report (a number from 0 to 1000).', 'error');
      return;
    }
    const entries = read<ScoreEntry[]>(scoreKey(session.imageId), []);
    entries.push({ t: Date.now(), score: value, note: noteInput.value.trim() });
    write(scoreKey(session.imageId), entries);
    scoreInput.value = '';
    noteInput.value = '';
    renderScores();
  }

  // ---- round timer --------------------------------------------------------
  function timerState(imageId: string): TimerState {
    return read<TimerState>(timerKey(imageId), { lengthMin: 240, startedAt: null, elapsedMs: 0 });
  }

  function renderTimer(): void {
    const session = currentSession();
    const display = $('timer-display');
    const phase = $('timer-phase');
    const toggle = $<HTMLButtonElement>('timer-toggle');
    const length = $<HTMLSelectElement>('timer-length');
    if (!session || !display || !phase || !toggle || !length) return;
    const t = timerState(session.imageId);
    length.value = String(t.lengthMin);
    const elapsed = t.elapsedMs + (t.startedAt ? Date.now() - t.startedAt : 0);
    const left = t.lengthMin * 60_000 - elapsed;
    display.textContent = hms(left);
    display.dataset.low = String(left < 10 * 60_000);
    toggle.textContent = t.startedAt ? 'Pause' : elapsed > 0 ? 'Resume' : 'Start';
    const now = phaseAt(elapsed / 60_000, t.lengthMin);
    phase.textContent = elapsed === 0 ? 'Not started' : left <= 0 ? 'Time is up' : `Now: ${now.title}`;
  }

  function toggleTimer(): void {
    const session = currentSession();
    if (!session) return;
    const t = timerState(session.imageId);
    if (t.startedAt) {
      t.elapsedMs += Date.now() - t.startedAt;
      t.startedAt = null;
    } else {
      t.startedAt = Date.now();
    }
    write(timerKey(session.imageId), t);
    renderTimer();
  }

  function resetTimer(): void {
    const session = currentSession();
    if (!session) return;
    const t = timerState(session.imageId);
    write(timerKey(session.imageId), { lengthMin: t.lengthMin, startedAt: null, elapsedMs: 0 });
    renderTimer();
  }

  // ---- README paste -------------------------------------------------------
  const README_KEY = 'cp:range:readme';

  function readmeFields() {
    return {
      admins: $<HTMLInputElement>('cfg-admins'),
      users: $<HTMLInputElement>('cfg-users'),
      critical: $<HTMLInputElement>('cfg-critical'),
    };
  }

  function saveReadme(): void {
    const f = readmeFields();
    write(README_KEY, { admins: f.admins?.value ?? '', users: f.users?.value ?? '', critical: f.critical?.value ?? '' });
  }

  function fillFromReadme(): void {
    const text = $<HTMLTextAreaElement>('cfg-paste')?.value ?? '';
    const os = ($<HTMLSelectElement>('cfg-paste-os')?.value ?? 'linux') as OS;
    if (!text.trim()) {
      ctx.message('Paste the README text first.', 'error');
      return;
    }
    const found = parseReadme(text, os);
    const f = readmeFields();
    if (f.admins) f.admins.value = found.admins.join(' ');
    if (f.users) f.users.value = found.users.join(' ');
    if (f.critical) f.critical.value = [...found.services].join(' ');
    saveReadme();
    const who = found.me ? ` You are ${found.me}.` : '';
    ctx.message(`Filled in ${found.admins.length} admin(s), ${found.users.length} user(s) and ${found.services.size} critical service(s).${who} Check them against the README.`, found.admins.length + found.users.length ? 'ok' : 'error');
  }

  // ---- compare runs -------------------------------------------------------
  function renderCompareChoices(): void {
    const a = $<HTMLSelectElement>('cmp-a');
    const b = $<HTMLSelectElement>('cmp-b');
    const card = $('range-compare');
    if (!a || !b || !card) return;
    // finished runs with findings: the agent's terminal states
    const runs = ctx.runs().filter((r) => r.state === 'done' || r.state === 'done-with-errors');
    card.hidden = runs.length < 2;
    const keepA = a.value;
    const keepB = b.value;
    for (const select of [a, b]) {
      select.replaceChildren();
      for (const run of runs) {
        const option = h('option', '', `${run.imageName} · ${run.mode.toUpperCase()} · ${run.startedAt.replace('T', ' ').replace('Z', '')}`);
        option.value = run.id;
        select.append(option);
      }
    }
    // runs are newest first: compare the previous run (A) with the latest (B) by default
    a.value = runs.some((r) => r.id === keepA) ? keepA : (runs[1]?.id ?? '');
    b.value = runs.some((r) => r.id === keepB) ? keepB : (runs[0]?.id ?? '');
  }

  async function loadRunData(id: string): Promise<{ findings: FindingRow[]; logs: Record<string, string> }> {
    const [findings, logs] = await Promise.all([
      ctx.api<{ results?: FindingRow[] }>(`/api/runs/${id}/findings`).catch(() => ({ results: [] as FindingRow[] })),
      ctx.api<{ files?: Record<string, string> }>(`/api/runs/${id}/logs`).catch(() => ({ files: {} as Record<string, string> })),
    ]);
    return { findings: findings.results ?? [], logs: logs.files ?? {} };
  }

  async function compareRuns(): Promise<void> {
    const out = $('cmp-out');
    const idA = $<HTMLSelectElement>('cmp-a')?.value;
    const idB = $<HTMLSelectElement>('cmp-b')?.value;
    if (!out || !idA || !idB) return;
    if (idA === idB) {
      ctx.message('Pick two different runs to compare.', 'error');
      return;
    }
    out.replaceChildren(h('p', 'cp-hint', 'Comparing…'));
    const [a, b] = await Promise.all([loadRunData(idA), loadRunData(idB)]);
    const d = diffFindings(a.findings, b.findings);
    out.replaceChildren();

    const counts = h('table', 'rg-table rg-cmp__counts');
    const head = h('tr');
    for (const label of ['', 'Run A', 'Run B']) head.append(h('th', '', label));
    counts.append(head);
    const ca = countBy(a.findings);
    const cb = countBy(b.findings);
    for (const status of [...new Set([...Object.keys(ca), ...Object.keys(cb)])].sort()) {
      const row = h('tr');
      row.append(h('td', '', status), h('td', '', String(ca[status] ?? 0)), h('td', '', String(cb[status] ?? 0)));
      counts.append(row);
    }
    out.append(counts);

    const group = (title: string, rows: string[], tone: string) => {
      const box = h('details', `rg-cmp__group ${tone}`);
      box.open = rows.length > 0 && rows.length <= 12;
      box.append(h('summary', '', `${title} (${rows.length})`));
      const list = h('ul');
      for (const line of rows.slice(0, 200)) list.append(h('li', '', line));
      if (rows.length === 0) list.append(h('li', 'cp-hint', 'nothing'));
      box.append(list);
      out.append(box);
    };
    group('Only in run A (gone in B)', d.gone.map((f) => `${f.status} · ${f.section}: ${f.text}`), 'is-good');
    group('Only in run B (new)', d.added.map((f) => `${f.status} · ${f.section}: ${f.text}`), 'is-new');
    group('Changed status', d.changed.map((c) => `${c.from} → ${c.row.status} · ${c.row.section}: ${c.row.text}`), 'is-changed');

    const names = [...new Set([...Object.keys(a.logs), ...Object.keys(b.logs)])].sort();
    const logs = h('div', 'rg-cmp__logs');
    logs.append(h('h4', '', 'What changed in each log'));
    let any = false;
    for (const name of names) {
      const diff = diffLines(a.logs[name] ?? '', b.logs[name] ?? '');
      if (!diff.added.length && !diff.removed.length) continue;
      any = true;
      const box = h('details', 'rg-cmp__group');
      box.append(h('summary', '', `${name}: ${diff.removed.length} gone, ${diff.added.length} new`));
      const list = h('ul');
      for (const line of diff.removed.slice(0, 60)) list.append(h('li', 'is-removed', `− ${line}`));
      for (const line of diff.added.slice(0, 60)) list.append(h('li', 'is-added', `+ ${line}`));
      box.append(list);
      logs.append(box);
    }
    if (!any) logs.append(h('p', 'cp-hint', 'The log files are identical.'));
    out.append(logs);
  }

  // ---- share a setup ------------------------------------------------------
  interface Setup {
    rampartSetup: 1;
    image: { url: string; name: string; family: string; user: string; keyFile: string; checksum: string };
    readme: { admins: string; users: string; critical: string };
  }

  const val = (id: string) => $<HTMLInputElement>(id)?.value.trim() ?? '';

  function exportSetup(): void {
    const setup: Setup = {
      rampartSetup: 1,
      image: {
        url: val('add-url'),
        name: val('add-name'),
        family: $<HTMLSelectElement>('add-family')?.value ?? 'linux',
        user: val('add-user'),
        keyFile: val('add-key'),
        checksum: val('add-sha'),
      },
      readme: { admins: val('cfg-admins'), users: val('cfg-users'), critical: val('cfg-critical') },
    };
    if (!setup.image.url) {
      ctx.message('Fill in the download link first: that is the part worth sharing.', 'error');
      return;
    }
    const blob = new Blob([JSON.stringify(setup, null, 2)], { type: 'application/json' });
    const link = h('a');
    link.href = URL.createObjectURL(blob);
    link.download = `rampart-setup-${(setup.image.name || 'image').toLowerCase().replace(/[^a-z0-9]+/g, '-')}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    ctx.message('Saved. It holds the link, checksum and README answers, never the unzip password: tell your teammate that separately.', 'ok');
  }

  async function importSetup(file: File): Promise<void> {
    try {
      const data = JSON.parse(await file.text()) as Partial<Setup>;
      if (data.rampartSetup !== 1 || !data.image || typeof data.image.url !== 'string') throw new Error('not a Rampart setup file');
      const set = (id: string, value: string | undefined) => {
        const input = $<HTMLInputElement | HTMLSelectElement>(id);
        if (input && typeof value === 'string') {
          input.value = value;
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }
      };
      set('add-url', data.image.url);
      set('add-name', data.image.name);
      set('add-family', data.image.family);
      set('add-user', data.image.user);
      set('add-key', data.image.keyFile);
      set('add-sha', data.image.checksum);
      set('cfg-admins', data.readme?.admins);
      set('cfg-users', data.readme?.users);
      set('cfg-critical', data.readme?.critical);
      saveReadme();
      ctx.message('Setup loaded. Type the unzip password (they send it separately) and press Download & boot.', 'ok');
    } catch (error) {
      ctx.message(`Could not read that file: ${error instanceof Error ? error.message : String(error)}`, 'error');
    }
  }

  // ---- wiring -------------------------------------------------------------
  const wired = { done: false };
  function wire(): void {
    if (wired.done) return;
    wired.done = true;
    $('snap-save')?.addEventListener('click', () => void saveSnapshot());
    $('snap-refresh')?.addEventListener('click', () => void loadSnapshots());
    $('score-add')?.addEventListener('click', addScore);
    $('score-clear')?.addEventListener('click', () => {
      const session = currentSession();
      if (session && window.confirm('Clear the logged scores for this image?')) {
        write(scoreKey(session.imageId), []);
        renderScores();
      }
    });
    $('timer-toggle')?.addEventListener('click', toggleTimer);
    $('timer-reset')?.addEventListener('click', resetTimer);
    $('timer-length')?.addEventListener('change', (event) => {
      const session = currentSession();
      if (!session) return;
      const t = timerState(session.imageId);
      t.lengthMin = Number((event.target as HTMLSelectElement).value) || 240;
      write(timerKey(session.imageId), t);
      renderTimer();
    });
    $('cfg-paste-btn')?.addEventListener('click', fillFromReadme);
    for (const id of ['cfg-admins', 'cfg-users', 'cfg-critical']) $(id)?.addEventListener('input', saveReadme);
    $('cmp-go')?.addEventListener('click', () => void compareRuns());
    $('setup-export')?.addEventListener('click', exportSetup);
    $('setup-import')?.addEventListener('change', (event) => {
      const input = event.target as HTMLInputElement;
      const file = input.files?.[0];
      if (file) void importSetup(file);
      input.value = '';
    });
    // restore the README answers typed earlier
    const saved = read<{ admins: string; users: string; critical: string } | null>(README_KEY, null);
    const f = readmeFields();
    if (saved) {
      if (f.admins) f.admins.value = saved.admins;
      if (f.users) f.users.value = saved.users;
      if (f.critical) f.critical.value = saved.critical;
    }
  }

  return {
    init: wire,
    /** The selected VM changed (or its state did): refresh every panel for it. */
    onSessionSelected(): void {
      wire();
      renderTabs();
      void loadSnapshots();
      renderScores();
      renderTimer();
      window.clearInterval(timerHandle);
      timerHandle = window.setInterval(renderTimer, 1000);
    },
    onSessionsChanged(): void {
      renderTabs();
    },
    onRunsChanged(): void {
      renderCompareChoices();
    },
    stop(): void {
      window.clearInterval(timerHandle);
    },
  };
}
