"""Import prices from a CSV file (A-31; M2 T07).

Flow: CSV template -> preview with changes highlighted -> apply as new price
versions from a chosen time.

- **Columns:** service, category, pricing_model, price, and optionally minimum and
  unit. Header names are forgiving ("Pricing model", "Minimum charge").
- **Matching:** a row's service matches an existing one by code, or by name if that
  name is unique. Unmatched services (and their categories) are created, switched
  off: an import never puts something on sale unseen. They're switched on in the
  catalogue (A-30).
- **Each row is:** new, changed (old -> new price), unchanged, or invalid with the
  reason. Prices are digits with an optional point and at most 2 decimals. A comma
  is refused ("1,200" could mean 1200 or 1.2), and so is anything else that isn't a
  plain amount.
- **An existing service keeps its pricing model and unit** (T04); a row that differs
  is invalid. It also keeps its category: the file's category is used only for new
  services.
- **Apply** needs the preview's fingerprint. If the catalogue changed meanwhile, the
  fingerprint no longer matches and nothing is applied. It is all or nothing.
- **Limits:** 1 MB and 1,000 rows. Excel's byte-order mark and semicolon-separated
  files are handled.
"""

import csv
import hashlib
import io
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from django.db import transaction
from django.utils.text import slugify

from apps.catalog import selectors, services
from apps.catalog.models import Service, ServiceCategory
from apps.core import audit

MAX_BYTES = 1_000_000
MAX_ROWS = 1000
REQUIRED = ("service", "category", "pricing_model", "price")
OPTIONAL = ("minimum", "unit")
TEMPLATE_HEADER = ("service", "category", "pricing_model", "price", "minimum", "unit")
HEADER_ALIASES = {
    "pricing model": "pricing_model",
    "model": "pricing_model",
    "minimum charge": "minimum",
    "minimum_charge": "minimum",
    "min": "minimum",
}
MODELS = {
    "per_kg": "per_kg",
    "per kg": "per_kg",
    "per_item": "per_item",
    "per item": "per_item",
    "flat": "flat",
}
AMOUNT = re.compile(r"^\d{1,10}(\.\d{1,2})?$")

Status = Literal["new", "changed", "unchanged", "invalid"]


class CatalogImportError(Exception):
    """The file as a whole can't be imported. ``detail`` adds facts for the message."""

    def __init__(self, code: str, **detail: Any) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class ImportRow:
    line: int  # line number in the file, counting the header as 1
    service: str
    category: str
    pricing_model: str
    unit: str
    price: str  # as typed, so invalid rows can show what was there
    minimum: str
    status: Status = "invalid"
    problem: str = ""  # a code, for invalid rows
    service_id: str | None = None  # the existing service, if matched
    new_code: str | None = None  # the code a new service will get
    new_category: bool = False
    old_price: str | None = None
    old_minimum: str | None = None


@dataclass
class Preview:
    rows: list[ImportRow]
    fingerprint: str
    counts: dict[str, int] = field(default_factory=dict)


# --- Reading the file --------------------------------------------------------------------


def _header_key(name: str) -> str:
    key = " ".join(name.strip().lower().replace("_", " ").split())
    return HEADER_ALIASES.get(key, key.replace(" ", "_"))


def read_rows(text: str) -> list[dict[str, Any]]:
    """The file's rows as dictionaries keyed by the normalised header names."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise CatalogImportError("too_big", max_bytes=MAX_BYTES)
    text = text.lstrip("﻿")  # Excel's byte-order mark
    if not text.strip():
        raise CatalogImportError("empty")
    first_line = text.splitlines()[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = [_header_key(name) for name in next(reader)]
        missing = [name for name in REQUIRED if name not in header]
        if missing:
            raise CatalogImportError("missing_columns", columns=missing)
        rows: list[dict[str, Any]] = []
        for number, values in enumerate(reader, start=2):
            if not any(value.strip() for value in values):
                continue  # blank lines
            if len(rows) >= MAX_ROWS:
                raise CatalogImportError("too_many_rows", max_rows=MAX_ROWS)
            row: dict[str, Any] = {
                name: (values[i].strip() if i < len(values) else "")
                for i, name in enumerate(header)
            }
            row["_line"] = number
            rows.append(row)
    except csv.Error as exc:
        raise CatalogImportError("unreadable") from exc
    if not rows:
        raise CatalogImportError("empty")
    return rows


# --- Preview -------------------------------------------------------------------------------


def _amount(text: str, *, allow_zero: bool) -> Decimal | str:
    """The amount, or the problem code."""
    if "," in text:
        return "amount_has_comma"
    if not AMOUNT.fullmatch(text):
        return "bad_amount"
    value = Decimal(text)
    if value == 0 and not allow_zero:
        return "bad_amount"
    return value


class _Catalogue:
    """The business's catalogue as the preview sees it."""

    def __init__(self) -> None:
        self.services: list[Service] = list(Service.objects.select_related("category"))
        self.by_code: dict[str, Service] = {s.code: s for s in self.services}
        names: dict[str, list[Service]] = {}
        for service in self.services:
            names.setdefault(service.name_en.casefold(), []).append(service)
        self.by_name = names
        self.categories = {c.name_en.casefold() for c in ServiceCategory.objects.all()}
        self.codes = set(self.by_code)

    def match(self, text: str) -> Service | Literal["ambiguous"] | None:
        if text in self.by_code:
            return self.by_code[text]
        found = self.by_name.get(text.casefold(), [])
        if len(found) > 1:
            return "ambiguous"
        return found[0] if found else None

    def new_code(self, name: str) -> str:
        base = slugify(name)[:28].strip("-") or "service"
        code, n = base, 2
        while code in self.codes:
            code, n = f"{base}-{n}", n + 1
        self.codes.add(code)
        return code


def _check_row(raw: dict[str, Any], catalogue: _Catalogue, seen: set[str]) -> ImportRow:
    row = ImportRow(
        line=int(raw["_line"]),
        service=raw.get("service", ""),
        category=raw.get("category", ""),
        pricing_model=raw.get("pricing_model", ""),
        unit=raw.get("unit", "").lower(),
        price=raw.get("price", ""),
        minimum=raw.get("minimum", ""),
    )
    if not row.service:
        row.problem = "service_required"
        return row
    key = row.service.casefold()
    if key in seen:
        row.problem = "duplicate_row"
        return row
    seen.add(key)

    model = MODELS.get(" ".join(row.pricing_model.lower().replace("_", " ").split()))
    if model is None:
        row.problem = "bad_pricing_model"
        return row
    row.pricing_model = model

    price = _amount(row.price, allow_zero=False)
    if isinstance(price, str):
        row.problem = f"price_{price}"
        return row
    minimum = _amount(row.minimum or "0", allow_zero=True)
    if isinstance(minimum, str):
        row.problem = f"minimum_{minimum}"
        return row
    if minimum and model != Service.PricingModel.PER_KG:
        row.problem = "minimum_per_kg_only"
        return row

    match = catalogue.match(row.service)
    if match == "ambiguous":
        row.problem = "ambiguous_service"
        return row
    if match is not None:
        if match.pricing_model != model:
            row.problem = "pricing_model_differs"
            return row
        if row.unit and row.unit != match.unit:
            row.problem = "unit_differs"
            return row
        row.unit = match.unit
        row.service_id = str(match.pk)
        row.category = match.category.name_en
        current = selectors.price_at(match.pk)
        if current is not None:
            row.old_price, row.old_minimum = str(current.unit_price), str(current.minimum_charge)
            same = (current.unit_price, current.minimum_charge) == (price, minimum)
            row.status = "unchanged" if same else "changed"
        else:
            row.status = "changed"
        row.price, row.minimum = f"{price:.2f}", f"{minimum:.2f}"
        return row

    # A new service.
    unit = row.unit or ("kg" if model == Service.PricingModel.PER_KG else "item")
    if (model == Service.PricingModel.PER_KG) != (unit == Service.Unit.KG) or (
        unit not in Service.Unit.values
    ):
        row.problem = "unit_mismatch"
        return row
    if not row.category:
        row.problem = "category_required"
        return row
    row.unit = unit
    row.new_code = catalogue.new_code(row.service)
    row.new_category = row.category.casefold() not in catalogue.categories
    row.price, row.minimum = f"{price:.2f}", f"{minimum:.2f}"
    row.status = "new"
    return row


def _fingerprint(rows: Iterable[ImportRow]) -> str:
    # Covers what the file says and what the catalogue held (matched services, old
    # prices, new codes): if either changes, the fingerprint changes.
    payload = json.dumps([asdict(row) for row in rows], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def preview(text: str) -> Preview:
    raw_rows = read_rows(text)
    catalogue = _Catalogue()
    seen: set[str] = set()
    rows = [_check_row(raw, catalogue, seen) for raw in raw_rows]
    counts = {
        status: sum(1 for r in rows if r.status == status)
        for status in ("new", "changed", "unchanged", "invalid")
    }
    return Preview(rows=rows, fingerprint=_fingerprint(rows), counts=counts)


# --- Apply ---------------------------------------------------------------------------------


def apply(
    text: str,
    *,
    fingerprint: str,
    effective_from: datetime | None = None,
    actor: Any = None,
    request: Any = None,
) -> Preview:
    """Apply a previewed file: new services and categories, and new price versions for
    new and changed rows, all in one transaction."""
    checked = preview(text)
    if checked.fingerprint != fingerprint:
        raise CatalogImportError("changed_since_preview")
    if checked.counts["invalid"]:
        raise CatalogImportError("has_invalid_rows", count=checked.counts["invalid"])

    with transaction.atomic():
        categories = {c.name_en.casefold(): c for c in ServiceCategory.objects.all()}
        for row in checked.rows:
            if row.status == "unchanged":
                continue
            if row.status == "new":
                category = categories.get(row.category.casefold())
                if category is None:
                    category = services.create_category(
                        name_en=row.category, actor=actor, request=request
                    )
                    categories[row.category.casefold()] = category
                service = services.create_service(
                    category=category,
                    code=row.new_code or "",
                    name_en=row.service,
                    pricing_model=row.pricing_model,
                    unit=row.unit,
                    actor=actor,
                    request=request,
                )
            else:
                service = Service.objects.get(pk=row.service_id)
            services.set_price(
                service,
                unit_price=Decimal(row.price),
                minimum_charge=Decimal(row.minimum),
                effective_from=effective_from,
                actor=actor,
                request=request,
            )
        audit.record(
            "catalog.import.apply",
            object_type="catalog.serviceprice",
            after={
                **checked.counts,
                "effective_from": effective_from.isoformat() if effective_from else None,
            },
            actor=actor,
            request=request,
        )
    return checked


# --- The template ----------------------------------------------------------------------------


def template_csv() -> str:
    """The template: the header and the business's current services and prices, ready to
    edit and import again. A service whose name isn't unique is written by its code."""
    catalogue = _Catalogue()
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(TEMPLATE_HEADER)
    for service in catalogue.services:
        unique = len(catalogue.by_name.get(service.name_en.casefold(), [])) == 1
        current = selectors.price_at(service.pk)
        writer.writerow(
            [
                service.name_en if unique else service.code,
                service.category.name_en,
                service.pricing_model,
                f"{current.unit_price:.2f}" if current else "",
                f"{current.minimum_charge:.2f}" if current and current.minimum_charge else "",
                service.unit,
            ]
        )
    return out.getvalue()
