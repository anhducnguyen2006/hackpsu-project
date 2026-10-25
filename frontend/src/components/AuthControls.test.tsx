import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { AuthControls } from "./AuthControls";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));

const loginWithRedirect = vi.fn();
const logout = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useAuth0).mockReturnValue({
    isLoading: false, isAuthenticated: false, error: undefined,
    loginWithRedirect, logout,
  } as unknown as ReturnType<typeof useAuth0>);
});

it("returns to the dashboard after logging in", async () => {
  render(<AuthControls />);
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));
  expect(loginWithRedirect).toHaveBeenCalledWith({ appState: { returnTo: "/dashboard" } });
});

it("opens signup and returns to the dashboard", async () => {
  render(<AuthControls />);
  await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
  expect(loginWithRedirect).toHaveBeenCalledWith({
    appState: { returnTo: "/dashboard" },
    authorizationParams: { screen_hint: "signup" },
  });
});

it("shows the signed-in user and logs out to the landing page", async () => {
  vi.mocked(useAuth0).mockReturnValue({
    isLoading: false, isAuthenticated: true, user: { email: "researcher@example.com" }, logout,
  } as unknown as ReturnType<typeof useAuth0>);
  render(<AuthControls />);
  expect(screen.getByText("researcher@example.com")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Log out" }));
  expect(logout).toHaveBeenCalledWith({ logoutParams: { returnTo: window.location.origin } });
});
