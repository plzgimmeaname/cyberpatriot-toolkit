// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLinksValidator from 'starlight-links-validator';
import { CHECKLISTS, LEARNING_PATH, REPO_URL } from './src/data/catalog.mjs';
import config from './site.config.mjs';

const site = config.siteUrl;
const base = config.base || undefined; // GitHub Pages project sites live under /<repository>/
const BASE = (config.base || '').replace(/\/$/, '');
const { accent } = config;

/** @type {Record<string, { text: string; variant: 'note' | 'default' }>} */
const checklistBadges = {
  'windows-10-11': { text: 'R1 · R2', variant: 'note' },
  'windows-server': { text: 'R2+', variant: 'note' },
  'linux-mint': { text: 'R1+', variant: 'note' },
  debian: { text: 'Not in CP-19', variant: 'default' },
  freebsd: { text: 'Not in CP-19', variant: 'default' },
  ubuntu: { text: 'State', variant: 'note' },
};

const ORIGIN = site.replace(/\/$/, '');

/** The <head> tags added to every page. The type is written out because a spread inside an
 *  object literal widens `tag` to `string`, which `astro check` rejects. */
/** @type {Array<{ tag: 'base'|'link'|'meta'|'title'|'style'|'script'|'noscript'|'template'; attrs?: Record<string, string | boolean | undefined>; content?: string }>} */
const headTags = [
  { tag: 'meta', attrs: { name: 'theme-color', content: '#0b1220' } },
  { tag: 'meta', attrs: { name: 'robots', content: config.noindex ? 'noindex' : 'index,follow' } },
  // Our own social card and app icon (rendered by scripts/make-brand.mjs).
  { tag: 'meta', attrs: { property: 'og:site_name', content: config.title } },
  { tag: 'meta', attrs: { property: 'og:type', content: 'website' } },
  { tag: 'meta', attrs: { property: 'og:image', content: `${ORIGIN}/og/rampart.png` } },
  { tag: 'meta', attrs: { property: 'og:image:width', content: '1200' } },
  { tag: 'meta', attrs: { property: 'og:image:height', content: '630' } },
  { tag: 'meta', attrs: { property: 'og:image:alt', content: `${config.title} — hardening checklists, tools and scripts for every CyberPatriot image` } },
  { tag: 'meta', attrs: { name: 'twitter:card', content: 'summary_large_image' } },
  { tag: 'meta', attrs: { name: 'twitter:image', content: `${ORIGIN}/og/rampart.png` } },
  // Installable app: manifest, home-screen icon, offline checklists.
  { tag: 'link', attrs: { rel: 'manifest', href: `${BASE}/manifest.webmanifest` } },
  { tag: 'link', attrs: { rel: 'apple-touch-icon', href: `${BASE}/og/apple-touch-icon.png`, sizes: '180x180' } },
  { tag: 'link', attrs: { rel: 'stylesheet', href: `${BASE}/palette.css` } },
  { tag: 'script', attrs: { src: `${BASE}/palette.js`, defer: true } },
  {
    // Never register the worker on localhost: a cached dev page is impossible to refresh.
    tag: 'script',
    content: `if('serviceWorker'in navigator&&!/^(localhost|127\\.0\\.0\\.1|\\[::1\\])$/.test(location.hostname)){addEventListener('load',function(){navigator.serviceWorker.register('${BASE}/sw.js',{scope:'${BASE}/'}).catch(function(){})})}`,
  },
  {
    tag: 'style',
    content: `:root{--sl-color-accent-low:${accent.darkLow};--sl-color-accent:${accent.dark};--sl-color-accent-high:${accent.darkHigh};--cp-gradient:linear-gradient(135deg,${accent.gradient[0]} 0%,${accent.gradient[1]} 100%)}:root[data-theme='light']{--sl-color-accent-low:${accent.lightLow};--sl-color-accent:${accent.light};--sl-color-accent-high:${accent.lightHigh}}`,
  },
];

export default defineConfig({
  site,
  ...(base ? { base } : {}),
  trailingSlash: 'always',
  integrations: [
    starlight({
      title: config.title,
      description: config.description,
      logo: { src: './src/assets/logo.svg', alt: '' },
      favicon: '/favicon.svg', // Starlight adds the base path itself
      social: [{ icon: 'github', label: 'GitHub repository', href: REPO_URL }],
      editLink: { baseUrl: `${REPO_URL}/edit/main/site/` },
      customCss: [
        '@fontsource-variable/inter',
        '@fontsource-variable/jetbrains-mono',
        '@fontsource-variable/space-grotesk',
        './src/styles/theme.css',
        './src/styles/site.css',
        './src/styles/polish.css',
        './src/styles/print.css',
      ],
      components: {
        PageTitle: './src/components/overrides/PageTitle.astro',
        SiteTitle: './src/components/overrides/SiteTitle.astro',
        Sidebar: './src/components/overrides/Sidebar.astro',
        MarkdownContent: './src/components/overrides/MarkdownContent.astro',
        Hero: './src/components/overrides/Hero.astro',
      },
      head: headTags,
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 3 },
      expressiveCode: {
        themes: ['github-dark-default', 'github-light-default'],
        styleOverrides: { borderRadius: '0.6rem', codeFontFamily: "'JetBrains Mono Variable', ui-monospace, monospace" },
      },
      // Two sections. src/routeData.ts shows only the current section's groups:
      // Toolkit = what experienced people use during a round, Learn = for beginners.
      // Group labels starting with "Learn" belong to the Learn section.
      sidebar: [
        {
          label: 'Toolkit',
          items: [
            { label: 'Dashboard', link: '/toolkit/' },
            { label: 'My progress', link: '/progress/' },
          ],
        },
        {
          label: 'Checklists',
          items: CHECKLISTS.map((c) => ({
            label: c.name,
            link: `/checklists/${c.id}/`,
            badge: checklistBadges[c.id],
          })),
        },
        {
          label: 'Tools',
          items: [
            { label: 'README config builder', link: '/tools/config-builder/' },
            { label: 'Round timer', link: '/tools/round-timer/' },
            { label: 'Field cards', link: '/field-cards/' },
            { label: 'Findings to-do list', link: '/tools/findings/' },
            { label: 'Round log', link: '/tools/round-log/' },
            { label: 'Score dropped: triage', link: '/tools/triage/' },
            { label: 'Round post-mortem', link: '/tools/post-mortem/' },
            { label: 'Command finder', link: '/tools/commands/' },
            { label: 'Forensics helper', link: '/tools/forensics/' },
            { label: 'Download the scripts', link: '/downloads/' },
            { label: 'Practice range', link: '/range/' },
          ],
        },
        {
          label: 'Cisco, basics → State',
          items: [
            { label: 'Overview and level ladder', link: '/cisco/' },
            { label: 'Level 1 · Basics', link: '/cisco/level-1-basics/', badge: { text: 'L1', variant: 'note' } },
            { label: 'Level 2 · Addressing and routing', link: '/cisco/level-2-addressing/', badge: { text: 'L2', variant: 'note' } },
            { label: 'Level 3 · Switching and services', link: '/cisco/level-3-switching/', badge: { text: 'L3', variant: 'note' } },
            { label: 'Level 4 · State round', link: '/cisco/level-4-state/', badge: { text: 'L4', variant: 'caution' } },
            { label: 'Cisco & Packet Tracer reference', link: '/guides/cisco-networking/' },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'Points map', link: '/points-map/' },
            { label: 'Gotchas by image', link: '/gotchas/' },
            { label: 'What the scripts do', link: '/automation/' },
            { label: 'Forensics questions', link: '/guides/forensics-questions/' },
            { label: 'Linux service hardening', link: '/guides/linux-service-hardening/' },
          ],
        },
        {
          label: 'Project',
          items: [
            { label: 'Changelog & contributors', link: '/history/' },
            { label: 'About this site', link: '/about/' },
          ],
        },
        {
          label: 'Learn: Start here',
          items: [
            { label: 'Welcome', link: '/' },
            ...LEARNING_PATH.map((l, i) => ({
              label: `${i + 1}. ${l.label}`,
              link: `/${l.path.replace(/\.md$/, '')}/`,
            })),
          ],
        },
        {
          label: 'Learn: Glossary & more',
          items: [
            { label: 'Glossary', link: '/guides/glossary/' },
            { label: 'Glossary quiz', link: '/tools/glossary-quiz/' },
            { label: 'Networking quiz', link: '/tools/networking-quiz/' },
            { label: 'For mentors & teachers', link: '/guides/for-mentors-and-teachers/' },
            { label: 'About this site', link: '/about/' },
          ],
        },
      ],
      routeMiddleware: './src/routeData.ts',
      // The hand-written pages below cannot be validated by the plugin, and every path carries the base prefix
      plugins: [
        starlightLinksValidator({
          errorOnLocalLinks: true,
          exclude: [
            '/',
            '/#checklists',
            '/toolkit/',
            '/files/**',
            '/tools/**',
            '/progress/',
            '/downloads/',
            '/field-cards/',
            '/points-map/',
            '/automation/',
            '/gotchas/',
            '/history/',
          ].map((p) => `${BASE}${p}`),
        }),
      ],
    }),
  ],
});
