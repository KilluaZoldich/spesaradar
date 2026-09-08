import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import CategoryNavigation from "./CategoryNavigation";

afterEach(cleanup);
function Navigation() {
  const [selected, setSelected] = useState<string[]>([]);
  return (
    <CategoryNavigation
      categories={[
        { id: "carne", label: "Carne e pollame" },
        { id: "dolci", label: "Dolci e snack dolci" },
        { id: "animali", label: "Animali" },
      ]}
      counts={{ carne: 2, dolci: 3, animali: 1 }}
      selected={selected}
      onChange={setSelected}
    />
  );
}
describe("Navigazione delle categorie", () => {
  it("espande tutte le categorie conservando la selezione multipla e i conteggi", () => {
    render(<Navigation />);
    fireEvent.click(screen.getByRole("button", { name: "Carne 2" }));
    fireEvent.click(screen.getByRole("button", { name: "Dolci 3" }));
    fireEvent.click(screen.getByRole("button", { name: "Tutte le categorie" }));
    expect(
      screen.getByRole("button", { name: "Riduci categorie" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Carne 2" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Dolci 3" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    fireEvent.click(screen.getByRole("button", { name: "Tutti 6" }));
    expect(screen.getByRole("button", { name: "Carne 2" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByRole("button", { name: "Dolci 3" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
