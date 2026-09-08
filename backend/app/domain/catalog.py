from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

ROME = ZoneInfo("Europe/Rome")
CATEGORIES = dict(
    zip(
        [
            "carne",
            "salumi",
            "pesce",
            "frutta_verdura",
            "latticini_uova",
            "pane_forno",
            "pasta_riso_cereali",
            "dispensa",
            "piatti_pronti",
            "dolci",
            "snack_salati",
            "bevande",
            "casa_pulizia",
            "cura_persona",
            "infanzia",
            "animali",
            "non_alimentare",
            "altri",
        ],
        [
            "Carne e pollame",
            "Salumi",
            "Pesce",
            "Frutta e verdura",
            "Latticini e uova",
            "Pane e forno",
            "Pasta, riso e cereali",
            "Dispensa e condimenti",
            "Piatti pronti e alternative vegetali",
            "Dolci e snack dolci",
            "Snack salati",
            "Bevande",
            "Casa e pulizia",
            "Cura della persona",
            "Infanzia",
            "Animali",
            "Non alimentare",
            "Altri prodotti",
        ],
    )
)


def normalized(value: str) -> str:
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", value.casefold())
            if not unicodedata.combining(c)
        ).split()
    )


def money(text: str | None) -> int | None:
    if text is None:
        return None
    text = unicodedata.normalize("NFKC", text).strip()
    match = re.fullmatch(
        r"(?:€\s*)?((?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})?)(?:\s*€)?", text
    )
    if not match:
        raise ValueError("Prezzo non interpretabile")
    return int(Decimal(match[1].replace(".", "").replace(",", ".")) * 100)


def cents(number) -> int:
    value = Decimal(str(number)) * 100
    if value != value.to_integral() or value <= 0:
        raise ValueError("Prezzo non valido")
    return int(value)


def end_exclusive(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, ROME).astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


def identity(*parts) -> str:
    return hashlib.sha256("|".join(str(x) for x in parts).encode()).hexdigest()[:32]


# Priority exceptions precede exact source mappings. No dietary tags inferred.
RULES = [
    ("baby-food", "infanzia", r"\bomogeneizzat[oi]\b"),
    ("sliced-poultry", "salumi", r"\baffettati\b.*\b(?:pollo|tacchino)\b"),
    ("prepared-pizza", "piatti_pronti", r"\bpizza\b"),
    ("plant-kebab", "piatti_pronti", r"\bkebab\b.*\bvegetale\b"),
    ("stuffed-pasta", "pasta_riso_cereali", r"\b(?:tortellini|tortelloni|ravioli)\b"),
    ("mashed-potatoes", "piatti_pronti", r"\bpure[’']? di patate\b"),
    ("baby-diapers", "infanzia", r"\bpampers baby[ -]?dry\b"),
    ("sliced-turkey", "salumi", r"\barrosto di tacchino\b"),
    ("bacon-speck", "salumi", r"\b(?:bacon|speck|spianata piccante)\b"),
    (
        "sweet-bakery",
        "dolci",
        r"\b(?:pancakes?|wafer|wafers|crostata|ciambelle zuccherate|cannoli|tortina|cookie)\b",
    ),
    ("rusks", "pane_forno", r"\bfette biscottate\b"),
    ("breakfast-grains", "pasta_riso_cereali", r"\b(?:fiocchi di avena|granola)\b"),
    ("pasta-shapes", "pasta_riso_cereali", r"\b(?:orecchiette|trofie|strozzapreti)\b"),
    ("tomato-passata", "dispensa", r"\b(?:passata di pomodoro|sugo pronto|pinoli)\b"),
    ("personal-soap", "cura_persona", r"\bsapone liquido\b"),
    ("cleansing-paste", "cura_persona", r"\bpasta lavamani\b"),
    ("pickled-cabbage", "dispensa", r"\bcrauti\b"),
    ("cooked-sausage", "salumi", r"\bwurstel\b"),
    ("ambiguous-trancino", "altri", r"\btrancino\b"),
    ("savory-bakery", "pane_forno", r"\b(?:focaccia|pagnotta)\b"),
    ("vinegar", "dispensa", r"\baceto\b"),
    ("coconut-milk", "dispensa", r"\blatte di cocco\b"),
    ("pretzel", "snack_salati", r"\bpretzel\b"),
    ("prepared-side", "piatti_pronti", r"\bcontorno di\b"),
    (
        "prepared-meal",
        "piatti_pronti",
        r"\b(?:arancini|mini toast|panzerotti|polpette di maccheroni|burger vegetale)\b",
    ),
    ("pet-food", "animali", r"\b(?:gatti|gatto|cani|cane|lettiera)\b"),
    ("chocolate-egg", "dolci", r"\buov[oa] di cioccolato\b"),
    ("cleansing-milk", "cura_persona", r"\blatte detergente\b"),
    ("plant-burger", "piatti_pronti", r"\bburger vegetal[ei]\b"),
    ("cooked-turkey", "salumi", r"\bpetto di tacchino (?:arrosto|al forno)\b"),
    (
        "cured-meat",
        "salumi",
        r"\b(?:salamini|salame|porchetta|pancetta arrotolata|prosciutto crudo|prosciutto cotto|bresaola)\b",
    ),
]
KEYWORDS = [
    (
        "salumi",
        r"\b(?:salame|prosciutto|bresaola|mortadella|pancetta|wurstel|lonzino)\b",
    ),
    (
        "carne",
        r"\b(?:pollo|tacchino|bovino|scottona|suino|salsiccia|manzo|hamburger)\b",
    ),
    (
        "pesce",
        r"\b(?:pesce|salmone|merluzzo|tonno|gamberi|orata|branzino|vongole|cozze)\b",
    ),
    ("cura_persona", r"\b(?:shampoo|dentifricio|bagnoschiuma|deodorante|crema viso)\b"),
    ("infanzia", r"\b(?:pannolini|omogeneizzato)\b"),
    (
        "casa_pulizia",
        r"\b(?:lavatrice|detersivo|ammorbidente|carta igienica|asciugatutto|swiffer|candeggina)\b",
    ),
    (
        "latticini_uova",
        r"\b(?:latte|uova|uovo|yogurt|formaggio|mozzarella|burro|mascarpone|panna|grana|latticino|fermenti|grattugiato|stracchino|albume)\b",
    ),
    (
        "dolci",
        r"\b(?:biscotti|frollini|cioccolato|cioc|gelato|gelati|torta|croissant|milk snack|crema alla nocciola|merendine)\b",
    ),
    ("snack_salati", r"\b(?:patatine|taralli|cracker|salatini)\b"),
    ("piatti_pronti", r"\b(?:vellutata|zuppa|burger vegetale|lasagne|pizza)\b"),
    (
        "pasta_riso_cereali",
        r"\b(?:pasta|spaghetti|riso|fusilli|penne|cereali|cavatelli|scialatielli)\b",
    ),
    ("pane_forno", r"\b(?:pane|piadina|pinsa|panini)\b"),
    ("bevande", r"\b(?:acqua|birra|vino|cola|limonata|succo|bibita)\b"),
    (
        "dispensa",
        r"\b(?:olio|aceto|maionese|ragu|fagioli|miele|farina|caffe|zucchero|sale|olive|carciofini|polpa di pomodoro|confettura)\b",
    ),
    (
        "frutta_verdura",
        r"\b(?:mele|pere|uva|banane|cipolle|zucchine|carote|insalata|patate|pomodori|peperoni)\b",
    ),
    (
        "non_alimentare",
        r"\b(?:scarpa|scarpe|pigiama|serra|scaffale|ferro da stiro|scala|sgabello|lanterna|pianta artificiale|telo|pensilina|stiratrice|pantaloni|tappeto|calzini)\b",
    ),
]
EXACT = {
    "CARNI": "carne",
    "ORTOFRUTTA": "frutta_verdura",
    "BEVANDE": "bevande",
    "CURA PERSONA": "cura_persona",
    "CURA CASA": "casa_pulizia",
    "PETCARE": "animali",
    "Carne e pollame": "carne",
    "Carne di manzo": "carne",
    "Carne di maiale": "carne",
    "Pesce": "pesce",
    "Frutta": "frutta_verdura",
    "Verdura": "frutta_verdura",
    "Dolci": "dolci",
    "Prodotti per animali": "animali",
}


def classify(title: str, original: str | None = None, description: str = "") -> dict:
    text = normalized(title)
    cat, rule, level = "altri", "fallback", "unclassified"
    for rid, candidate, pattern in RULES:
        if re.search(pattern, text):
            cat, rule, level = candidate, rid, "specific_rule"
            break
    else:
        mapping = next(
            (EXACT[x] for x in reversed((original or "").split("/")) if x in EXACT),
            None,
        )
        if mapping:
            cat, rule, level = mapping, "source-category", "exact_mapping"
        else:
            for candidate, pattern in KEYWORDS:
                if re.search(pattern, text):
                    cat, rule, level = candidate, "keyword-" + candidate, "generic_rule"
                    break
    evidence = normalized(" ".join([title, original or "", description]))
    tags = [
        label
        for word, label in [
            ("surgelat", "Surgelato"),
            ("biologico", "Biologico"),
            ("senza glutine", "Senza glutine"),
            ("senza lattosio", "Senza lattosio"),
            ("vegetale", "Vegetale"),
        ]
        if word in evidence
    ]
    return dict(
        category_id=cat,
        category_rule_id=rule,
        classification_level=level,
        classification_version="5",
        tags=tags,
    )


class Package(BaseModel):
    raw_text: str | None = None
    units_in_pack: int | None = None
    quantity_per_unit: str | None = None
    quantity_unit: Literal["g", "kg", "ml", "l"] | None = None
    total_quantity: str | None = None
    quantity_basis: Literal["net", "drained", "unknown"] = "unknown"


class Price(BaseModel):
    currency: Literal["EUR"] = "EUR"
    advertised_amount_cents: int = Field(gt=0)
    basis: Literal["pack", "kg", "l", "piece", "bundle", "from", "unknown"]
    raw_text: str
    published_unit_price: str | None = None
    calculated_unit_price: str | None = None
    unit_price_basis: Literal["kg", "l"] | None = None
    calculation: str | None = None
    previous_amount_cents: int | None = None


class Conditions(BaseModel):
    status: Literal["complete", "partial", "unknown"] = "unknown"
    loyalty_required: bool | None = None
    app_activation_required: bool | None = None
    minimum_pack_count: int | None = None
    minimum_spend_cents: int | None = None
    minimum_cost_cents: int | None = None
    raw_text: str | None = None


class Validity(BaseModel):
    timezone: Literal["Europe/Rome"] = "Europe/Rome"
    start_at: datetime | None = None
    end_at_exclusive: datetime | None = None
    raw_text: str | None = None
    evidence_level: Literal["explicit_dates", "unknown"] = "unknown"


class Offer(BaseModel):
    id: str
    data_origin: Literal["official_live", "synthetic_fixture"] = "official_live"
    offer_type: Literal[
        "product_offer",
        "product_coupon",
        "basket_coupon",
        "future_voucher",
        "loyalty_benefit",
    ] = "product_offer"
    retailer_id: str
    source_id: str
    source_offer_id: str | None = None
    campaign_id: str
    target_ids: list[str]
    title: str = Field(min_length=1, max_length=500)
    title_normalized: str
    brand: str | None = None
    original_category: str | None = None
    category_id: str
    category_rule_id: str
    classification_level: Literal[
        "exact_mapping", "specific_rule", "generic_rule", "unclassified"
    ]
    classification_version: str
    tags: list[str] = []
    package: Package
    price: Price
    conditions: Conditions
    validity: Validity
    scope: dict
    quality: Literal["publishable", "limited", "quarantined"] = "limited"
    limitations: list[str] = []
    source_url: str
    image_url: None = None
    evidence: dict
    parser_version: str
    first_seen_at: datetime
    last_seen_at: datetime
    last_verified_at: datetime
    published_at: datetime | None = None


def package_and_price(
    raw: str, amount: int, basis: str, raw_price: str, published: str | None = None
):
    pack = Package(raw_text=raw or None)
    # Full match prevents appliance tank sizes and variant ranges becoming net content.
    match = re.fullmatch(
        r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)(?:\s*(?:confezione|sacchetto|vasetto|bottiglia|rete))?",
        raw.strip(),
        re.IGNORECASE,
    )
    price = Price(advertised_amount_cents=amount, basis=basis, raw_text=raw_price)
    if match:
        units = int(match[1] or 1)
        qty = Decimal(match[2].replace(",", "."))
        unit = match[3].lower()
        total = qty * units
        if total > 0:
            pack = Package(
                raw_text=raw,
                units_in_pack=units,
                quantity_per_unit=str(qty),
                quantity_unit=unit,
                total_quantity=str(total),
                quantity_basis="net",
            )
            if basis == "pack":
                total_si = total / (1000 if unit in ["g", "ml"] else 1)
                price.calculated_unit_price = str(
                    (Decimal(amount) / 100 / total_si).quantize(
                        Decimal(".0001"), rounding=ROUND_HALF_UP
                    )
                )
                price.unit_price_basis = "kg" if unit in ["g", "kg"] else "l"
                price.calculation = f"{Decimal(amount) / 100:.2f} € per {raw} → {price.calculated_unit_price} €/{price.unit_price_basis} (calcolato dall’app)"
    if published:
        m = re.fullmatch(
            r"(?:1\s*(kg|l)\s*=\s*)?(\d+[.,]\d+)\s*€(?:/(kg|l))?", published.strip()
        )
        if m and (m[1] or m[3]):
            price.published_unit_price = str(Decimal(m[2].replace(",", ".")))
            price.unit_price_basis = m[1] or m[3]
    if basis in ["kg", "l"]:
        price.published_unit_price = str(Decimal(amount) / 100)
        price.unit_price_basis = basis
    return pack, price


def temporal(offer: dict, now: datetime) -> tuple[str, str]:
    def dt(v):
        return (
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            if isinstance(v, str)
            else v
        )

    start = dt(offer["validity"].get("start_at"))
    end = dt(offer["validity"].get("end_at_exclusive"))
    status = (
        "expired"
        if end and now >= end
        else "future"
        if start and now < start
        else "active"
        if start
        else "unknown"
    )
    age = (now - dt(offer["last_verified_at"])).total_seconds()
    return status, "hidden" if age > 172800 else "stale" if age > 43200 else "fresh"
