import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
<<<<<<< HEAD
import AppEntry from "./AppEntry";
=======
import { Auth0Provider } from "@auth0/auth0-react";
import App from "./App";
import { AuthControls } from "./components/AuthControls";
>>>>>>> origin/main
import "./styles/foundation.css";
import "./styles/landing.css";
import "./styles/workspace.css";
import "./styles/graph.css";
import "./styles/analysis.css";

<<<<<<< HEAD
createRoot(document.getElementById("root")!).render(<StrictMode><AppEntry /></StrictMode>);
=======
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Auth0Provider
      domain="dev-cavt8qsoguvw8bjv.us.auth0.com"
      clientId="HAeCwrM0uklvSub6tBLwcPOIsjVNKyAK"
      authorizationParams={{ redirect_uri: window.location.origin }}
    >
      <App authControls={<AuthControls />} />
    </Auth0Provider>
  </StrictMode>,
);
>>>>>>> origin/main
