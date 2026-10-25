import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { AuthorizedFetch } from "../auth/api";
import { RelatedResearch } from "./RelatedResearch";

const authorizedFetch: AuthorizedFetch = (input, init) => {
  const headers = new Headers(init?.headers);
  headers.set("Authorization", "Bearer test-token");
  return fetch(input, { ...init, headers });
};

afterEach(() => vi.restoreAllMocks());

it("fetches related research and opens a selected saved question", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([{
    id: 3,
    question: "How does irrigation affect yield?",
    normalized_question: "irrigation and yield",
    created_at: "2026-01-01T12:00:00Z",
    similarity_score: 0.87,
  }]), { status: 200 }));
  const onOpenResearch = vi.fn();
  render(<RelatedResearch apiBase="http://localhost:8000" authorizedFetch={authorizedFetch} question="Does rainfall affect crop yield?" onOpenResearch={onOpenResearch} />);

  await userEvent.click(screen.getByRole("button", { name: "Find related work" }));
  expect(await screen.findByText("How does irrigation affect yield?")).toBeVisible();
  expect(screen.getByText(/87\.0%/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /How does irrigation affect yield/ }));
  expect(onOpenResearch).toHaveBeenCalledWith(3);
});

it("shows an empty state when the semantic endpoint returns no matches", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
  render(<RelatedResearch apiBase="http://localhost:8000" authorizedFetch={authorizedFetch} question="Does rainfall affect crop yield?" onOpenResearch={vi.fn()} />);

  await userEvent.click(screen.getByRole("button", { name: "Find related work" }));
  expect(await screen.findByText("No saved research is semantically related to this question.")).toBeVisible();
});

it("does not search saved research while logged out", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  render(<RelatedResearch apiBase="http://localhost:8000" question="Does rainfall affect crop yield?" onOpenResearch={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Find related work" }));
  expect(screen.getByText("Log in to compare this question with your saved research.")).toBeVisible();
  expect(fetchMock).not.toHaveBeenCalled();
});
