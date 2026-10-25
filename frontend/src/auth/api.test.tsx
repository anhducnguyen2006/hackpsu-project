import { fetchWithAccessToken, type AuthorizedFetch } from "../auth/api";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

it("sends the Auth0 access token as a bearer credential", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
  const getAccessToken = vi.fn(async () => "header.payload.signature");

  await fetchWithAccessToken(
    getAccessToken,
    "http://localhost:8000/api/v1/discovery/search",
    { method: "POST", body: "{}" },
    "https://dataopedia.test/api",
  );

  expect(getAccessToken).toHaveBeenCalledOnce();
  const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
  expect(headers.get("Authorization")).toBe("Bearer header.payload.signature");
});

it("does not request a token when the API audience is not configured", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  const getAccessToken = vi.fn(async () => "header.payload.signature");
  await expect(
    fetchWithAccessToken(getAccessToken, "http://localhost:8000/api/v1/discovery/search", undefined, ""),
  ).rejects.toThrow(/API audience is not configured/);
  expect(getAccessToken).not.toHaveBeenCalled();
  expect(fetchMock).not.toHaveBeenCalled();
});

it("does not call the API when an access token cannot be acquired", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  await expect(
    fetchWithAccessToken(
      async () => {
        throw new Error("Login required");
      },
      "http://localhost:8000/api/v1/research/history",
      undefined,
      "https://dataopedia.test/api",
    ),
  ).rejects.toThrow("Login required");
  expect(fetchMock).not.toHaveBeenCalled();
});

it("keeps a logged-out cached preview free of protected requests", async () => {
  const { default: App } = await import("../App");
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
  const request = vi.spyOn(globalThis, "fetch");
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: "Explore the example" }));
  expect(screen.getByRole("heading", { name: "Interpretation" })).toBeVisible();
  expect(request).not.toHaveBeenCalled();
});

export type { AuthorizedFetch };
