import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import AppEntry from "./AppEntry";

vi.mock("./landing/WorldCanvas", () => ({
  default: () => <div data-testid="research-world" />,
}));

beforeEach(() => {
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
    matches: query.includes("prefers-reduced-motion"), media: query,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
});

afterEach(() => {
  window.history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("preserves the research preview stages at the root", () => {
  render(<AppEntry />);
  expect(screen.getByText("Static preview · cached UCI example")).toBeVisible();
  const navigation = screen.getByRole("navigation", { name: "Research navigation" });
  const stageNames = ["Question", "Interpretation", "Datasets", "Graph", "Analysis", "Research graph", "Past Research"];
  expect(navigation.children).toHaveLength(stageNames.length);
  for (const name of stageNames) {
    expect(within(navigation).getByRole("button", { name })).toBeVisible();
  }
  expect(screen.queryByTestId("research-world")).not.toBeInTheDocument();
});

it.each(["/landing", "/landing/", "/landing?source=preview"])(
  "opens the isolated, accessible composition at %s without API calls",
  async (path) => {
    window.history.replaceState(null, "", path);
    const request = vi.spyOn(globalThis, "fetch");
    render(<AppEntry />);
    expect(await screen.findByRole("heading", { level: 1, name: "Every question opens a world." })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open research preview" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Research navigation" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("research-world")).not.toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
  },
);

it("keeps the existing preview fallback for other paths", () => {
  window.history.replaceState(null, "", "/landing/not-a-route");
  render(<AppEntry />);
  expect(screen.getByRole("textbox", { name: "Research question" })).toBeVisible();
});

it("loads the scene in standard mode and responds to the device motion preference", async () => {
  let reduced = false;
  const listeners = new Set<() => void>();
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
    get matches() { return query.includes("prefers-reduced-motion") && reduced; },
    media: query,
    addEventListener: (_event: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_event: string, listener: () => void) => listeners.delete(listener),
  })));
  window.history.replaceState(null, "", "/landing");
  const { act } = await import("@testing-library/react");
  const view = render(<AppEntry />);
  expect(await screen.findByTestId("research-world")).toBeInTheDocument();
  act(() => { reduced = true; listeners.forEach((listener) => listener()); });
  expect(screen.queryByTestId("research-world")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Every question opens a world." })).toBeVisible();
  view.unmount();
  expect(listeners.size).toBe(0);
});
