import { createContext, useContext, useEffect, useState } from 'react';
import { observeThemeColors } from '../theme/theme';

// Original brand values remain available to deterministic geometry/navigation helpers.
export const PALETTE = {
  ice: '#DDE3E8', aubergine: '#3A0F34', marigold: '#EAAA00', paper: '#F6F7F6',
} as const;
export type LandingPalette = Record<keyof typeof PALETTE, string>;
export const LandingPaletteContext = createContext<LandingPalette>(PALETTE);
export const useLandingPalette = () => useContext(LandingPaletteContext);
function readPalette(style = getComputedStyle(document.documentElement)): LandingPalette {
  return {ice: style.getPropertyValue('--color-bg').trim() || PALETTE.ice,
    aubergine: style.getPropertyValue('--color-heading').trim() || PALETTE.aubergine,
    marigold: style.getPropertyValue('--color-scene-accent').trim() || PALETTE.marigold,
    paper: style.getPropertyValue('--color-surface').trim() || PALETTE.paper};
}
export function useAnimatedLandingPalette() {
  const [palette, setPalette] = useState<LandingPalette>(readPalette);
  useEffect(() => observeThemeColors(style => setPalette(readPalette(style))), []);
  return palette;
}
