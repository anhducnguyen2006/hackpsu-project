import { useEffect, useState, useSyncExternalStore } from 'react';

export type Theme = 'light' | 'dark';
const STORAGE_KEY = 'dataopedia-theme';
const CHANGE_EVENT = 'dataopedia:theme';
const validTheme = (value: unknown): value is Theme => value === 'light' || value === 'dark';
let preference: Theme | null = null;

function readPreference(): Theme | null {
  try { const value = localStorage.getItem(STORAGE_KEY); return validTheme(value) ? value : null; }
  catch { return null; }
}
function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (root.dataset.theme === theme) return;
  root.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#090907' : '#DDE3E8');
  window.dispatchEvent(new Event(CHANGE_EVENT));
}
export function initializeTheme() {
  const system = window.matchMedia?.('(prefers-color-scheme: dark)');
  preference = readPreference();
  const resolve = () => applyTheme(preference ?? (system?.matches ? 'dark' : 'light'));
  resolve();
  const frame = requestAnimationFrame(() => { document.documentElement.dataset.themeReady = ''; });
  const onSystem = () => { if (!preference) resolve(); };
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY && event.key !== null) return;
    preference = readPreference(); resolve();
  };
  system?.addEventListener('change', onSystem);
  window.addEventListener('storage', onStorage);
  return () => {
    cancelAnimationFrame(frame);
    system?.removeEventListener('change', onSystem);
    window.removeEventListener('storage', onStorage);
  };
}
export function setTheme(theme: Theme) {
  preference = theme;
  try { localStorage.setItem(STORAGE_KEY, theme); } catch { /* In-memory choice still works. */ }
  applyTheme(theme);
}
export const getTheme = (): Theme => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
export function subscribeTheme(listener: () => void) {
  window.addEventListener(CHANGE_EVENT, listener);
  return () => window.removeEventListener(CHANGE_EVENT, listener);
}
export function useTheme() { return useSyncExternalStore(subscribeTheme, getTheme, () => 'light' as Theme); }

/** Canvas renderers sample the same animated CSS tokens, retaining camera and layout state. */
export function observeThemeColors(update: (style: CSSStyleDeclaration) => void) {
  let frame = 0;
  const sample = () => update(getComputedStyle(document.documentElement));
  const changed = () => {
    cancelAnimationFrame(frame);
    sample();
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    const start = performance.now();
    const tick = () => {
      sample();
      if (performance.now() - start < 450) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
  };
  const unsubscribe = subscribeTheme(changed);
  sample();
  // Lazy routes may mount after the theme event but before its transition ends.
  if (document.documentElement.getAnimations?.().some(animation => animation.playState === 'running')) changed();
  return () => { unsubscribe(); cancelAnimationFrame(frame); };
}
export function themeColor(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function useThemeColor(name: string) {
  const [color, setColor] = useState(() => themeColor(name));
  useEffect(() => observeThemeColors(style => setColor(style.getPropertyValue(name).trim())), [name]);
  return color;
}
