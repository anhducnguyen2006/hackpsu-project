export type NodeKind = 'research_question' | 'dataset' | 'variable' | 'concept' | 'domain' | 'geography' | 'time_period';
export type EvidenceClass = 'search_context' | 'interpretation' | 'documented' | 'metadata_supported' | 'inferred' | 'unverified' | 'computed';
export interface Provenance { origin: 'cached' | 'repository' | 'search' | 'backend' | 'computed'; datasetIds: string[]; sourceRecordUrls: string[]; fieldPaths: string[]; evidenceText: string; backendId?: string }
export interface EvidenceNode { id: string; kind: NodeKind; label: string; datasetId?: string; provenance: Provenance; attributes: Record<string, unknown> }
export interface EvidenceEdge { id: string; source: string; target: string; relationship: string; evidenceClass: EvidenceClass; provenance: Provenance; rawVerificationStatus?: string; rawRelationshipType?: string }
export interface Snapshot { searchGeneration: number; revision: number; nodes: EvidenceNode[]; edges: EvidenceEdge[]; warnings: string[]; mode: 'cached' | 'live' }
export interface EvidencePatch { searchGeneration: number; revision: number; nodes: EvidenceNode[]; edges: EvidenceEdge[]; removedNodeIds: string[]; removedEdgeIds: string[] }
