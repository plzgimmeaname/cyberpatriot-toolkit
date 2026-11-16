// Practice range page: talks to the local Rampart Range agent (range/agent.py).
// Everything here is browser-only. The token is kept in sessionStorage: it is
// never sent to the website's own server, and it disappears when the tab closes.

interface RangeImage {
  id: string;
  name: string;
  family: string;
  osName: string;
  script: string;
  notes: string;
  sourceKind: string;
  sourceLabel: string | null;
  checksum: boolean;
  guest: Record<string, unknown>;
  state: string;
  progress: number;
  detail: string;
  disk: string | null;
  sizeBytes: number | null;
  pulledAt: string | null;
}

interface RunSummary {
  [status: string]: number;
}

interface RangeRun {
  id: string;
  imageId: string;
  imageName: string;
  family: string;
  mode: string;
  state: string;
  startedAt: string;
  finishedAt: string | null;
  error: string | null;
  summary: RunSummary | null;
  provider: string | null;
  sessionId?: string | null;
  logBytes?: number;
}

interface DesktopInfo {
  host: string;
  port: number;
  password: string;
}

interface RangeSession {
  id: string;
  imageId: string;
  imageName: string;
  state: string;
  startedAt: string;
  stoppedAt: string | null;
  detail: string;
  provider: string | null;
  host: string | null;
  port: number | null;
  consoleAvailable: boolean;
  canRun: boolean;
  screenAvailable: boolean;
  desktopAvailable?: boolean;
  desktopOnly?: boolean;
}

interface Finding {
  status: string;
  section: string;
  text: string;
}

interface Findings {
  tool?: string;
  legacy?: boolean;
  results?: Finding[];
}

const TOKEN_KEY = 'cp:range:token';
const URL_KEY = 'cp:range:url';
const DEFAULT_URL = 'http://127.0.0.1:8787';
const TERMINAL = new Set(['done', 'failed', 'interrupted', 'done-with-errors']);

const CATEGORY_LABELS: Record<string, string> = {
  '00-index.txt': 'Index (what each file holds)',
  '01-readme.txt': 'What the README said',
  '02-users.txt': 'Users, groups, sudo',
  '03-apps-installed.txt': 'Apps installed / downloaded',
  '04-apps-removed.txt': 'Apps removed',
  '05-files-found.txt': 'Files found',
  '06-files-deleted.txt': 'Files deleted',
  '07-open-ports.txt': 'Open ports',
  '08-processes.txt': 'Processes',
  '09-services.txt': 'Services',
  '10-persistence.txt': 'Persistence (cron, units, keys)',
  '11-connections.txt': 'Connections',
};

const state = {
  url: DEFAULT_URL,
  token: '',
  connected: false,
  images: [] as RangeImage[],
  runs: [] as RangeRun[],
  selected: null as string | null,
  offset: 0,
  timer: 0,
  logFiles: {} as Record<string, string>,
  findings: null as Findings | null,
  sessions: [] as RangeSession[],
  session: null as string | null,
  consoleOffset: 0,
  sessionTimer: 0,
  screenTimer: 0,
  screenUrl: '',
  rfb: null as null | { disconnect(): void; sendCtrlAltDel(): void; scaleViewport: boolean },
  rfbSession: '',
};

function byId<T extends HTMLElement>(id: string): T | null {
  return document.getElementById(id) as T | null;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function message(text: string, kind: 'info' | 'error' | 'ok' = 'info'): void {
  const box = byId<HTMLDivElement>('range-msg');
  if (!box) return;
  box.hidden = !text;
  box.textContent = text;
  box.dataset.kind = kind;
}

function stored(key: string, storage: Storage): string {
  try {
    return storage.getItem(key) ?? '';
  } catch {
    return '';
  }
}

function store(key: string, value: string, storage: Storage): void {
  try {
    if (value) storage.setItem(key, value);
    else storage.removeItem(key);
  } catch {
    /* private mode: the page still works for this visit */
  }
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${state.token}`);
  if (init.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${state.url.replace(/\/$/, '')}${path}`, { ...init, headers });
  const text = await response.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(`the agent answered with something that is not JSON: ${text.slice(0, 120)}`);
  }
  if (!response.ok) {
    const problem = data as { error?: string } | null;
    throw new Error(problem?.error || `request failed (${response.status})`);
  }
  return data as T;
}

function statusPill(stateName: string): HTMLSpanElement {
  const pill = el('span', 'cp-pill rg-pill', stateName);
  const map: Record<string, string> = {
    ready: 'cp-pill--success',
    done: 'cp-pill--success',
    missing: 'cp-pill--warn',
    pulling: 'cp-pill--warn',
    queue: 'cp-pill--warn',
    queued: 'cp-pill--warn',
    preparing: 'cp-pill--warn',
    running: 'cp-pill--warn',
    stopping: 'cp-pill--warn',
    error: 'cp-pill--danger',
    failed: 'cp-pill--danger',
    interrupted: 'cp-pill--danger',
  };
  pill.classList.add(map[stateName] ?? 'cp-pill--warn');
  return pill;
}

function summaryText(run: RangeRun): string {
  const summary = run.summary;
  if (!summary) return run.error ? `error: ${run.error}` : 'no findings yet';
  const parts = ['OK', 'CHANGED', 'WOULD', 'REVIEW', 'FAILED']
    .filter((k) => summary[k] !== undefined)
    .map((k) => `${k} ${summary[k]}`);
  return parts.join(' · ');
}

function readmeConfig(): Record<string, string> {
  const admins = byId<HTMLInputElement>('cfg-admins')?.value ?? '';
  const users = byId<HTMLInputElement>('cfg-users')?.value ?? '';
  const critical = byId<HTMLInputElement>('cfg-critical')?.value ?? '';
  return { admins, users, critical };
}

function renderImages(): void {
  const host = byId<HTMLDivElement>('range-images');
  if (!host) return;
  host.replaceChildren();
  if (state.images.length === 0) {
    host.append(el('p', 'cp-hint', 'The catalog is empty. Add an image to range/images.json and restart the agent.'));
    return;
  }
  for (const image of state.images) {
    const card = el('article', 'rg-image');
    const head = el('div', 'rg-image__head');
    const title = el('div');
    title.append(el('h3', 'rg-image__title', image.name));
    title.append(el('p', 'rg-image__os', `${image.osName || image.family} · ${image.sourceKind} source${image.checksum ? ' · checksum verified' : ''}`));
    head.append(title, statusPill(image.state));
    card.append(head);

    if (image.notes) card.append(el('p', 'rg-image__notes', image.notes));
    if (image.detail) card.append(el('p', 'cp-hint', image.detail));
    if (image.state === 'pulling' && image.progress > 0) {
      const bar = el('div', 'cp-bar rg-bar');
      const fill = el('span', 'cp-bar__fill');
      fill.style.width = `${image.progress}%`;
      bar.append(fill);
      card.append(bar);
    }

    const actions = el('div', 'rg-actions');
    const pull = el('button', 'cp-btn cp-btn--sm', image.state === 'ready' ? 'Pull again' : 'Pull image');
    pull.type = 'button';
    pull.dataset.action = 'pull';
    pull.dataset.image = image.id;
    pull.disabled = image.state === 'pulling';
    actions.append(pull);

    const live = state.sessions.find((sess) => sess.imageId === image.id && (sess.state === 'running' || sess.state === 'booting'));
    const boot = el('button', 'cp-btn cp-btn--sm', live ? 'Booted' : 'Boot');
    boot.type = 'button';
    boot.dataset.action = 'boot';
    boot.dataset.image = image.id;
    boot.disabled = image.state !== 'ready' || Boolean(live);
    actions.append(boot);

    const desk = el('button', 'cp-btn cp-btn--sm', 'Boot desktop only');
    desk.type = 'button';
    desk.dataset.action = 'boot-desktop';
    desk.dataset.image = image.id;
    desk.title = 'Boot without waiting for SSH/WinRM: for stock images. You use the machine in the browser.';
    desk.disabled = image.state !== 'ready' || Boolean(live);
    actions.append(desk);

    for (const mode of ['audit', 'apply'] as const) {
      const btn = el('button', `cp-btn cp-btn--sm${mode === 'audit' ? ' cp-btn--primary' : ''}`, mode === 'audit' ? 'Run audit' : 'Run apply');
      btn.type = 'button';
      btn.dataset.action = 'run';
      btn.dataset.image = image.id;
      btn.dataset.mode = mode;
      btn.disabled = image.state !== 'ready';
      actions.append(btn);
    }
    card.append(actions);
    host.append(card);
  }
}

function renderRuns(): void {
  const host = byId<HTMLTableSectionElement>('range-runs');
  if (!host) return;
  host.replaceChildren();
  if (state.runs.length === 0) {
    const row = el('tr');
    const cell = el('td', 'cp-hint', 'No runs yet. Pull an image, then run an audit.');
    cell.colSpan = 5;
    row.append(cell);
    host.append(row);
    return;
  }
  for (const run of state.runs) {
    const row = el('tr', 'rg-run');
    row.dataset.run = run.id;
    row.tabIndex = 0;
    const image = el('td');
    image.append(el('strong', '', run.imageName));
    image.append(el('span', 'rg-run__mode', run.mode.toUpperCase()));
    if (run.sessionId) image.append(el('span', 'rg-run__mode', 'on the booted VM'));
    row.append(image);
    const when = el('td', 'rg-muted', run.startedAt.replace('T', ' ').replace('Z', ''));
    row.append(when);
    const st = el('td');
    st.append(statusPill(run.state));
    row.append(st);
    row.append(el('td', 'rg-muted', summaryText(run)));
    const actions = el('td', 'rg-run__actions');
    const open = el('button', 'cp-btn cp-btn--sm', 'Open');
    open.type = 'button';
    open.dataset.action = 'open';
    open.dataset.run = run.id;
    actions.append(open);
    row.append(actions);
    host.append(row);
  }
}

function renderDetailHeader(run: RangeRun): void {
  const title = byId<HTMLHeadingElement>('detail-title');
  if (title) title.textContent = `${run.imageName} · ${run.mode.toUpperCase()}`;
  const meta = byId<HTMLDivElement>('detail-meta');
  if (meta) {
    meta.replaceChildren(statusPill(run.state));
    meta.append(el('span', 'rg-muted', ` ${run.startedAt.replace('T', ' ').replace('Z', '')} · run ${run.id}${run.provider ? ` · ${run.provider}` : ''}`));
    if (run.error) meta.append(el('p', 'rg-error', run.error));
  }
  const stop = byId<HTMLButtonElement>('detail-stop');
  if (stop) stop.hidden = TERMINAL.has(run.state);
  const del = byId<HTMLButtonElement>('detail-delete');
  if (del) del.hidden = !TERMINAL.has(run.state);
}

function renderFindings(): void {
  const host = byId<HTMLDivElement>('detail-findings');
  if (!host) return;
  host.replaceChildren();
  const data = state.findings;
  if (!data || !data.results || data.results.length === 0) {
    host.append(el('p', 'cp-hint', 'No findings yet. They appear when the run finishes.'));
    return;
  }
  if (data.legacy) {
    host.append(el('p', 'cp-hint', 'This image ran an older script: only the text to-do list came back. Update scripts/linux/harden.sh on the image for the per-kind logs.'));
  }
  const counts = new Map<string, number>();
  for (const item of data.results) counts.set(item.status, (counts.get(item.status) ?? 0) + 1);
  const bar = el('div', 'rg-counts');
  for (const status of ['OK', 'CHANGED', 'WOULD', 'REVIEW', 'FAILED']) {
    if (!counts.has(status)) continue;
    const chip = el('span', 'rg-count');
    chip.append(statusPill(status), el('strong', '', ` ${counts.get(status)}`));
    bar.append(chip);
  }
  host.append(bar);

  const table = el('table', 'rg-table');
  const thead = el('thead');
  const headRow = el('tr');
  for (const label of ['Status', 'Section', 'What the script found']) headRow.append(el('th', '', label));
  thead.append(headRow);
  const tbody = el('tbody');
  for (const item of data.results) {
    const row = el('tr');
    const st = el('td');
    st.append(statusPill(item.status));
    row.append(st, el('td', 'rg-muted', item.section), el('td', '', item.text));
    tbody.append(row);
  }
  table.append(thead, tbody);
  host.append(table);
}

function logCategoryName(file: string): string {
  return CATEGORY_LABELS[file] ?? file;
}

function renderCategories(): void {
  const select = byId<HTMLSelectElement>('detail-categories');
  const pre = byId<HTMLPreElement>('detail-logfile');
  if (!select || !pre) return;
  const files = Object.keys(state.logFiles).sort();
  select.replaceChildren();
  if (files.length === 0) {
    select.append(el('option', '', 'No per-kind logs collected yet'));
    select.disabled = true;
    pre.textContent = 'Runs collect /root/cyberpatriot/logs-*/ (Linux) or C:\\harden-toolkit\\logs-* (Windows): one file per kind of finding.';
    return;
  }
  select.disabled = false;
  for (const file of files) {
    const option = el('option', '', logCategoryName(file));
    option.value = file;
    select.append(option);
  }
  const first = files.find((f) => f.startsWith('00-')) ?? files[0];
  select.value = first;
  pre.textContent = state.logFiles[first] ?? '';
}

function renderLog(): void {
  const pre = byId<HTMLPreElement>('detail-log');
  if (!pre) return;
  if (!pre.dataset.ready) {
    pre.textContent = '';
    pre.dataset.ready = '1';
  }
}

async function loadRun(id: string): Promise<void> {
  state.selected = id;
  state.offset = 0;
  state.logFiles = {};
  state.findings = null;
  window.clearTimeout(state.timer);
  const pre = byId<HTMLPreElement>('detail-log');
  if (pre) {
    pre.textContent = '';
    delete pre.dataset.ready;
  }
  renderFindings();
  renderCategories();
  const detail = byId<HTMLElement>('range-detail');
  if (detail) detail.hidden = false;
  await pollRun();
  detail?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function pollRun(): Promise<void> {
  const id = state.selected;
  if (!id) return;
  try {
    const run = await api<RangeRun>(`/api/runs/${id}`);
    renderDetailHeader(run);
    renderLog();
    const tail = await api<{ offset: number; size: number; text: string }>(`/api/runs/${id}/log?offset=${state.offset}`);
    state.offset = tail.offset;
    const pre = byId<HTMLPreElement>('detail-log');
    if (pre && tail.text) {
      pre.textContent = (pre.textContent ?? '') + tail.text;
      pre.scrollTop = pre.scrollHeight;
    }
    if (TERMINAL.has(run.state)) {
      await loadRunArtifacts(id);
      await refreshRuns();
      return;
    }
    state.timer = window.setTimeout(() => void pollRun(), 1500);
  } catch (error) {
    message(error instanceof Error ? error.message : String(error), 'error');
  }
}

async function loadRunArtifacts(id: string): Promise<void> {
  try {
    state.findings = await api<Findings>(`/api/runs/${id}/findings`);
  } catch {
    state.findings = null;
  }
  try {
    const logs = await api<{ files: Record<string, string> }>(`/api/runs/${id}/logs`);
    state.logFiles = logs.files;
  } catch {
    state.logFiles = {};
  }
  renderFindings();
  renderCategories();
}

async function refreshImages(): Promise<void> {
  const data = await api<{ images: RangeImage[] }>('/api/images');
  state.images = data.images;
  renderImages();
}

async function refreshRuns(): Promise<void> {
  const data = await api<{ runs: RangeRun[] }>('/api/runs');
  state.runs = data.runs;
  renderRuns();
  if (state.selected) {
    const current = state.runs.find((r) => r.id === state.selected);
    if (current) renderDetailHeader(current);
  }
}

async function connect(): Promise<void> {
  const urlInput = byId<HTMLInputElement>('range-url');
  const tokenInput = byId<HTMLInputElement>('range-token');
  state.url = (urlInput?.value || DEFAULT_URL).trim().replace(/\/$/, '');
  state.token = (tokenInput?.value || '').trim();
  if (!state.token) {
    message('Paste the token the agent printed (it is also in ~/.rampart-range/token).', 'error');
    return;
  }
  message('Connecting to the agent...');
  const status = byId<HTMLSpanElement>('range-status');
  try {
    const health = await api<{ ok: boolean; version: string }>('/api/health');
    state.connected = health.ok;
    store(URL_KEY, state.url, localStorage);
    store(TOKEN_KEY, state.token, sessionStorage);
    if (status) {
      status.textContent = `Connected · agent ${health.version}`;
      status.dataset.state = 'ok';
    }
    const live = byId<HTMLElement>('range-live');
    if (live) live.hidden = false;
    const setup = byId<HTMLElement>('range-setup');
    if (setup) setup.hidden = true;
    message('');
    await Promise.all([refreshImages(), refreshRuns(), refreshSessions()]);
  } catch (error) {
    state.connected = false;
    if (status) {
      status.textContent = 'Not connected';
      status.dataset.state = 'error';
    }
    message(
      `${error instanceof Error ? error.message : String(error)} — is range/agent.py running? Check the address and token.`,
      'error',
    );
  }
}

async function pullImage(id: string): Promise<void> {
  try {
    message('Started pulling the image. Progress appears on its card; downloads can take a while.', 'info');
    await api(`/api/images/${id}/pull`, { method: 'POST', body: '{}' });
    await refreshImages();
    window.setTimeout(() => void refreshImages(), 3000);
  } catch (error) {
    message(error instanceof Error ? error.message : String(error), 'error');
  }
}

async function startRun(id: string, mode: 'audit' | 'apply', sessionId?: string): Promise<void> {
  if (mode === 'apply' && !window.confirm('Apply mode CHANGES the practice VM (it never touches the base image). Run Apply?')) return;
  try {
    const live = sessionId ?? state.sessions.find((sess) => sess.imageId === id && sess.state === 'running')?.id;
    const body = JSON.stringify({ imageId: id, mode, config: readmeConfig(), confirmApply: mode === 'apply', ...(live ? { sessionId: live } : {}) });
    const created = await api<{ id: string }>('/api/runs', { method: 'POST', body });
    message(`Run ${created.id} queued.`, 'ok');
    await refreshRuns();
    await loadRun(created.id);
  } catch (error) {
    message(error instanceof Error ? error.message : String(error), 'error');
  }
}

async function stopRun(): Promise<void> {
  if (!state.selected) return;
  try {
    await api(`/api/runs/${state.selected}/stop`, { method: 'POST', body: '{}' });
    message('Stopping the run...', 'info');
    await pollRun();
  } catch (error) {
    message(error instanceof Error ? error.message : String(error), 'error');
  }
}

async function deleteRun(): Promise<void> {
  if (!state.selected) return;
  if (!window.confirm('Delete this run and its collected reports from the agent?')) return;
  const id = state.selected;
  try {
    await api(`/api/runs/${id}`, { method: 'DELETE' });
    state.selected = null;
    const detail = byId<HTMLElement>('range-detail');
    if (detail) detail.hidden = true;
    await refreshRuns();
    message('Run deleted.', 'ok');
  } catch (error) {
    message(error instanceof Error ? error.message : String(error), 'error');
  }
}

function downloadFindings(): void {
  if (!state.selected || !state.findings) return;
  const blob = new Blob([JSON.stringify(state.findings, null, 2)], { type: 'application/json' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `findings-${state.selected}.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}


async function refreshSessions(): Promise<void> {
  const data = await api<{ sessions: RangeSession[] }>('/api/sessions');
  state.sessions = data.sessions;
  renderSessions();
  renderImages();
  if (state.session) {
    const current = state.sessions.find((sess) => sess.id === state.session);
    const desktop = byId<HTMLElement>('session-desktop-wrap');
    if (current?.desktopAvailable && desktop?.hidden) {
      desktop.hidden = false;
      const frame = byId<HTMLElement>('session-screen-wrap');
      if (frame) frame.hidden = true;
      stopScreenTimerOnly();
      void connectDesktop(current.id);
    }
    await pollSession(state.session);
  }
  window.clearTimeout(state.sessionTimer);
  if (state.sessions.some((sess) => sess.state === 'booting' || sess.state === 'running' || sess.state === 'stopping')) {
    state.sessionTimer = window.setTimeout(() => void refreshSessions(), 2500);
  }
}

function renderSessions(): void {
  const host = byId<HTMLDivElement>('session-list');
  if (!host) return;
  host.replaceChildren();
  const view = byId<HTMLElement>('session-view');
  if (state.sessions.length === 0) {
    host.append(el('p', 'cp-hint', 'No VM is booted. Add an image from a link above, then press Boot — or Run audit, which boots one just for the run.'));
    if (view) view.hidden = true;
    return;
  }
  for (const session of state.sessions) {
    const card = el('article', 'rg-session');
    const head = el('div', 'rg-session__head');
    head.append(el('strong', '', session.imageName), statusPill(session.state));
    card.append(head);
    if (session.detail) card.append(el('p', 'cp-hint', session.detail));
    if (session.host && session.port) {
      card.append(el('p', 'rg-muted', `${session.provider ?? 'vm'} · ${session.host}:${session.port}${session.canRun ? ' · ready for a run' : ''}`));
    }
    const actions = el('div', 'rg-actions');
    const consoleBtn = el('button', 'cp-btn cp-btn--sm', 'Console');
    consoleBtn.type = 'button';
    consoleBtn.dataset.action = 'console';
    consoleBtn.dataset.session = session.id;
    actions.append(consoleBtn);
    if (session.canRun) {
      const audit = el('button', 'cp-btn cp-btn--sm cp-btn--primary', 'Run audit on it');
      audit.type = 'button';
      audit.dataset.action = 'run-session';
      audit.dataset.session = session.id;
      actions.append(audit);
    }
    const reset = el('button', 'cp-btn cp-btn--sm', 'Reset to original');
    reset.type = 'button';
    reset.dataset.action = 'reset-session';
    reset.dataset.session = session.id;
    actions.append(reset);
    if (session.state === 'booting' || session.state === 'running') {
      const stop = el('button', 'cp-btn cp-btn--sm', 'Stop VM');
      stop.type = 'button';
      stop.dataset.action = 'stop-session';
      stop.dataset.session = session.id;
      actions.append(stop);
    }
    card.append(actions);
    host.append(card);
  }
}

async function pollSession(id: string): Promise<void> {
  try {
    const tail = await api<{ offset: number; size: number; text: string; source: string }>(
      `/api/sessions/${id}/console?offset=${state.consoleOffset}`,
    );
    state.consoleOffset = tail.offset;
    const pre = byId<HTMLPreElement>('session-console');
    if (pre && tail.text) {
      pre.textContent = (pre.textContent ?? '') + tail.text;
      pre.scrollTop = pre.scrollHeight;
    }
    const note = byId<HTMLParagraphElement>('session-note');
    const session = state.sessions.find((sess) => sess.id === id);
    if (note && session) note.textContent = `${tail.source === 'console' ? 'Serial console from the VM' : 'Agent messages (no serial console for this provider)'} · ${session.detail}`;
  } catch {
    /* the session may have been deleted */
  }
}

function setDesktopStatus(text: string, kind: 'ok' | 'error' | '' = ''): void {
  const status = byId<HTMLElement>('session-desktop-status');
  if (!status) return;
  status.textContent = text;
  status.dataset.kind = kind;
}

type FullscreenCapable = HTMLElement & { webkitRequestFullscreen?: () => void };
type FullscreenDoc = Document & { webkitFullscreenElement?: Element | null; webkitExitFullscreen?: () => void };

/** Full screen for the VM view; Esc leaves it. The browser keeps Esc, so use the toolbar to send other keys. */
async function toggleDesktopFullscreen(): Promise<void> {
  const target = byId<FullscreenCapable>('session-desktop');
  const doc = document as FullscreenDoc;
  if (!target) return;
  try {
    if (document.fullscreenElement || doc.webkitFullscreenElement) {
      if (document.exitFullscreen) await document.exitFullscreen();
      else doc.webkitExitFullscreen?.();
    } else if (target.requestFullscreen) {
      await target.requestFullscreen();
    } else if (target.webkitRequestFullscreen) {
      target.webkitRequestFullscreen();
    } else {
      setDesktopStatus('This browser does not allow full screen for this view.', 'error');
      return;
    }
    target.focus();
  } catch (error) {
    setDesktopStatus(error instanceof Error ? error.message : 'Full screen was blocked.', 'error');
  }
}

function disconnectDesktop(): void {
  try {
    state.rfb?.disconnect();
  } catch {
    /* already closed */
  }
  state.rfb = null;
  state.rfbSession = '';
}

/** Connect the live desktop: QEMU serves VNC over a loopback WebSocket, noVNC draws it in the page. */
async function connectDesktop(id: string): Promise<void> {
  const target = byId<HTMLElement>('session-desktop');
  if (!target) return;
  disconnectDesktop();
  target.replaceChildren();
  setDesktopStatus('Connecting…');
  try {
    const info = await api<DesktopInfo>(`/api/sessions/${id}/desktop`);
    const { default: RFB } = await import('@novnc/novnc');
    // The agent lives at state.url; QEMU's WebSocket listens on the same machine.
    const host = new URL(state.url).hostname || info.host;
    const rfb = new RFB(target, `ws://${host}:${info.port}`, { credentials: { password: info.password } });
    rfb.scaleViewport = true;
    rfb.resizeSession = false;
    rfb.background = '#000';
    rfb.addEventListener('connect', () => {
      if (state.session === id) setDesktopStatus('Connected. Click inside to type and use the mouse.', 'ok');
    });
    rfb.addEventListener('disconnect', (event: Event) => {
      const clean = (event as CustomEvent<{ clean: boolean }>).detail?.clean;
      if (state.rfb === rfb) state.rfb = null;
      setDesktopStatus(clean ? 'Disconnected.' : 'Connection lost. The VM may still be booting: press Connect again.', clean ? '' : 'error');
    });
    state.rfb = rfb;
    state.rfbSession = id;
  } catch (error) {
    setDesktopStatus(error instanceof Error ? error.message : String(error), 'error');
  }
}

function stopScreenTimerOnly(): void {
  window.clearInterval(state.screenTimer);
  state.screenTimer = 0;
}

function stopScreen(): void {
  disconnectDesktop();
  window.clearInterval(state.screenTimer);
  state.screenTimer = 0;
  if (state.screenUrl) {
    URL.revokeObjectURL(state.screenUrl);
    state.screenUrl = '';
  }
}

async function refreshScreen(id: string): Promise<void> {
  try {
    const response = await fetch(`${state.url.replace(/\/$/, '')}/api/sessions/${id}/screen?t=${Date.now()}`, {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    if (!response.ok) return;
    const blob = await response.blob();
    const image = byId<HTMLImageElement>('session-screen');
    if (!image) return;
    if (state.screenUrl) URL.revokeObjectURL(state.screenUrl);
    state.screenUrl = URL.createObjectURL(blob);
    image.src = state.screenUrl;
  } catch {
    /* keep the last frame */
  }
}

async function selectSession(id: string): Promise<void> {
  state.session = id;
  stopScreen();
  state.consoleOffset = 0;
  const pre = byId<HTMLPreElement>('session-console');
  if (pre) pre.textContent = '';
  const view = byId<HTMLElement>('session-view');
  if (view) view.hidden = false;
  const session = state.sessions.find((sess) => sess.id === id);
  const title = byId<HTMLHeadingElement>('session-title');
  if (title) title.textContent = `Console · ${session?.imageName ?? id}`;
  disconnectDesktop();
  const desktop = byId<HTMLElement>('session-desktop-wrap');
  if (desktop) desktop.hidden = !session?.desktopAvailable;
  const wrap = byId<HTMLElement>('session-screen-wrap');
  if (session?.desktopAvailable) {
    if (wrap) wrap.hidden = true;
    void connectDesktop(id);
  } else if (wrap) wrap.hidden = !session?.screenAvailable;
  if (!session?.desktopAvailable && session?.screenAvailable) {
    void refreshScreen(id);
    state.screenTimer = window.setInterval(() => void refreshScreen(id), 2000);
  }
  await pollSession(id);
  view?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function bootImage(id: string, desktopOnly = false): Promise<void> {
  try {
    const created = await api<{ id: string }>(`/api/images/${id}/boot`, { method: 'POST', body: JSON.stringify({ desktopOnly }) });
    message('Booting the VM. The console appears under Booted VMs when the guest answers.', 'ok');
    await refreshSessions();
    await selectSession(created.id);
  } catch (error) {
    message(error instanceof Error ? error.message : String(error), 'error');
  }
}

async function resetSession(id: string): Promise<void> {
  if (!window.confirm('Throw away this VM and boot the original image again? Changes made inside it are lost; finished runs and their reports are kept.')) return;
  try {
    const created = await api<{ id: string }>(`/api/sessions/${id}/reset`, { method: 'POST', body: '{}' });
    stopScreen();
    message('Rebooting from the original image — the overlay with your changes is gone.', 'ok');
    await refreshSessions();
    await selectSession(created.id);
  } catch (error) {
    message(error instanceof Error ? error.message : String(error), 'error');
  }
}

async function stopSession(id: string): Promise<void> {
  try {
    await api(`/api/sessions/${id}/stop`, { method: 'POST', body: '{}' });
    stopScreen();
    message('VM stopped. Your reports stay in the run list.', 'ok');
    await refreshSessions();
  } catch (error) {
    message(error instanceof Error ? error.message : String(error), 'error');
  }
}

async function watchImage(id: string): Promise<void> {
  for (let i = 0; i < 150; i++) {
    await new Promise((resolve) => window.setTimeout(resolve, 2000));
    try {
      await refreshImages();
    } catch {
      return;
    }
    const image = state.images.find((entry) => entry.id === id);
    if (!image) return;
    if (image.state === 'ready') {
      message(`${image.name} is ready${image.detail ? ` (${image.detail})` : ''}.`, 'ok');
      await refreshSessions();
      return;
    }
    if (image.state === 'error') {
      message(`Could not prepare ${image.name}: ${image.detail}`, 'error');
      return;
    }
  }
  message('The download is still going in the background — watch the image card.', 'info');
}

async function addImage(): Promise<void> {
  const value = (id: string) => byId<HTMLInputElement>(id)?.value.trim() ?? '';
  const url = value('add-url');
  if (!url) {
    message('Paste the download link first.', 'error');
    return;
  }
  try {
    message('Sending the link to the agent...', 'info');
    const created = await api<{ id: string }>('/api/images/add', {
      method: 'POST',
      body: JSON.stringify({
        url,
        password: byId<HTMLInputElement>('add-password')?.value ?? '',
        name: value('add-name'),
        family: byId<HTMLSelectElement>('add-family')?.value ?? 'linux',
        keyFile: value('add-key'),
        user: value('add-user'),
        sha256: value('add-sha'),
        boot: byId<HTMLInputElement>('add-boot')?.checked ?? true,
      }),
    });
    message(`Added ${created.id}. Downloading and unpacking — progress is on its card.`, 'ok');
    const password = byId<HTMLInputElement>('add-password');
    if (password) password.value = '';
    await refreshImages();
    await watchImage(created.id);
  } catch (error) {
    message(error instanceof Error ? error.message : String(error), 'error');
  }
}

function wire(): void {
  const storedUrl = stored(URL_KEY, localStorage);
  const storedToken = stored(TOKEN_KEY, sessionStorage);
  state.url = storedUrl || DEFAULT_URL;
  state.token = storedToken;
  const urlInput = byId<HTMLInputElement>('range-url');
  const tokenInput = byId<HTMLInputElement>('range-token');
  if (urlInput) urlInput.value = state.url;
  if (tokenInput && storedToken) tokenInput.value = storedToken;

  byId<HTMLButtonElement>('range-connect-btn')?.addEventListener('click', () => void connect());
  byId<HTMLButtonElement>('add-btn')?.addEventListener('click', () => void addImage());
  byId<HTMLButtonElement>('range-refresh-btn')?.addEventListener('click', () => {
    void refreshImages();
    void refreshRuns();
    void refreshSessions();
  });
  document.addEventListener('fullscreenchange', () => {
    const button = document.querySelector<HTMLButtonElement>('button[data-desktop="fullscreen"]');
    const on = Boolean(document.fullscreenElement);
    if (button) button.textContent = on ? 'Exit full screen' : 'Full screen';
    window.dispatchEvent(new Event('resize')); // noVNC re-fits the picture to the new size
  });
  document.querySelector('.rg__desktop-actions')?.addEventListener('click', (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>('button[data-desktop]');
    if (!button || !state.session) return;
    const act = button.dataset.desktop;
    if (act === 'connect') void connectDesktop(state.session);
    if (act === 'disconnect') {
      disconnectDesktop();
      setDesktopStatus('Disconnected.');
    }
    if (act === 'cad') state.rfb?.sendCtrlAltDel();
    if (act === 'fullscreen') void toggleDesktopFullscreen();
  });
  byId<HTMLButtonElement>('detail-stop')?.addEventListener('click', () => void stopRun());
  byId<HTMLButtonElement>('detail-delete')?.addEventListener('click', () => void deleteRun());
  byId<HTMLButtonElement>('detail-download')?.addEventListener('click', downloadFindings);
  byId<HTMLSelectElement>('detail-categories')?.addEventListener('change', (event) => {
    const select = event.target as HTMLSelectElement;
    const pre = byId<HTMLPreElement>('detail-logfile');
    if (pre) pre.textContent = state.logFiles[select.value] ?? '';
  });

  document.addEventListener('click', (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>('button[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'pull' && button.dataset.image) void pullImage(button.dataset.image);
    if (action === 'boot' && button.dataset.image) void bootImage(button.dataset.image);
    if (action === 'boot-desktop' && button.dataset.image) void bootImage(button.dataset.image, true);
    if (action === 'console' && button.dataset.session) void selectSession(button.dataset.session);
    if (action === 'stop-session' && button.dataset.session) void stopSession(button.dataset.session);
    if (action === 'reset-session' && button.dataset.session) void resetSession(button.dataset.session);
    if (action === 'run-session' && button.dataset.session) {
      const session = state.sessions.find((sess) => sess.id === button.dataset.session);
      if (session) void startRun(session.imageId, 'audit', session.id);
    }
    if (action === 'run' && button.dataset.image) void startRun(button.dataset.image, button.dataset.mode === 'apply' ? 'apply' : 'audit');
    if (action === 'open' && button.dataset.run) void loadRun(button.dataset.run);
  });

  byId<HTMLTableSectionElement>('range-runs')?.addEventListener('click', (event) => {
    const row = (event.target as HTMLElement).closest<HTMLTableRowElement>('tr[data-run]');
    if (row?.dataset.run && !(event.target as HTMLElement).closest('button')) void loadRun(row.dataset.run);
  });

  if (storedToken) void connect();
}

wire();
