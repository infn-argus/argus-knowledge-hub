import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, documentsApi } from "../api/client";
import { DocumentDetail } from "../pages/documents/Detail";
import { renderWith } from "../test/render";
import { Route, Routes } from "react-router-dom";

vi.mock("../api/useCurrentWorkspaceId", () => ({ useCurrentWorkspaceId: () => "own" }));

afterEach(() => vi.restoreAllMocks());

const page = (
  <Routes>
    <Route path="/documents/:uid" element={<DocumentDetail />} />
  </Routes>
);

describe("a document link opened in another workspace", () => {
  it("names the reader's workspace that holds it and opens it there", async () => {
    vi.spyOn(documentsApi, "get").mockRejectedValue(new ApiError(404, { detail: "Document not found" }));
    vi.spyOn(documentsApi, "workspace").mockResolvedValue({ workspace_id: "sparc", name: "SPARC" });
    renderWith(page, { path: "/documents/bd42" });
    const link = await screen.findByRole("link", { name: "Open it in SPARC" });
    expect(link.getAttribute("href")).toContain("ws=sparc");
    expect(documentsApi.get).toHaveBeenCalledTimes(1);                  // a 404 is not retried
  });

  it("says not found when none of the reader's workspaces holds it", async () => {
    vi.spyOn(documentsApi, "get").mockRejectedValue(new ApiError(404, { detail: "Document not found" }));
    vi.spyOn(documentsApi, "workspace").mockRejectedValue(new ApiError(404, { detail: "Document not found" }));
    renderWith(page, { path: "/documents/bd42" });
    expect(await screen.findByText(/Document not found, or you may not read it/)).toBeInTheDocument();
  });
});
