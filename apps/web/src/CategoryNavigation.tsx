import { useState } from "react";
import {
  Apple,
  Beef,
  CakeSlice,
  Fish,
  Milk,
  Package,
  PawPrint,
  Wheat,
  Wine,
  Sparkles,
  Grid2X2,
  ChevronDown,
  Sandwich,
  CookingPot,
  Baby,
  Shirt,
  SprayCan,
} from "lucide-react";

const icons = {
  carne: Beef,
  salumi: Sandwich,
  piatti_pronti: CookingPot,
  infanzia: Baby,
  non_alimentare: Shirt,
  cura_persona: SprayCan,
  pesce: Fish,
  frutta_verdura: Apple,
  latticini_uova: Milk,
  dolci: CakeSlice,
  pane_forno: Wheat,
  pasta_riso_cereali: Wheat,
  animali: PawPrint,
  bevande: Wine,
  casa_pulizia: Sparkles,
};
export function CategoryIcon({ id, size = 18 }: { id: string; size?: number }) {
  const Icon = icons[id as keyof typeof icons] || Package;
  return <Icon size={size} strokeWidth={1.6} aria-hidden="true" />;
}
export const shortCategory = (value: string) =>
  value === "Carne e pollame"
    ? "Carne"
    : value === "Dolci e snack dolci"
      ? "Dolci"
      : value;
export default function CategoryNavigation({
  categories,
  counts,
  selected,
  onChange,
}: {
  categories: { id: string; label: string }[];
  counts: Record<string, number>;
  selected: string[];
  onChange: (value: string[]) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const ordered = [
    ...categories.filter((c) =>
      [
        "carne",
        "salumi",
        "pesce",
        "frutta_verdura",
        "latticini_uova",
        "dolci",
      ].includes(c.id),
    ),
    ...categories.filter(
      (c) =>
        ![
          "carne",
          "salumi",
          "pesce",
          "frutta_verdura",
          "latticini_uova",
          "dolci",
        ].includes(c.id),
    ),
  ];
  return (
    <div className="category-navigation">
      <nav
        id="categorie"
        className={"categories" + (expanded ? " expanded" : "")}
        aria-label="Categorie prodotti"
      >
        <button
          className={!selected.length ? "active" : ""}
          aria-pressed={!selected.length}
          onClick={() => onChange([])}
        >
          <Grid2X2 size={17} aria-hidden="true" />
          Tutti <span>{Object.values(counts).reduce((a, b) => a + b, 0)}</span>
        </button>
        {ordered.map((c) => (
          <button
            key={c.id}
            className={selected.includes(c.id) ? "active" : ""}
            aria-pressed={selected.includes(c.id)}
            onClick={() =>
              onChange(
                selected.includes(c.id)
                  ? selected.filter((id) => id !== c.id)
                  : [...selected, c.id],
              )
            }
          >
            <CategoryIcon id={c.id} />
            {shortCategory(c.label)} <span>{counts[c.id] || 0}</span>
          </button>
        ))}
      </nav>
      <button
        className="all-categories"
        aria-label={expanded ? "Riduci categorie" : "Tutte le categorie"}
        aria-expanded={expanded}
        aria-controls="categorie"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? "Riduci" : "Tutte"}
        <span className="category-extra">
          {expanded ? " categorie" : " le categorie"}
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
    </div>
  );
}
