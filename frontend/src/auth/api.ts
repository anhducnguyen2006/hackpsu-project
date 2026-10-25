import { auth0Audience } from "./config";

export type AuthorizedFetch = (input: string, init?: RequestInit) => Promise<Response>;

type AccessTokenFactory = () => Promise<string | undefined>;

export function protectedRequestError(status: number, fallback: string): string {
  if (status === 401) return "Your session has expired. Log in again to continue.";
  if (status === 403) return "You do not have permission for this action.";
  if (status === 429) return "Too many requests. Wait a moment and try again.";
  if (status === 503) return "The service is temporarily unavailable.";
  return fallback;
}

export async function fetchWithAccessToken(
  getAccessTokenSilently: AccessTokenFactory,
  input: string,
  init?: RequestInit,
  audience: string = auth0Audience,
): Promise<Response> {
  if (!audience) {
    throw new Error(
      "The API audience is not configured. Set VITE_AUTH0_AUDIENCE to the Auth0 API identifier.",
    );
  }
  let accessToken: string | undefined;
  try {
    accessToken = await getAccessTokenSilently();
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : "Sign in again to continue.");
  }
  if (!accessToken || accessToken.split(".").length !== 3) {
    throw new Error("Auth0 did not return an API access token.");
  }
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  return fetch(input, { ...init, headers });
}
