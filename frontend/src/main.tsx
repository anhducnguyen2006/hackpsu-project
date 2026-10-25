import { StrictMode, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import AppEntry from "./AppEntry";
import { fetchWithAccessToken, type AuthorizedFetch } from "./auth/api";
import { auth0Audience, auth0ClientId, auth0Domain } from "./auth/config";
import { AuthControls } from "./components/AuthControls";
import "./styles/foundation.css";
import "./styles/landing.css";
import "./styles/workspace.css";
import "./styles/graph.css";
import "./styles/analysis.css";

function AuthenticatedEntry() {
  const { getAccessTokenSilently, isAuthenticated, isLoading } = useAuth0();
  const authorizedFetch = useCallback<AuthorizedFetch>((input, init) => {
    return fetchWithAccessToken(
      () => getAccessTokenSilently({ authorizationParams: { audience: auth0Audience } }),
      input,
      init,
    );
  }, [getAccessTokenSilently]);
  return (
    <AppEntry
      authControls={<AuthControls />}
      authorizedFetch={isAuthenticated && !isLoading ? authorizedFetch : undefined}
    />
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Auth0Provider
      domain={auth0Domain}
      clientId={auth0ClientId}
      authorizationParams={{
        redirect_uri: window.location.origin,
        ...(auth0Audience ? { audience: auth0Audience } : {}),
      }}
    >
      <AuthenticatedEntry />
    </Auth0Provider>
  </StrictMode>,
);
