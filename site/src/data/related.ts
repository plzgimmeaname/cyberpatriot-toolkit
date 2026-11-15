// Tools worth opening next to a given page, shown as "Tools for this page".
// Keys are page ids (the docs path without ".md"). Checklists are handled by
// ChecklistHeader and use CHECKLIST_TOOLS.
import type { UiIconName } from './icons';

export interface RelatedTool {
  href: string;
  label: string;
  hint: string;
  icon: UiIconName;
}

const commands = (os: string): RelatedTool => ({
  href: `/tools/commands/?os=${os}`,
  label: 'Command finder',
  hint: 'Search commands by what you want to do',
  icon: 'terminal',
});

const T = {
  builder: { href: '/tools/config-builder/', label: 'README config builder', hint: 'Turn the README into a config file', icon: 'sliders' },
  timer: { href: '/tools/round-timer/', label: 'Round timer', hint: 'A 4-hour countdown with the game plan', icon: 'timer' },
  log: { href: '/tools/round-log/', label: 'Round log', hint: 'Log changes, find what cost you points', icon: 'clipboard' },
  findings: { href: '/tools/findings/', label: 'Findings to-do list', hint: "Turn the script's report into a to-do list", icon: 'clipboard' },
  forensics: { href: '/tools/forensics/', label: 'Forensics helper', hint: 'Hash a file, decode Base64 and more', icon: 'search' },
  glossaryQuiz: { href: '/tools/glossary-quiz/', label: 'Glossary quiz', hint: 'Flashcards for the words you will see', icon: 'book' },
  netQuiz: { href: '/tools/networking-quiz/', label: 'Networking quiz', hint: 'Quiz and endless subnetting practice', icon: 'book' },
  downloads: { href: '/downloads/', label: 'Download the scripts', hint: 'One-line download commands and checksums', icon: 'download' },
  triage: { href: '/tools/triage/', label: 'Score dropped: triage', hint: 'Likely cause and how to put it back', icon: 'search' },
  postMortem: { href: '/tools/post-mortem/', label: 'Round post-mortem', hint: 'What we missed and what changes next round', icon: 'clipboard' },
  pointsMap: { href: '/points-map/', label: 'Points map', hint: 'Which section covers which scored category', icon: 'sliders' },
  gotchas: { href: '/gotchas/', label: 'Gotchas by image', hint: 'The traps that only exist on one image', icon: 'book' },
  fieldCards: { href: '/field-cards/', label: 'Field cards', hint: 'The commands, on one printable page', icon: 'download' },
} satisfies Record<string, RelatedTool>;

export const RELATED: Record<string, RelatedTool[]> = {
  'start-here/what-is-cyberpatriot': [T.glossaryQuiz],
  'start-here/reading-the-readme': [T.builder],
  'start-here/round-game-plan': [T.timer, T.log, T.fieldCards],
  'start-here/linux-terminal-basics': [commands('linux')],
  'start-here/powershell-basics': [commands('windows')],
  'start-here/using-the-scripts': [T.downloads, T.builder, T.findings],
  'guides/things-that-lose-points': [T.log, T.triage, T.postMortem],
  'guides/forensics-questions': [T.forensics, commands('linux'), T.gotchas],
  'guides/glossary': [T.glossaryQuiz],
  'guides/cisco-networking': [T.netQuiz, commands('cisco')],
  'guides/linux-service-hardening': [T.builder, commands('linux'), T.pointsMap],
};

/** Shown in the header of every checklist; `os` is the Command finder filter. */
export function checklistTools(os: string): RelatedTool[] {
  return [T.findings, T.log, commands(os), T.forensics];
}
