import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import RetailerPicker, { oneTargetPerRetailer } from "./RetailerPicker";
import type { Target } from "./types";
const targets = [
  {
    id: "conad-a",
    retailer_id: "conad",
    retailer_name: "Conad",
    enabled: true,
    type: "store",
    label: "Carpi 41012 Via A",
  },
  {
    id: "conad-b",
    retailer_id: "conad",
    retailer_name: "Conad",
    enabled: true,
    type: "store",
    label: "Carpi 41012 Via B",
  },
  {
    id: "lidl",
    retailer_id: "lidl",
    retailer_name: "Lidl",
    enabled: true,
    type: "national",
    label: "Offerte nazionali",
  },
] as Target[];
describe("Scelta per insegna", () => {
  it("mostra un solo Conad e richiede una sede esplicita", () => {
    const change = vi.fn();
    render(
      <RetailerPicker
        targets={targets}
        selected={[]}
        query="41012"
        max={5}
        onChange={change}
      />,
    );
    expect(screen.getAllByText("Conad")).toHaveLength(1);
    expect(screen.getByRole("checkbox", { name: /Lidl/ })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Conad: scegli sede" }));
    expect(change).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "conad-b" },
    });
    expect(change).toHaveBeenCalledWith(["conad-b"]);
  });
  it("cambiare sede sostituisce la precedente preservando le altre insegne", () => {
    const change = vi.fn();
    render(
      <RetailerPicker
        targets={targets}
        selected={["conad-a", "lidl"]}
        query=""
        max={5}
        onChange={change}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Conad: cambia sede" }));
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "conad-b" },
    });
    expect(change).toHaveBeenCalledWith(["lidl", "conad-b"]);
  });
  it("migra le vecchie selezioni ripetute senza inventare una nuova sede", () => {
    expect(
      oneTargetPerRetailer(["conad-b", "conad-a", "lidl"], targets),
    ).toEqual(["conad-b", "lidl"]);
  });
});

it("filtra le sedi interne per CAP e conserva un'eventuale selezione", () => {
  const remote = {
    ...targets[0],
    id: "conad-remote",
    label: "Monza 20900 Via C",
  };
  render(
    <RetailerPicker
      targets={[...targets, remote]}
      selected={[]}
      query="41012"
      max={5}
      onChange={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Conad: scegli sede" }));
  expect(screen.queryByRole("option", { name: /Monza/ })).toBeNull();
  expect(
    screen.getByRole("option", { name: /Carpi 41012 Via B/ }),
  ).toBeVisible();
});
