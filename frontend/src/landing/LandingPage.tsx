import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState, useSyncExternalStore, type CSSProperties, type ReactNode } from "react";
import StaticWorldPlate from "./StaticWorldPlate";
import { ThemeToggle } from "../components/ThemeToggle";
import styles from "./LandingPage.module.css";
import EvidenceWall from "./EvidenceWall";
import { LANDING_DURATION } from "./storyTiming";
import ResearchStory from "./ResearchStory";

const WorldCanvas = lazy(() => import("./WorldCanvas"));
const motionQuery = "(prefers-reduced-motion: reduce)";
const motionSnapshot = () => window.matchMedia?.(motionQuery).matches ?? false;
function subscribeMotion(listener: () => void) {
  const query = window.matchMedia?.(motionQuery);
  query?.addEventListener("change", listener);
  return () => query?.removeEventListener("change", listener);
}

class SceneBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onError(); }
  render() { return this.state.failed ? null : this.props.children; }
}

function DirectionIcon() {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false"><path d="M5 19 19 5M5 5h14v14" stroke="currentColor" strokeWidth="1.5" /></svg>;
}

export default function LandingPage({ authControls }: { authControls?: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  const reducedMotion = useSyncExternalStore(subscribeMotion, motionSnapshot, () => true);
  const [ready, setReady] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const onReady = useCallback(() => setReady(true), []);
  const onUnavailable = useCallback(() => { setUnavailable(true); setReady(false); }, []);
  const showCanvas = !reducedMotion && !unavailable;
  useEffect(() => { if (reducedMotion) setReady(false); }, [reducedMotion]);

  const journeyMode = showCanvas ? (ready ? "active" : "loading") : "static";
  const theme = { "--landing-duration": LANDING_DURATION } as CSSProperties;

  return <div ref={root} className={styles.page} style={theme} data-landing-page="arrival" data-journey={journeyMode}>
    <header className={styles.header} data-landing-header data-landing-chrome>
      <a className={styles.wordmark} href="/" aria-label="DataOPedia home">DataOPedia</a>
      <span className={styles.headerNote}>A research instrument</span>
      <a className={styles.headerLink} href="/dashboard">Research preview<DirectionIcon /></a>
      <ThemeToggle />
      {authControls && <div className={styles.authControls}>{authControls}</div>}
    </header>
    <div className={styles.viewport}>
    <a className={styles.skipLink} href="#landing-main">Skip to content</a>
    <div className={styles.world} data-flight-world aria-hidden="true" data-world-state={showCanvas && ready ? "webgl" : "static"}>
      {(!showCanvas || !ready) && <StaticWorldPlate />}
      {showCanvas && <SceneBoundary onError={onUnavailable}>
        <Suspense fallback={null}><WorldCanvas onReady={onReady} onUnavailable={onUnavailable} root={root} journeyReady={ready} /></Suspense>
      </SceneBoundary>}
    </div>

    <main id="landing-main" className={styles.main} tabIndex={-1}>
      <div className={styles.copy} data-flight-copy>
        <h1 className={styles.headline} data-flight-headline>Every question<br /><span>opens a world.</span></h1>
        <div className={styles.revealCopy} data-flight-reveal>
          <h2>A field of possibilities</h2>
          <p>Illustrative connections. A starting point for research.</p>
        </div>
        <div className={styles.introduction}>
          <p data-flight-support>Discover public datasets.<br />See the evidence behind every possibility.</p>
          <a className={styles.primaryLink} href="/dashboard">Open research preview<DirectionIcon /></a>
          <span className={styles.previewNote} data-flight-support>Explore the cached UCI example</span>
        </div>
      </div>
      <div className={styles.referenceAxis} data-flight-annotations aria-hidden="true"><span>y</span><i /><span>x</span></div>
      <div className={styles.sceneNote} data-flight-annotations aria-hidden="true"><span>Fig. 01</span><span>A field of possibilities</span></div>
      <ResearchStory />
      <EvidenceWall />
    </main>

    </div>
  </div>;
}
