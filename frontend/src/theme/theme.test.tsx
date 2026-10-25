import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { initializeTheme, observeThemeColors, setTheme } from './theme';
import { ThemeToggle } from '../components/ThemeToggle';

let system: EventTarget & { matches: boolean };
let dispose: () => void;
beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  system = Object.assign(new EventTarget(), { matches: true });
  vi.stubGlobal('matchMedia', () => system);
});
afterEach(() => { dispose?.(); vi.unstubAllGlobals(); });
it('follows system changes only until a user chooses a theme', () => {
  dispose = initializeTheme();
  expect(document.documentElement.dataset.theme).toBe('dark');
  system.matches = false;
  system.dispatchEvent(new Event('change'));
  expect(document.documentElement.dataset.theme).toBe('light');
  setTheme('dark');
  expect(localStorage.getItem('dataopedia-theme')).toBe('dark');
  system.dispatchEvent(new Event('change'));
  expect(document.documentElement.dataset.theme).toBe('dark');
});
it('restores a valid preference and ignores invalid stored values', () => {
  localStorage.setItem('dataopedia-theme', 'light');
  dispose = initializeTheme();
  expect(document.documentElement.dataset.theme).toBe('light');
  dispose();
  localStorage.setItem('dataopedia-theme', 'invalid');
  dispose = initializeTheme();
  expect(document.documentElement.dataset.theme).toBe('dark');
});
it('synchronizes another tab and falls back to the system when storage is cleared', () => {
  dispose = initializeTheme();
  localStorage.setItem('dataopedia-theme', 'light');
  window.dispatchEvent(new StorageEvent('storage', {key:'dataopedia-theme',newValue:'light'}));
  expect(document.documentElement.dataset.theme).toBe('light');
  localStorage.clear();
  window.dispatchEvent(new StorageEvent('storage', {key:null}));
  expect(document.documentElement.dataset.theme).toBe('dark');
});
it('keeps the toggle accessible and synchronized without remounting children', () => {
  dispose = initializeTheme();
  render(<ThemeToggle />);
  const toggle = screen.getByRole('button', {name:'Switch to light mode'});
  expect(toggle).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(toggle);
  expect(screen.getByRole('button', {name:'Switch to dark mode'})).toBe(toggle);
  expect(toggle).toHaveAttribute('aria-pressed', 'false');
  act(() => setTheme('dark'));
  expect(toggle).toHaveAttribute('aria-label', 'Switch to light mode');
});
it('continues working when browser storage is unavailable', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
  dispose = initializeTheme();
  expect(() => setTheme('light')).not.toThrow();
  system.dispatchEvent(new Event('change'));
  expect(document.documentElement.dataset.theme).toBe('light');
  vi.restoreAllMocks();
});

it('finishes an active palette transition when a renderer mounts during navigation', () => {
  vi.stubGlobal('matchMedia', () => ({matches:false}));
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.push(callback); return frames.length; });
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  const root = document.documentElement;
  Object.defineProperty(root, 'getAnimations', {configurable:true, value:() => [{playState:'running'}]});
  root.style.setProperty('--color-bg', '#51514C');
  const seen: string[] = [];
  const stop = observeThemeColors(style => seen.push(style.getPropertyValue('--color-bg')));
  try {
    expect(frames).toHaveLength(1);
    root.style.setProperty('--color-bg', '#090907');
    frames[0](16);
    expect(seen[seen.length - 1]).toBe('#090907');
  } finally {
    stop(); root.style.removeProperty('--color-bg');
    Reflect.deleteProperty(root, 'getAnimations');
  }
});
