#!/usr/bin/env node
// Builds the site's own branding and offline machinery from site.config.mjs and
// the data sync-docs.mjs just generated:
//   public/og/*.png              social cards + app icons (rendered with sharp)
//   public/manifest.webmanifest  installable app manifest (base path included)
//   public/sw.js                 service worker: the checklists work offline
//   public/palette.js            data + UI for the ⌘K command palette
// Runs after sync-docs (see package.json), so it never invents content.

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { CHECKLISTS, SEASON } from '../src/data/catalog.mjs';
import config from '../site.config.mjs';

const SITE = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const PUBLIC = join(SITE, 'public');
const OG = join(PUBLIC, 'og');
const BASE = (config.base || '').replace(/\/$/, '');
const ORIGIN = config.siteUrl.replace(/\/$/, '');
const FONT = "'DejaVu Sans','Helvetica Neue',Helvetica,Arial,sans-serif";
const MONO = "'DejaVu Sans Mono','SFMono-Regular',Menlo,Consolas,monospace";

const pages = JSON.parse(readFileSync(join(SITE, 'src/data/generated/pages.json'), 'utf8'));
const checklists = JSON.parse(readFileSync(join(SITE, 'src/data/generated/checklists.json'), 'utf8'));
const downloads = JSON.parse(readFileSync(join(SITE, 'src/data/generated/downloads.json'), 'utf8'));

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

/** The battlement mark as an SVG group, scaled from its 48×48 artboard. */
function mark(x, y, size) {
  const s = size / 48;
  return `<g transform="translate(${x} ${y}) scale(${s})">
    <path fill="url(#mark)" fill-rule="evenodd" d="M4 9h10v6h6V9h8v6h6V9h10v29a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V9Zm7 16v10h7V25h-7Zm12 0v10h7V25h-7Zm12 0v10h7V25h-7Z"/>
  </g>`;
}

const GRADIENT = `<linearGradient id="mark" x1="6" y1="7" x2="42" y2="43" gradientUnits="userSpaceOnUse">
  <stop stop-color="#a9b8ff"/><stop offset="0.55" stop-color="#8da2ff"/><stop offset="1" stop-color="#5b3fd9"/>
</linearGradient>`;

/** Long text -> lines that fit the card. */
function wrap(text, maxChars) {
  const words = String(text).split(/\s+/);
  const lines = [];
  let line = '';
  for (const w of words) {
    if ((line + ' ' + w).trim().length > maxChars && line) {
      lines.push(line);
      line = w;
    } else line = (line + ' ' + w).trim();
  }
  if (line) lines.push(line);
  return lines;
}

/** One 1200×630 social card. */
function cardSvg({ eyebrow, title, subtitle, footer }) {
  const titleLines = wrap(title, 26).slice(0, 2);
  const subLines = wrap(subtitle, 56).slice(0, 2);
  const titleY = 300;
  const subY = titleY + titleLines.length * 70 + 34;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
    <defs>${GRADIENT}
      <linearGradient id="glow" x1="0" y1="0" x2="1" y2="1">
        <stop stop-color="#8da2ff" stop-opacity="0.20"/><stop offset="1" stop-color="#5b3fd9" stop-opacity="0"/>
      </linearGradient>
      <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M40 0H0V40" fill="none" stroke="#8da2ff" stroke-opacity="0.07" stroke-width="1"/>
      </pattern>
    </defs>
    <rect width="1200" height="630" fill="#0b1220"/>
    <rect width="1200" height="630" fill="url(#grid)"/>
    <rect width="1200" height="630" fill="url(#glow)"/>
    <rect x="0" y="0" width="1200" height="8" fill="url(#mark)"/>
    ${mark(80, 92, 96)}
    <text x="196" y="136" font-family="${FONT}" font-size="34" font-weight="700" fill="#ffffff">${esc(config.title)}</text>
    <text x="196" y="176" font-family="${MONO}" font-size="19" fill="#8da2ff">${esc(eyebrow)}</text>
    ${titleLines
      .map(
        (l, i) =>
          `<text x="80" y="${titleY + i * 70}" font-family="${FONT}" font-size="58" font-weight="800" fill="#ffffff">${esc(l)}</text>`,
      )
      .join('')}
    ${subLines
      .map(
        (l, i) =>
          `<text x="80" y="${subY + i * 36}" font-family="${FONT}" font-size="24" fill="#a7b0c0">${esc(l)}</text>`,
      )
      .join('')}
    <rect x="80" y="540" width="1040" height="1" fill="#8da2ff" fill-opacity="0.25"/>
    <text x="80" y="582" font-family="${MONO}" font-size="19" fill="#7b8598">${esc(footer)}</text>
    <text x="1120" y="582" text-anchor="end" font-family="${MONO}" font-size="19" fill="#8da2ff">${esc(
      ORIGIN.replace(/^https?:\/\//, ''),
    )}</text>
  </svg>`;
}

async function png(svg, file, width) {
  const img = sharp(Buffer.from(svg));
  const info = await (width ? img.resize({ width }) : img).png({ compressionLevel: 9 }).toFile(file);
  return `${file.split('/public/')[1]} (${Math.round(info.size / 1024)} kB)`;
}

/** Square app icon: dark tile, rounded like a phone icon, mark centred. */
function iconSvg(size) {
  const pad = Math.round(size * 0.16);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <defs>${GRADIENT}</defs>
    <rect width="${size}" height="${size}" rx="${Math.round(size * 0.22)}" fill="#0b1220"/>
    ${mark(pad, pad, size - pad * 2)}
  </svg>`;
}

const written = [];

mkdirSync(OG, { recursive: true });

// ---- Social cards -----------------------------------------------------------
const season = `${SEASON.name} ${SEASON.years}`;
written.push(
  await png(
    cardSvg({
      eyebrow: `${season} · checklists · tools · scripts`,
      title: 'Hardening checklists that explain every step',
      subtitle: 'Checklists, tools and scripts that explain every step, for every image in the round.',
      footer: `${checklists && Object.keys(checklists).length} checklists · ${
        Object.values(checklists).reduce((n, c) => n + c.steps.length, 0)
      } steps · ${downloads.length} script files`,
    }),
    join(OG, 'rampart.png'),
  ),
);

for (const c of CHECKLISTS) {
  const data = checklists[`checklists/${c.id}`];
  if (!data) continue;
  const sections = new Set(data.steps.map((s) => s.section)).size;
  written.push(
    await png(
      cardSvg({
        eyebrow: `${c.name} · ${season}`,
        title: data.title.replace(/\s*\(.*\)\s*$/, ''),
        subtitle: c.blurb,
        footer: `${data.steps.length} steps · ${sections} sections · ${downloads.length} script files`,
      }),
      join(OG, `checklist-${c.id}.png`),
    ),
  );
}

// ---- App icons --------------------------------------------------------------
written.push(await png(iconSvg(180), join(OG, 'apple-touch-icon.png')));
written.push(await png(iconSvg(192), join(OG, 'icon-192.png')));
written.push(await png(iconSvg(512), join(OG, 'icon-512.png')));

// ---- Web app manifest -------------------------------------------------------
writeFileSync(
  join(PUBLIC, 'manifest.webmanifest'),
  `${JSON.stringify(
    {
      name: `${config.title} — CyberPatriot Toolkit`,
      short_name: config.title,
      description: config.description,
      start_url: `${BASE}/`,
      scope: `${BASE}/`,
      display: 'standalone',
      background_color: '#0b1220',
      theme_color: '#0b1220',
      icons: [
        { src: `${BASE}/og/icon-192.png`, sizes: '192x192', type: 'image/png', purpose: 'any' },
        { src: `${BASE}/og/icon-512.png`, sizes: '512x512', type: 'image/png', purpose: 'any' },
        { src: `${BASE}/og/icon-512.png`, sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ],
    },
    null,
    2,
  )}\n`,
);
written.push('manifest.webmanifest');

// ---- Service worker: the whole site works with no internet -------------------
/** Every route the site actually builds: hand-written pages on disk plus the synced docs. */
function pageRoutes(dir = join(SITE, 'src/pages'), prefix = '') {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) out.push(...pageRoutes(join(dir, entry.name), `${prefix}/${entry.name}`));
    else if (entry.name.endsWith('.astro') && !entry.name.includes('[')) {
      const base = entry.name.replace(/\.astro$/, '');
      out.push(base === 'index' ? `${prefix}/` : `${prefix}/${base}/`);
    }
  }
  return out;
}

const routes = new Set([
  '/',
  '/about/', // a Starlight content page: not in src/pages and not in docs/
  ...Object.values(pages).map((p) => p.route),
  ...pageRoutes().filter((r) => r !== '/404/'),
  // The field cards are one dynamic route; list them explicitly.
  ...CHECKLISTS.map((c) => `/field-cards/${c.id}/`),
]);
const core = [...routes].map((route) => `${BASE}${route}`);
const build = Date.now().toString(36);

writeFileSync(
  join(PUBLIC, 'sw.js'),
  `// Generated by site/scripts/make-brand.mjs. Do not edit by hand.
// Strategy: pages are network-first (a new deploy shows up on the next load),
// styles/uploads/icons are cache-first with a background refresh. Only GET
// requests for this site are touched; nothing is ever sent anywhere.
const CACHE = 'rampart-${build}';
const BASE = ${JSON.stringify(BASE)};
const CORE = ${JSON.stringify(core, null, 2)};
const ASSET = ${JSON.stringify([`${BASE}/_astro/`, `${BASE}/files/`, `${BASE}/og/`, `${BASE}/pagefind/`, `${BASE}/fonts/`])};

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      Promise.allSettled(CORE.map((url) => cache.add(new Request(url, { cache: 'reload' })))),
    ).then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin || !url.pathname.startsWith(BASE + '/')) return;
  if (url.pathname.endsWith('/sw.js')) return;

  // Pages: try the network, fall back to the cached copy, then to the home page.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) caches.open(CACHE).then((c) => c.put(req, res.clone()));
          return res;
        })
        .catch(async () => (await caches.match(req)) || (await caches.match(BASE + '/')) || Response.error()),
    );
    return;
  }

  // Assets: serve the cached copy immediately and refresh it in the background.
  if (ASSET.some((p) => url.pathname.startsWith(p))) {
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const hit = await cache.match(req);
        const network = fetch(req)
          .then((res) => {
            if (res.ok) cache.put(req, res.clone());
            return res;
          })
          .catch(() => hit);
        return hit || network;
      }),
    );
  }
});
`,
);
written.push('sw.js');

// ---- Command palette data + UI ---------------------------------------------
const palette = {
  pages: Object.entries(pages)
    .map(([slug, p]) => ({ title: p.title, route: p.route, kind: 'page', slug }))
    .sort((a, b) => a.title.localeCompare(b.title)),
  steps: Object.entries(checklists).flatMap(([slug, c]) =>
    c.steps.map((s) => ({
      title: s.title,
      section: s.section,
      route: `${c.route}#${s.id}`,
      kind: 'step',
      checklist: c.title.replace(/\s*\(.*\)\s*$/, ''),
      script: s.script || 'manual',
      slug,
    })),
  ),
};

writeFileSync(
  join(PUBLIC, 'palette.js'),
  `// Generated by site/scripts/make-brand.mjs. A ⌘K / Ctrl-K palette over every
// page and every checklist step. No dependencies, nothing leaves the page.
(() => {
  const DATA = ${JSON.stringify(palette)};
  const BASE = ${JSON.stringify(BASE)};
  let ui = null, items = [], active = 0;

  const norm = (s) => s.toLowerCase().normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '');
  const all = DATA.pages.concat(DATA.steps);
  for (const item of all) item.hay = norm(item.title + ' ' + (item.section || '') + ' ' + (item.checklist || ''));

  function build() {
    const wrap = document.createElement('div');
    wrap.className = 'cp-pal';
    wrap.hidden = true;
    wrap.innerHTML =
      '<div class="cp-pal__backdrop" data-pal-close></div>' +
      '<div class="cp-pal__box" role="dialog" aria-modal="true" aria-label="Jump to a page or step">' +
        '<input class="cp-pal__input" type="search" placeholder="Jump to a checklist step, tool or page…" aria-label="Search the site" autocomplete="off" spellcheck="false">' +
        '<ul class="cp-pal__list" role="listbox" aria-label="Results"></ul>' +
        '<p class="cp-pal__foot"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open</span><span><kbd>Esc</kbd> close</span><span class="cp-pal__hint">works offline</span></p>' +
      '</div>';
    document.body.appendChild(wrap);
    const input = wrap.querySelector('.cp-pal__input');
    const list = wrap.querySelector('.cp-pal__list');
    input.addEventListener('input', () => { active = 0; render(); });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(active + 1, items.length - 1); paint(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(active - 1, 0); paint(); }
      else if (e.key === 'Enter') { e.preventDefault(); go(items[active]); }
      else if (e.key === 'Escape') { e.preventDefault(); close(); }
    });
    list.addEventListener('click', (e) => {
      const li = e.target.closest('[data-i]');
      if (li) go(items[Number(li.dataset.i)]);
    });
    wrap.querySelector('[data-pal-close]').addEventListener('click', close);
    return { wrap, input, list };
  }

  function render() {
    const q = norm(ui.input.value.trim());
    items = (q ? all.filter((x) => q.split(/\\s+/).every((w) => x.hay.includes(w))) : DATA.pages.slice(0, 12))
      .sort((a, b) => {
        const a0 = a.title.toLowerCase().startsWith(q) ? 0 : 1, b0 = b.title.toLowerCase().startsWith(q) ? 0 : 1;
        return a0 - b0 || a.title.length - b.title.length;
      })
      .slice(0, 40);
    ui.list.innerHTML = items.length
      ? items.map((x, i) =>
          '<li role="option" data-i="' + i + '" class="cp-pal__item' + (i === active ? ' is-active' : '') + '">' +
            '<span class="cp-pal__title">' + esc(x.title) + '</span>' +
            (x.kind === 'step'
              ? '<span class="cp-pal__meta">' + esc(x.checklist) + ' · ' + esc(x.section || '') + '</span>'
              : '<span class="cp-pal__meta">page</span>') +
            (x.kind === 'step' ? '<span class="cp-pal__badge cp-pal__badge--' + x.script + '">' + x.script + '</span>' : '') +
          '</li>').join('')
      : '<li class="cp-pal__empty">Nothing matches “' + esc(ui.input.value) + '”.</li>';
    paint();
  }

  function paint() {
    ui.list.querySelectorAll('[data-i]').forEach((li, i) => li.classList.toggle('is-active', i === active));
    const cur = ui.list.querySelector('.is-active');
    if (cur) cur.scrollIntoView({ block: 'nearest' });
  }

  function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]); }

  function go(item) {
    if (!item) return;
    close();
    location.href = item.route.startsWith('/') ? BASE + item.route : item.route;
  }

  function open() {
    if (!ui) ui = build();
    ui.wrap.hidden = false;
    document.documentElement.classList.add('cp-pal-open');
    ui.input.value = '';
    render();
    ui.input.focus();
  }
  function close() {
    if (!ui) return;
    ui.wrap.hidden = true;
    document.documentElement.classList.remove('cp-pal-open');
  }

  addEventListener('keydown', (e) => {
    const typing = /^(input|textarea|select)$/i.test(document.activeElement?.tagName || '') || document.activeElement?.isContentEditable;
    if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) { e.preventDefault(); open(); return; }
    if (e.key === 'Escape' && ui && !ui.wrap.hidden) { e.preventDefault(); close(); return; }
    if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey) {
      const search = document.querySelector('site-search button, [data-open-modal]');
      if (!search) { e.preventDefault(); open(); }
    }
  });
})();
`,
);
written.push('palette.js');

// ---- Palette styles (kept out of Astro so the palette works on every page) ---
const css = `/* Generated by site/scripts/make-brand.mjs */
.cp-pal{position:fixed;inset:0;z-index:9999;display:grid;place-items:start center;padding-top:12vh}
.cp-pal[hidden]{display:none}
.cp-pal-open{overflow:hidden}
.cp-pal__backdrop{position:fixed;inset:0;background:rgba(4,7,15,.62);backdrop-filter:blur(3px)}
.cp-pal__box{position:relative;width:min(46rem,94vw);max-height:70vh;display:flex;flex-direction:column;border:1px solid rgba(141,162,255,.28);border-radius:.9rem;background:#0e1424;box-shadow:0 24px 60px rgba(0,0,0,.55);overflow:hidden;color:#e8ecf6}
.cp-pal__input{width:100%;padding:1rem 1.15rem;border:0;border-bottom:1px solid rgba(141,162,255,.2);background:transparent;color:#fff;font:inherit;font-size:1.02rem;outline:none}
.cp-pal__input::placeholder{color:#7b8598}
.cp-pal__list{margin:0;padding:.35rem;list-style:none;overflow:auto}
.cp-pal__item{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:.35rem .75rem;align-items:center;padding:.55rem .7rem;border-radius:.55rem;cursor:pointer}
.cp-pal__item.is-active{background:rgba(141,162,255,.16)}
.cp-pal__title{color:#fff;font-size:.94rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cp-pal__meta{grid-column:1;color:#8d97aa;font-size:.74rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cp-pal__badge{grid-row:1/3;grid-column:2;padding:.05rem .4rem;border-radius:.35rem;background:rgba(141,162,255,.14);color:#b9c4ff;font-size:.66rem;text-transform:uppercase;letter-spacing:.04em}
.cp-pal__badge--auto{background:rgba(52,199,123,.16);color:#7ee2a8}
.cp-pal__badge--review{background:rgba(255,193,94,.16);color:#ffd08a}
.cp-pal__badge--manual{background:rgba(141,162,255,.14);color:#b9c4ff}
.cp-pal__empty{padding:1rem .8rem;color:#8d97aa;font-size:.9rem}
.cp-pal__foot{display:flex;flex-wrap:wrap;gap:.9rem;margin:0;padding:.55rem .9rem;border-top:1px solid rgba(141,162,255,.16);color:#7b8598;font-size:.72rem}
.cp-pal__foot kbd{padding:.05rem .3rem;border:1px solid #2a3550;border-radius:.25rem;background:#141c30;color:#c3cbe0;font-size:.7rem}
.cp-pal__hint{margin-left:auto;color:#5b6678}
@media (max-width:34rem){.cp-pal__meta{display:none}.cp-pal__item{grid-template-columns:minmax(0,1fr) auto}}
`;
writeFileSync(join(PUBLIC, 'palette.css'), css);
written.push('palette.css');

console.log(`make-brand: ${written.length} files — ${written.join(', ')}`);
