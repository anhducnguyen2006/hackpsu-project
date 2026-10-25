import type { Dispatch } from 'react';
import type { Snapshot } from './model';
import type { FilterKey, GraphSession, SessionAction } from './graphSession';

function counts(values: string[]) {
  const result = new Map<string, number>();
  values.forEach(value => result.set(value, (result.get(value) ?? 0) + 1));
  return [...result].sort(([a], [b]) => a.localeCompare(b));
}

export function GraphFilters({ snapshot, session, dispatch }: {
  snapshot: Snapshot; session: GraphSession; dispatch: Dispatch<SessionAction>;
}) {
  const groups: { key: FilterKey; label: string; options: [string, number][]; secondary?: boolean }[] = [
    { key: 'nodeType', label: 'Node type', options: counts(snapshot.nodes.map(n => n.kind)) },
    { key: 'evidence', label: 'Evidence class', options: counts(snapshot.edges.map(e => e.evidenceClass)) },
    { key: 'repository', label: 'Repository', secondary: true, options: counts(snapshot.nodes.filter(n => n.kind === 'dataset' && n.attributes.source).map(n => String(n.attributes.source))) },
    { key: 'relationship', label: 'Relationship', secondary: true, options: counts(snapshot.edges.map(e => e.relationship)) },
  ];
  const active = groups.some(g => session[g.key] !== null);
  return <details className="graph-filters graph-panel" onToggle={event => {
    if (event.currentTarget.open) event.currentTarget.querySelector('.graph-filter-body')?.scrollTo?.(0, 0);
  }}>
    <summary>Filters{active && <span className="graph-filter-active"> · active</span>}</summary>
    <div className="graph-filter-body">
      <p className="graph-footnote">Counts show all loaded evidence. Hidden evidence remains available in the evidence list.</p>
      {groups.filter(g => g.options.length > 0).map(group => {
        const fields = <fieldset><legend>{group.label}</legend>{group.options.map(([value, count]) => <label key={value}>
          <input type="checkbox" checked={session[group.key] === null || session[group.key]!.includes(value)} onChange={e => {
            const selected = session[group.key] ?? group.options.map(([v]) => v);
            const next = e.target.checked ? [...selected, value] : selected.filter(v => v !== value);
            dispatch({ type: 'filter', key: group.key, value: group.options.every(([v]) => next.includes(v)) ? null : next });
          }} />
          <span>{value.replace(/_/g, ' ')}</span><span className="graph-filter-count">({count})</span>
        </label>)}</fieldset>;
        return group.secondary ? <details key={group.key} className="graph-filter-secondary"><summary>{group.label}</summary>{fields}</details> : <div key={group.key}>{fields}</div>;
      })}
      <button onClick={() => dispatch({ type: 'resetFilters' })}>Reset filters</button>
    </div>
  </details>;
}
