import type { ReactNode } from "react";
import { lazy, Suspense, useSyncExternalStore } from "react";
import App from "./App";

const LandingPage = lazy(() => import("./landing/LandingPage"));

function subscribeLocation(listener: () => void) {
  window.addEventListener("popstate", listener);
  return () => window.removeEventListener("popstate", listener);
}

const currentPath = () => window.location.pathname;

export default function AppEntry({ authControls }: { authControls?: ReactNode }) {
  const isLanding = useSyncExternalStore(subscribeLocation, currentPath) === "/";
  if (!isLanding) return <App authControls={authControls} />;
  return <Suspense fallback={<main aria-busy="true"><p>Opening DataOPedia…</p><a href="/dashboard">Open research preview</a></main>}>
    <LandingPage authControls={authControls} />
  </Suspense>;
}
