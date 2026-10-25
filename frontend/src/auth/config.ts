export const auth0Domain =
  import.meta.env.VITE_AUTH0_DOMAIN?.trim() || "dev-cavt8qsoguvw8bjv.us.auth0.com";

export const auth0ClientId =
  import.meta.env.VITE_AUTH0_CLIENT_ID?.trim() || "HAeCwrM0uklvSub6tBLwcPOIsjVNKyAK";

/** Auth0 API identifier. Empty until the Dashboard API is created and copied here. */
export const auth0Audience = import.meta.env.VITE_AUTH0_AUDIENCE?.trim() || "";
