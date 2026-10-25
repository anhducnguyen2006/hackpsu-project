import { useAuth0 } from "@auth0/auth0-react";

export function AuthControls() {
  const { isLoading, isAuthenticated, user, error, loginWithRedirect, logout } = useAuth0();

  if (isLoading) return <span className="auth-status">Checking session...</span>;
  if (error) return <span className="auth-status auth-error">Auth error: {error.message}</span>;
  if (isAuthenticated) {
    return <div className="auth-controls"><span className="auth-user">{user?.email}</span><button type="button" className="secondary-action" onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}>Log out</button></div>;
  }
  return <div className="auth-controls"><button type="button" className="secondary-action" onClick={() => loginWithRedirect({ authorizationParams: { screen_hint: "signup" } })}>Sign up</button><button type="button" className="primary-action" onClick={() => loginWithRedirect()}>Log in</button></div>;
}
