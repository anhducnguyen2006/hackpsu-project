import type { CSSProperties, ReactElement } from 'react';
export interface DriftWallItem { image: string; title?: string; href?: string }
export interface DriftWallProps {
  items?: DriftWallItem[];
  paused?: boolean;
  columns?: number;
  tileWidth?: number;
  tileHeight?: number;
  gap?: number;
  radius?: number;
  tilt?: number;
  turn?: number;
  roll?: number;
  perspective?: number;
  depth?: number;
  speed?: number;
  direction?: 'up' | 'down';
  variance?: number;
  parallax?: number;
  pauseOnHover?: boolean;
  lift?: number;
  fade?: number;
  dim?: number;
  grayscale?: boolean;
  overlayColor?: string;
  className?: string;
  style?: CSSProperties;
}
export default function DriftWall(props: DriftWallProps): ReactElement;
