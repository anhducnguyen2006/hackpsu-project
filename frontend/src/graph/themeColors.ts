import type { EvidenceNode } from './model';
import { themeColor } from '../theme/theme';

const nodeTokens: Record<EvidenceNode['kind'], string> = {
  research_question: '--color-node-question', dataset: '--color-node-dataset',
  variable: '--color-node-variable', concept: '--color-node-concept',
  domain: '--color-node-domain', geography: '--color-node-variable', time_period: '--color-node-variable',
};
export const nodeColor = (kind: EvidenceNode['kind']) => themeColor(nodeTokens[kind]);
export const edgeColor = (evidence: string) => themeColor(evidence === 'inferred' ? '--color-graph-inferred' : '--color-graph-edge');
