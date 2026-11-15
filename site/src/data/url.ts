// A GitHub Pages project site is served from /<repository>/, not from the root of the
// domain, so a link written as "/toolkit/" would point at the wrong place. Every
// root-absolute link in our own pages goes through this helper instead.
import config from '../../site.config.mjs';

const BASE = ((config as { base?: string }).base || '').replace(/\/$/, '');

/**
 * Prefix a site path ('/toolkit/') with the path the site is served from.
 * Anything that is not a root-absolute path (http://…, //host, #anchor, relative)
 * is returned unchanged, and a path that already carries the prefix is left alone,
 * so this is safe to apply at every link a template builds.
 */
export function withBase(path: string): string {
  if (!path.startsWith('/') || path.startsWith('//')) return path;
  if (BASE && (path === BASE || path.startsWith(`${BASE}/`))) return path;
  return `${BASE}${path}`;
}
