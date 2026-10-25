import { act } from "@testing-library/react";
import { setTheme } from "../theme/theme";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { ResearchConnectionsGraph } from "./ResearchConnectionsGraph";

const cytoscapeMock = vi.hoisted(() => vi.fn((_options: unknown) => {
    const stylesheet = { selector: vi.fn().mockReturnThis(), style: vi.fn().mockReturnThis(), update: vi.fn().mockReturnThis() };
    const collection = { removeClass: vi.fn(), addClass: vi.fn() };
    return { style: vi.fn(() => stylesheet), on: vi.fn(), elements: vi.fn(() => collection), $id: vi.fn(() => collection), fit: vi.fn(), resize: vi.fn(), destroy: vi.fn() };
}));

vi.mock("cytoscape", () => ({ default: cytoscapeMock }));

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); cytoscapeMock.mockClear(); });

const graph = {
  nodes: [
    { data: { id: "research:4", research_id: 4, type: "RESEARCH_QUESTION" as const, label: "Rainfall and crop yield", question: "Does rainfall affect crop yield?", created_at: "2026-01-01T12:00:00Z" } },
    { data: { id: "research:8", research_id: 8, type: "RESEARCH_QUESTION" as const, label: "Precipitation and harvests", question: "How does precipitation relate to harvests?", created_at: "2026-01-02T12:00:00Z" } },
  ],
  edges: [
    { data: { id: "research-connection:1", source: "research:4", target: "research:8", relationship_type: "SHARED_DATASET" as const, similarity_score: null, shared_dataset_count: 1, shared_datasets: [{ dataset_id: 12, title: "Rainfall observations", repository: "UCI", external_id: "uci:12" }], evidence: "1 shared discovered dataset(s): Rainfall observations", created_at: "2026-01-03T12:00:00Z" } },
  ],
};

it("fetches the saved graph and opens a selected research session", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(graph), { status: 200 }));
  const onSelectQuery = vi.fn();
  render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={onSelectQuery} />);

  expect(await screen.findByRole("button", { name: "Open saved research 4: Does rainfall affect crop yield?" })).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/research/graph?limit=100", expect.objectContaining({ signal: expect.any(AbortSignal) }));
  await userEvent.click(screen.getByRole("button", { name: "Open saved research 4: Does rainfall affect crop yield?" }));
  expect(onSelectQuery).toHaveBeenCalledWith(4);
});

it("explains a shared-dataset edge from the persisted payload", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(graph), { status: 200 }));
  render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={vi.fn()} />);

  await screen.findByRole("button", { name: "Open saved research 4: Does rainfall affect crop yield?" });
  const edgeButton = screen.getByRole("button", { name: /Shared dataset between Does rainfall affect crop yield\? and How does precipitation relate to harvests\?/ });
  expect(edgeButton).toHaveTextContent("Does rainfall affect crop yield?");
  await userEvent.click(edgeButton);
  expect(screen.getByText("1 shared discovered dataset(s): Rainfall observations")).toBeVisible();
  expect(screen.getByText("Rainfall observations")).toBeVisible();
});

it("offers retry after a graph request fails", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockRejectedValueOnce(new Error("Temporary graph outage"))
    .mockResolvedValueOnce(new Response(JSON.stringify({ nodes: [], edges: [] }), { status: 200 }));
  render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={vi.fn()} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Temporary graph outage");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("heading", { name: "No connected research yet" })).toBeVisible();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("shows a valid empty graph without inventing research", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ nodes: [], edges: [] }), { status: 200 }));
  render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={vi.fn()} />);

  expect(await screen.findByRole("heading", { name: "No connected research yet" })).toBeVisible();
  expect(screen.queryByRole("button", { name: /Open saved research/ })).not.toBeInTheDocument();
});

it("defaults to list mode on a narrow screen", async () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, media: "(max-width: 640px)", onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() })));
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(graph), { status: 200 }));
  render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={vi.fn()} />);

  await screen.findByRole("button", { name: "Open saved research 4: Does rainfall affect crop yield?" });
  expect(screen.getByRole("button", { name: "List" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Canvas" })).toHaveAttribute("aria-pressed", "false");
  expect(document.querySelector(".research-view-list")).toBeInTheDocument();
});

it("resizes and refits Cytoscape when returning to canvas mode", async () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, media: "(max-width: 640px)", onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() })));
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(graph), { status: 200 }));
  render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={vi.fn()} />);

  await screen.findByRole("button", { name: "Open saved research 4: Does rainfall affect crop yield?" });
  const canvas = screen.getByRole("button", { name: "Canvas" });
  await userEvent.click(canvas);
  const instance = cytoscapeMock.mock.results[0]?.value as { resize: ReturnType<typeof vi.fn>; fit: ReturnType<typeof vi.fn> };
  expect(instance.resize).toHaveBeenCalled();
  expect(instance.fit).toHaveBeenCalled();
});

it("synchronizes edge index selection state", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(graph), { status: 200 }));
  render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={vi.fn()} />);

  await screen.findByRole("button", { name: "Open saved research 4: Does rainfall affect crop yield?" });
  const edgeButton = screen.getByRole("button", { name: /Shared dataset between Does rainfall affect crop yield\? and How does precipitation relate to harvests\?/ });
  expect(edgeButton).toHaveAttribute("aria-pressed", "false");
  await userEvent.click(edgeButton);
  expect(edgeButton).toHaveAttribute("aria-pressed", "true");
});

it("uses a compact Cytoscape label for long questions", async () => {
  const longQuestion = "How does long-term exposure to changing environmental conditions affect academic performance across multiple populations and regions?";
  const longGraph = { ...graph, nodes: graph.nodes.map((node, index) => index === 0 ? { data: { ...node.data, question: longQuestion, label: longQuestion } } : node) };
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(longGraph), { status: 200 }));
  render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={vi.fn()} />);

  await screen.findByRole("button", { name: `Open saved research 4: ${longQuestion}` });
  const options = cytoscapeMock.mock.calls[cytoscapeMock.mock.calls.length - 1]?.[0] as { elements: { data: { id: string; display_label?: string } }[] };
  const node = options.elements.find(({ data }) => data.id === "research:4");
  expect(node?.data.display_label).toContain("\n");
  expect(node?.data.display_label?.length).toBeLessThan(longQuestion.length);
});

it("aborts the graph request when the component unmounts", async () => {
  let requestSignal: AbortSignal | undefined;
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    requestSignal = init?.signal ?? undefined;
    return new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError"))));
  });
  const { unmount } = render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={vi.fn()} />);
  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  unmount();
  expect(requestSignal?.aborted).toBe(true);
});

it('updates canvas styles in place on a theme change without refitting or recreating the graph', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(graph), {status:200}));
  vi.stubGlobal('matchMedia', () => ({matches:true}));
  const view=render(<ResearchConnectionsGraph apiBase="http://localhost:8000" onSelectQuery={vi.fn()} />);
  await screen.findByRole('button', {name:'Open saved research 4: Does rainfall affect crop yield?'});
  const cy=cytoscapeMock.mock.results[0].value;
  const updates=cy.style().update.mock.calls.length;
  document.documentElement.dataset.theme='light';
  act(()=>setTheme('dark'));
  expect(cytoscapeMock).toHaveBeenCalledTimes(1);
  expect(cy.style().update.mock.calls.length).toBeGreaterThan(updates);
  expect(cy.destroy).not.toHaveBeenCalled();
  view.unmount();
  document.documentElement.removeAttribute('data-theme');
});
