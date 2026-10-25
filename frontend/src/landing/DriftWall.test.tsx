import { act, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import DriftWall from './react-bits/DriftWall';

beforeEach(() => {
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
  vi.stubGlobal('requestAnimationFrame', vi.fn(() => 42));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
});
afterEach(() => vi.unstubAllGlobals());

it('stops the animation loop while paused, resumes, and cancels on unmount', () => {
  const items = [{ image: '/evidence.svg', title: 'Dataset discovery', href: 'https://example.org/paper' }];
  const view = render(<DriftWall items={items} paused columns={1} />);
  expect(requestAnimationFrame).not.toHaveBeenCalled();
  view.rerender(<DriftWall items={items} paused={false} columns={1} />);
  expect(requestAnimationFrame).toHaveBeenCalled();
  view.rerender(<DriftWall items={items} paused columns={1} />);
  expect(cancelAnimationFrame).toHaveBeenCalledWith(42);
  view.unmount();
});

it('keeps original source destinations and keyboard lift without repeated tab stops', () => {
  const view = render(<DriftWall items={[{ image: '/evidence.svg', title: 'Dataset discovery', href: 'https://example.org/paper' }]} columns={1} paused />);
  const links = Array.from(view.container.querySelectorAll('a'));
  expect(links.every(link => link.href === 'https://example.org/paper' && link.rel.includes('noopener'))).toBe(true);
  expect(links.filter(link => link.tabIndex === 0)).toHaveLength(1);
  act(() => { fireEvent.focus(links[0]); });
  expect(links[0]).toHaveClass('is-active');
});
