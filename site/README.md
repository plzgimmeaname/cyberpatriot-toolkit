# Website

## Make it your own

1. Fork or copy this repository.
2. Edit **`site/site.config.mjs`**: site name, description, public URL, GitHub repo, accent colours, and the season's rounds and dates. That one file drives the header, theme, dashboard and Edit links.
3. Optional overrides without editing the file: `SITE_TITLE`, `SITE_URL`, `SITE_REPO`, `SITE_NOINDEX=false` (set these as build environment variables on your host).
4. Swap `src/assets/logo.svg` and `public/favicon.svg` for your own logo.
5. To make the site public and searchable: set `noindex: false`, delete the `X-Robots-Tag` line in `public/_headers` and replace `public/robots.txt`.
6. Add or edit pages in `../docs/` (see below), then `npm run dev` to preview and `npm test` before you push.

The CyberPatriot Toolkit website: [Astro](https://astro.build/) + [Starlight](https://starlight.astro.build/), published to **GitHub Pages**.

**The content is not in this folder.** At build time, `scripts/sync-docs.mjs` copies `../docs/**/*.md` and `../scripts/` into the site. To change a checklist or guide, edit the file in [`docs/`](../docs). Never edit `src/content/docs/checklists|guides|start-here`: those folders are generated and git-ignored.

## Run it on your computer

You need [Node.js](https://nodejs.org/) 22 or newer.

```bash
cd site
npm install
npm run dev        # http://localhost:4321, reloads when you save a file in site/
```

After you change something in `docs/`, stop `npm run dev` and start it again so the docs are copied over.

| Command | What it does |
|---|---|
| `npm run dev` | Sync the docs and start a local preview |
| `npm run build` | Sync the docs and build the site into `dist/` |
| `npm run preview` | Serve the built `dist/` folder |
| `npm run check` | TypeScript / Astro checks |
| `npm test` | Build, then check every internal link, #anchor, checklist step and download checksum |

## Put it on GitHub Pages (one time)

1. Push the repository to GitHub.
2. In the repository, open **Settings → Pages** and set **Source** to **GitHub Actions**. That is the only setting: `.github/workflows/pages.yml` builds the site and deploys it on every push to `main`.
3. Your site is then at `https://<user>.github.io/<repository>/`, for example `https://plzgimmeaname.github.io/cyberpatriot-toolkit/`.

A project site is served from `/<repository>/`, so the build is told that in **`base` in `site/site.config.mjs`** (`SITE_BASE` overrides it). Links inside the pages go through `withBase()` in `src/data/url.ts`, and links inside the docs are rewritten at build time, so nothing else has to know about the sub-path.

Set `siteUrl` in `site/site.config.mjs` (or the `SITE_URL` variable) to the address people will use: it feeds canonical links and the sitemap.

### Optional: a nicer address

**Settings → Pages → Custom domain**, then set `SITE_URL` to that address **and `base: ''`** in `site/site.config.mjs`, because a custom domain (or a `<user>.github.io` repository) serves the site from the root.

### Optional: only let your class in

GitHub Pages sites are public. The site already asks search engines not to index it (`robots.txt` and a `noindex` tag), but anyone with the link can open it. If you need a login, put a Cloudflare Access (Zero Trust) application in front of the site.

## How the site is organised

```
site/
├── astro.config.mjs        # Starlight config: sidebar, theme, plugins
├── scripts/
│   ├── sync-docs.mjs       # ../docs → src/content/docs (+ data files, downloads)
│   └── verify-build.mjs    # checks dist/ after a build (npm test)
├── public/                 # favicon, robots.txt, _headers (Cloudflare headers)
└── src/
    ├── data/
    │   ├── catalog.mjs     # checklists, rounds, learning path, scripts: edit this when adding an OS
    │   ├── commands.ts     # the Command finder's commands
    │   └── site.ts         # typed helpers
    ├── components/
    │   ├── ChecklistHeader.astro
    │   └── overrides/      # Starlight components we customise (title, content, hero)
    ├── pages/              # home (Learn), toolkit dashboard, tools, downloads, progress
    ├── routeData.ts        # splits the sidebar into the Toolkit and Learn sections
    ├── scripts/            # browser code: progress storage, interactive checklists
    ├── styles/             # theme colours, components, print
    └── content/docs/about.md
```

### Adding a checklist

1. Write `docs/checklists/<name>.md` in the usual format. Every step is a `### N.N Title` heading followed by a `- [ ] Done` line, then a `**Script:** ✅/🔎/✋ ...` line saying what the hardening script does for that step (the build fails without it; a step titled "Fast path ..." is exempt).
2. Add an entry to `CHECKLISTS` in `src/data/catalog.mjs` (and to `SEASON` if a round uses it).
3. Add a sidebar badge in `astro.config.mjs` (optional).
4. Run `npm test`.

### How progress is stored

Everything is in the browser's `localStorage` under keys that start with `cp:v1:`. A checklist step's ID is its heading's anchor (for example `21-see-every-user-on-the-computer`), so **renaming a step's heading resets that one tick**. Nothing is sent to a server.
