import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { assetsApi, catalogueCollectionsApi } from "../api/client";
import type { Asset, SchemaAttribute } from "../api/types";
import { AttributeInput } from "../components/AttributeInput";
import { renderWith } from "../test/render";

afterEach(() => vi.restoreAllMocks());

const model = (uid: string, name: string) => ({ uid, key: uid.toUpperCase(), name, schema_uid: "pm" }) as Asset;
const attribute = { key: "product_model", name: "Product model", type: "reference", referenceType: "Product Model",
                    referenceSchemaUid: "pm" } as SchemaAttribute;

describe("the product model picker", () => {
  it("offers the models of the workspace's domains, and every model on request", async () => {
    vi.spyOn(assetsApi, "list").mockResolvedValue([model("m1", "NPort 5450"), model("m2", "PKR 251"), model("m3", "TPR 270")]);
    vi.spyOn(catalogueCollectionsApi, "offered").mockResolvedValue({ workspace_id: "it", packages: ["it"],
      hidden: ["m2", "m3"], collections: {} });
    renderWith(<AttributeInput attribute={attribute} value="m3" onChange={() => {}} />);

    const more = await screen.findByRole("button", { name: "Show every model (1 more)" });   // m3 is its own value
    const input = screen.getByRole("textbox");
    fireEvent.focus(input);
    await waitFor(() => expect(screen.getByText(/NPort 5450/)).toBeInTheDocument());
    expect(screen.queryByText(/PKR 251/)).not.toBeInTheDocument();
    fireEvent.click(more);
    fireEvent.focus(input);
    await waitFor(() => expect(screen.getByText(/PKR 251/)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Only the models for this workspace's domains" })).toBeInTheDocument();
  });

  it("leaves other references alone", async () => {
    vi.spyOn(assetsApi, "list").mockResolvedValue([model("r1", "Rack 1")]);
    const offered = vi.spyOn(catalogueCollectionsApi, "offered");
    renderWith(<AttributeInput attribute={{ ...attribute, key: "rack", referenceType: "Rack" }} value={null} onChange={() => {}} />);
    fireEvent.focus(await screen.findByRole("textbox"));
    expect(await screen.findByText(/Rack 1/)).toBeInTheDocument();
    expect(offered).not.toHaveBeenCalled();
  });
});
