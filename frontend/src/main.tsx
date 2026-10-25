import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Auth0Provider } from "@auth0/auth0-react";
import { initializeTheme } from "./theme/theme";
import AppEntry from "./AppEntry";
import { AuthControls } from "./components/AuthControls";
import "./styles/foundation.css";
import "./styles/landing.css";
import "./styles/workspace.css";
import "./styles/graph.css";
import "./styles/analysis.css";

initializeTheme();
document.documentElement.style.removeProperty("background-color");
document.documentElement.style.removeProperty("color-scheme");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Auth0Provider
      domain="dev-cavt8qsoguvw8bjv.us.auth0.com"
      clientId="HAeCwrM0uklvSub6tBLwcPOIsjVNKyAK"
      authorizationParams={{ redirect_uri: window.location.origin }}
      onRedirectCallback={() => {
        window.history.replaceState(null, "", "/dashboard");
        window.dispatchEvent(new PopStateEvent("popstate"));
      }}
    >
      <AppEntry authControls={<AuthControls />} />
    </Auth0Provider>
  </StrictMode>,
);
