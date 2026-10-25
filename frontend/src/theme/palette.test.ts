import { readFileSync } from 'node:fs';
const css = readFileSync('src/styles/theme.css', 'utf8');
const bootstrap = readFileSync('public/theme-init.js', 'utf8');
import { expect, it } from 'vitest';
const dark = css.split('[data-theme="dark"] {')[1].split('}')[0];
const token = (name: string) => dark.match(new RegExp(`--color-${name}: (#[A-Fa-f0-9]{6});`))![1];
const luminance = (hex: string) => {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4);
  return .2126 * r + .7152 * g + .0722 * b;
};
const contrast = (a: string, b: string) => (Math.max(luminance(a), luminance(b)) + .05) / (Math.min(luminance(a), luminance(b)) + .05);
it('uses the requested dark palette and accessible foregrounds on each reading surface', () => {
  expect(token('bg')).toBe('#090907');
  expect(token('secondary')).toBe('#6C5636');
  expect(token('accent')).toBe('#B99D73');
  for (const bg of ['bg', 'surface']) {
    for (const fg of ['text', 'heading', 'muted', 'danger']) expect(contrast(token(bg), token(fg)), `${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token(bg), token('border')), `border on ${bg}`).toBeGreaterThanOrEqual(3);
  }
  expect(contrast(token('on-action'), token('action-bg'))).toBeGreaterThanOrEqual(4.5);
  expect(contrast(token('on-accent'), token('accent'))).toBeGreaterThanOrEqual(4.5);
  expect(contrast(token('landing-text'), token('scene-accent'))).toBeGreaterThanOrEqual(4.5);
  expect(contrast(token('heading'), token('scene-accent'))).toBeGreaterThanOrEqual(3);
});
it('resolves the initial theme before React even when storage is blocked', () => {
  const script = bootstrap;
  document.head.innerHTML = '<meta name="theme-color" content="#DDE3E8">';
  const execute = new Function('window', 'document', 'localStorage', script);
  execute({ matchMedia: () => ({ matches: true }) }, document, {getItem: () => {throw new Error('blocked');}});
  expect(document.documentElement.dataset.theme).toBe('dark');
  expect(document.documentElement.style.backgroundColor).toBe('rgb(9, 9, 7)');
  execute({ matchMedia: () => ({ matches: true }) }, document, {getItem: () => 'light'});
  expect(document.documentElement.dataset.theme).toBe('light');
  expect(document.querySelector('meta')?.content).toBe('#DDE3E8');
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.removeAttribute('style');
});
