export function EvidenceTag({ label, explanation }: { label: string; explanation: string }) {
  return <span className="evidence-tag" title={explanation} aria-label={`${label}: ${explanation}`}>{label}</span>;
}
