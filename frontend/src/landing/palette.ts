import type { CSSProperties } from "react";

export const PALETTE = {
  ice: "#DDE3E8",
  aubergine: "#3A0F34",
  marigold: "#EAAA00",
  paper: "#F6F7F6",
} as const;

export const paletteProperties = Object.fromEntries(
  Object.entries(PALETTE).map(([name, color]) => [`--landing-${name}`, color]),
) as CSSProperties;
