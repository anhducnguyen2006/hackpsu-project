import { useState } from "react";
import microscopy from "./assets/hela-cells.jpg";
import satellite from "./assets/lena-delta.jpg";
import styles from "./ResearchStory.module.css";

const panels = [
  { label: "Microscopy", title: "A closer look.", image: microscopy, alt: "Fluorescence microscopy of HeLa cells, showing stained cytoskeletal structures and nuclei.", href: "https://wellcomecollection.org/works/mzz2rjvp", credit: "Kevin Mackenzie / Wellcome · CC BY 4.0" },
  { label: "Earth observation", title: "A wider view.", image: satellite, alt: "Landsat 7 observation of the branching waterways of the Lena Delta.", href: "https://science.nasa.gov/resource/lena-delta-russia/", credit: "Landsat 7 / NASA / USGS · Public domain" },
];

export default function ResearchStory() {
  const [selected, setSelected] = useState<number | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [focused, setFocused] = useState<number | null>(null);
  const active = hovered ?? focused ?? selected;
  return <>
    <section className={styles.panelsScene} data-story-panels aria-label="Scientific ways of seeing">
      <div className={styles.panels} onPointerLeave={() => { setHovered(null); setSelected(null); }}>
        {panels.map((panel, index) => <article key={panel.label} className={styles.panel} data-active={active === index} data-contracted={active !== null && active !== index}
          onPointerEnter={event => { if (event.pointerType === "mouse") setHovered(index); }}
          onPointerDown={event => { if (event.pointerType !== "mouse") { setHovered(null); setFocused(null); } }}
          onFocus={event => { if (event.target.matches(":focus-visible")) setFocused(index); }} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(null); }}>
          <img src={panel.image} alt={panel.alt} decoding="async" />
          <div className={styles.scrim} />
          <button className={styles.select} aria-pressed={active === index} aria-label={`Expand ${panel.label.toLowerCase()} panel`}
            onClick={() => setSelected(selected === index ? null : index)}>
            <span className={styles.label}>{panel.label}</span>
            <span className={styles.panelTitle}>{panel.title}</span>
          </button>
          <a className={styles.arrow} href={panel.href} aria-label={`View ${panel.label.toLowerCase()} image source`}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 19 19 5M5 5h14v14" stroke="currentColor" strokeWidth="1.5" /></svg>
          </a>
          <span className={styles.credit}>{panel.credit}</span>
        </article>)}
      </div>
    </section>
    <section className={styles.statementScene} data-story-statement aria-labelledby="evidence-statement">
      <div className={styles.statement}>
        <span className={styles.label}>Scientific inquiry / Evidence</span>
        <h2 id="evidence-statement" aria-label="Research begins with evidence, not assumptions.">
          {["Research begins", "with evidence,", "not assumptions."].map(line => <span className={styles.line} key={line} aria-hidden="true"><span data-statement-line>{line}</span></span>)}
        </h2>
      </div>
    </section>
  </>;
}
