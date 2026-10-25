import { PALETTE } from "./palette";

/** Distance since a direction change, rather than single-event delta, filters scroll jitter. */
export function createNavigationDirection(initial: number, threshold = 12) {
  let last = initial;
  let anchor = initial;
  let sign = 0;
  let hidden = false;
  return {
    reset(position: number) { last = anchor = position; sign = 0; hidden = false; },
    update(position: number): "show" | "hide" | null {
      const y = Math.max(0, position);
      if (y <= 4) { last = anchor = y; sign = 0; hidden = false; return "show"; }
      const nextSign = Math.sign(y - last);
      if (!nextSign) return null;
      if (nextSign !== sign) { anchor = last; sign = nextSign; }
      last = y;
      if (Math.abs(y - anchor) < threshold) return null;
      if (sign > 0 && !hidden) { hidden = true; return "hide"; }
      if (sign < 0 && hidden) { hidden = false; return "show"; }
      return null;
    },
  };
}

const rgb = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
function luminance(channels: number[]) {
  const linear = channels.map(v => { const c = v / 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); });
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}
const ice = rgb(PALETTE.ice), dark = rgb(PALETTE.aubergine);
const darkL = luminance(dark), lightL = luminance(rgb(PALETTE.paper));
export function chromeInk(darkness: number) {
  const mix = Math.max(0, Math.min(1, darkness));
  const backgroundL = luminance(ice.map((v, i) => v + (dark[i] - v) * mix));
  const darkContrast = (backgroundL + 0.05) / (darkL + 0.05);
  const paperContrast = (lightL + 0.05) / (backgroundL + 0.05);
  return darkContrast >= paperContrast ? PALETTE.aubergine : PALETTE.paper;
}
