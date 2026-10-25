import { lazy, Suspense } from "react";
import App from "./App";

const LandingPage = lazy(() => import("./landing/LandingPage"));

export default function AppEntry() {
  const isLanding = window.location.pathname === "/landing" || window.location.pathname === "/landing/";
  if (!isLanding) return <App />;
  return <Suspense fallback={<main aria-busy="true"><p>Opening DataOPedia…</p><a href="/">Open research preview</a></main>}>
    <LandingPage />
  </Suspense>;
}
