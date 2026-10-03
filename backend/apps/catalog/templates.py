"""The starting price list every new business gets (design doc "Pricing engine";
owner decision D-57). Prices are left blank for the owner to fill in, so every
service starts switched off. Swahili names are added when the translations exist
(D-23)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateCategory:
    name_en: str


@dataclass(frozen=True)
class TemplateService:
    code: str
    name_en: str
    category: str  # TemplateCategory.name_en
    pricing_model: str
    unit: str


WASH = TemplateCategory("Wash")
SPECIAL = TemplateCategory("Special items")

CATEGORIES: tuple[TemplateCategory, ...] = (WASH, SPECIAL)

SERVICES: tuple[TemplateService, ...] = (
    TemplateService("wash-fold", "Wash and fold", WASH.name_en, "per_kg", "kg"),
    TemplateService("wash-iron", "Wash and iron", WASH.name_en, "per_kg", "kg"),
    TemplateService("ironing", "Ironing only", SPECIAL.name_en, "per_item", "item"),
    TemplateService("duvet", "Duvets", SPECIAL.name_en, "per_item", "item"),
    TemplateService("blanket", "Blankets", SPECIAL.name_en, "per_item", "item"),
    TemplateService("suit", "Suits", SPECIAL.name_en, "per_item", "item"),
    TemplateService("curtains", "Curtains", SPECIAL.name_en, "per_item", "item"),
    TemplateService("shoes", "Shoes", SPECIAL.name_en, "per_item", "pair"),
)
