// Make this site your own: edit this file, nothing else is required.
// Plain JavaScript so both the build scripts (Node) and Astro can read it.
// Every value can also be overridden with an environment variable (see README).

export default {
  /** Name shown in the header, browser tab and search results. */
  title: process.env.SITE_TITLE || 'Rampart',

  /** One sentence for search engines and link previews. */
  description:
    'Rampart: beginner-friendly CyberPatriot checklists, guides, tools and hardening scripts for Windows, Windows Server, Linux Mint, Debian, Ubuntu and FreeBSD.',

  /** Public address of the deployed site (canonical links, sitemap). */
  siteUrl: process.env.SITE_URL || 'https://plzgimmeaname.github.io/cyberpatriot-toolkit',

  /**
   * Sub-path the site is served from. GitHub Pages serves a project site at /<repository>/.
   * Use '' when the site sits at the root of a domain (a <user>.github.io repository, or a custom domain).
   * If you change this, also edit the full links in src/content/docs/about.md and 404.md: Astro pages and
   * docs links are prefixed automatically, but frontmatter and hand-written content cannot be, so they spell it out.
   */
  base: process.env.SITE_BASE ?? '/cyberpatriot-toolkit',

  /** GitHub "owner/name" of the repository that holds this site. Used for Edit links and downloads. */
  repo: process.env.SITE_REPO || 'plzgimmeaname/cyberpatriot-toolkit',
  branch: 'main',

  /**
   * Keep the site out of search engines. Set to false for a public team site.
   * (Also edit site/public/_headers and robots.txt if you flip this.)
   */
  noindex: process.env.SITE_NOINDEX ? process.env.SITE_NOINDEX !== 'false' : true,

  /** Accent colours: dark mode, light mode, and the two ends of the gradient. */
  accent: {
    dark: '#8da2ff',
    darkLow: '#1b2147',
    darkHigh: '#dbe1ff',
    light: '#3d4fd6',
    lightLow: '#e8ebfd',
    lightHigh: '#1e2a82',
    gradient: ['#8da2ff', '#5b3fd9'],
  },

  /** The competition season shown on the dashboard and checklists. Edit rounds each year. */
  season: {
    name: 'CyberPatriot 19',
    years: '2026–27',
    rounds: [
      { id: 'r1', name: 'Round 1', dates: 'Oct 22–25, 2026', images: ['windows', 'mint'] },
      // Image lists follow the official CP-19 challenges page, not older seasons:
      // https://www.uscyberpatriot.org/competition/current-competition/challenges-by-round
      { id: 'r2', name: 'Round 2', dates: 'Nov 12–15, 2026', images: ['windows', 'server', 'mint'] },
      { id: 'state', name: 'State Round', dates: 'Dec 10–13, 2026', images: ['server', 'mint', 'ubuntu'] },
      { id: 'semis', name: 'Semifinals', dates: 'Jan 21–23, 2027', images: ['mint', 'server'] },
    ],
  },
};
