import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { AuthorizedFetch } from "../auth/api";
import { PastResearch } from "./PastResearch";

const authorizedFetch: AuthorizedFetch = (input, init) => {
  const headers = new Headers(init?.headers);
  headers.set("Authorization", "Bearer test-token");
  return fetch(input, { ...init, headers });
};

afterEach(() => vi.restoreAllMocks());

it("loads history and opens persisted session details", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/research/history?limit=100")) {
      return new Response(JSON.stringify([{
        id: 7,
        question: "Does rainfall affect crop yield?",
        normalized_question: "rainfall and crop yield",
        created_at: "2026-01-01T12:00:00Z",
      }]), { status: 200 });
    }
    return new Response(JSON.stringify({
      id: 7,
      question: "Does rainfall affect crop yield?",
      normalized_question: "rainfall and crop yield",
      created_at: "2026-01-01T12:00:00Z",
      datasets: [{
        metadata: { title: "Rainfall observations", source: "UCI", landing_page_url: "https://example.test/dataset" },
        rank: 1,
        relevance_score: 0.91,
        explanation: "Verified metadata match.",
      }],
      assessments: [{
        dataset_id: 12,
        model: "gemini-test",
        assessment_version: "v1",
        assessment: { overall_assessment: "Useful for review", final_score: 82 },
        suitability_score: 82,
      }],
    }), { status: 200 });
  });
  const onSelectQuery = vi.fn();
  render(<PastResearch apiBase="http://localhost:8000" authorizedFetch={authorizedFetch} selectedQueryId={null} onSelectQuery={onSelectQuery} />);

  await userEvent.click(await screen.findByRole("button", { name: /Does rainfall affect crop yield/ }));
  expect(onSelectQuery).toHaveBeenCalledWith(7);
  render(<PastResearch apiBase="http://localhost:8000" authorizedFetch={authorizedFetch} selectedQueryId={7} onSelectQuery={onSelectQuery} />);
  expect(await screen.findByText("Rainfall observations")).toBeVisible();
  expect(screen.getByText("Useful for review")).toBeVisible();
  const sessionCall = fetchMock.mock.calls.find((call) => String(call[0]).endsWith("/session"));
  expect(sessionCall?.[0]).toBe("http://localhost:8000/api/v1/research/7/session");
  expect(new Headers(sessionCall?.[1]?.headers).get("Authorization")).toBe("Bearer test-token");
});

it("does not request history while logged out", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  render(<PastResearch apiBase="http://localhost:8000" selectedQueryId={null} onSelectQuery={vi.fn()} />);
  expect(await screen.findByText("Log in to view your saved research.")).toBeVisible();
  expect(fetchMock).not.toHaveBeenCalled();
});

it("shows an empty state when no history is saved", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify([]), { status: 200 }),
  );
  render(<PastResearch apiBase="http://localhost:8000" authorizedFetch={authorizedFetch} selectedQueryId={null} onSelectQuery={vi.fn()} />);

  expect(await screen.findByText("No saved research yet")).toBeVisible();
});
