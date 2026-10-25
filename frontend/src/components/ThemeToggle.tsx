import { Moon, Sun } from 'lucide-react';
import { setTheme, useTheme } from '../theme/theme';

export function ThemeToggle() {
  const dark = useTheme() === 'dark';
  const label = `Switch to ${dark ? 'light' : 'dark'} mode`;
  return <button type="button" className="theme-toggle" aria-label={label} title={label}
    aria-pressed={dark} onClick={() => setTheme(dark ? 'light' : 'dark')}>
    {dark ? <Sun size={20} aria-hidden="true" /> : <Moon size={20} aria-hidden="true" />}
  </button>;
}
