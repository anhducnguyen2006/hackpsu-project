import { useThemeColor } from "../theme/theme";
import { useEffect, useRef, useState } from 'react';
import DriftWall from './react-bits/DriftWall';
import { RESEARCH_EVIDENCE } from './researchEvidence';
import styles from './EvidenceWall.module.css';

const images = import.meta.glob<string>('./assets/evidence/*.svg', { eager: true, query: '?url', import: 'default' });
const items = RESEARCH_EVIDENCE.map(source => ({
  image: images[`./assets/evidence/${source.id}.svg`],
  title: `${source.headline} ${source.summary} — ${source.source}. Editorial summary; verified ${source.verifiedOn}. Opens original source in a new tab.`,
  href: source.url,
}));

export default function EvidenceWall() {
  const overlayColor = useThemeColor("--color-cinema-bg");
  const section = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);
  const [paused, setPaused] = useState(false);
  const [small, setSmall] = useState(() => window.matchMedia?.('(max-width: 759px)').matches ?? false);

  useEffect(() => {
    const node = section.current;
    if (!node) return;
    const page = node.closest<HTMLElement>('[data-journey]');
    let intersecting = typeof IntersectionObserver === 'undefined';
    const update = () => setVisible(intersecting && !document.hidden && getComputedStyle(node).visibility !== 'hidden');
    const intersection = typeof IntersectionObserver !== 'undefined' ? new IntersectionObserver(([entry]) => {
      intersecting = entry.isIntersecting;
      update();
    }, { threshold: 0 }) : null;
    intersection?.observe(node);
    // A fixed scene can intersect while GSAP hides it. Observe only the outer scene,
    // never DriftWall's constantly changing internal transforms.
    const mutation = new MutationObserver(update);
    mutation.observe(node, { attributes: true, attributeFilter: ['style'] });
    if (page) mutation.observe(page, { attributes: true, attributeFilter: ['data-journey'] });
    document.addEventListener('visibilitychange', update);
    const media = window.matchMedia?.('(max-width: 759px)');
    const resize = () => setSmall(media?.matches ?? false);
    media?.addEventListener('change', resize);
    update();
    return () => {
      intersection?.disconnect();
      mutation.disconnect();
      document.removeEventListener('visibilitychange', update);
      media?.removeEventListener('change', resize);
    };
  }, []);

  return <section ref={section} className={styles.scene} data-evidence-scene aria-labelledby="evidence-title">
    <div className={styles.wall}>
      <DriftWall items={items} columns={small ? 3 : 5} tileWidth={small ? 220 : 260}
        tileHeight={small ? 144 : 170} gap={18} tilt={16} turn={-14} perspective={1200}
        depth={120} speed={42} direction="up" variance={0.45} parallax={0.6}
        lift={64} fade={0.6} dim={0.75} overlayColor={overlayColor} paused={!visible || paused} />
    </div>
    <div className={styles.editorial}>
      <h2 id="evidence-title">Finding the right data shouldn't be the hardest part of research.</h2>
      <p>Across disciplines, researchers face scattered sources, incomplete metadata, and hours of preparation before analysis can even begin.</p>
      <a className={styles.action} href="/dashboard">Explore research preview <span aria-hidden="true">↗</span></a>
    </div>
    <div className={styles.tools}>
      <button type="button" className={styles.pause} onClick={() => setPaused(value => !value)} aria-pressed={paused}>
        {paused ? 'Resume wall' : 'Pause wall'}
      </button>
      <details className={styles.sources}>
        <summary>Read all 18 sources</summary>
        <div className={styles.sourceList}>
          <p>Designed editorial summaries, not platform screenshots. Verified 25 October 2026. Community posts describe individual experiences.</p>
          <ul>{RESEARCH_EVIDENCE.map(source => <li key={source.id}>
            <a href={source.url} target="_blank" rel="noopener noreferrer">{source.headline}<span>{source.source} ↗</span></a>
          </li>)}</ul>
        </div>
      </details>
    </div>
  </section>;
}
