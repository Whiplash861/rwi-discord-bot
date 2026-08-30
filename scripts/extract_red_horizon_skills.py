from __future__ import annotations

import argparse
from pathlib import Path
from pprint import pformat
from typing import Any

import pdfplumber  # type: ignore[import-not-found]


def extract_skill_tables(pdf_path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    current_variant: str | None = None
    layout: dict[str, int | list[int]] | None = None
    with pdfplumber.open(pdf_path) as document:
        for page_number, page in enumerate(document.pages, start=1):
            for table in page.extract_tables():
                if not table:
                    continue
                for row in table:
                    clean_row = [_clean(cell) for cell in row]
                    if "Skill Variant" in clean_row:
                        layout = _layout(clean_row)
                        continue
                    if layout is None:
                        continue
                    effects_column = layout["effects"]
                    if not isinstance(effects_column, int) or len(clean_row) <= effects_column:
                        continue
                    variant_cell = _at(clean_row, layout["variant"])
                    if variant_cell.startswith("(Pv") and current_variant is not None:
                        prefix = current_variant if "(Pv" not in current_variant else ""
                        if prefix:
                            combined = f"{prefix} {variant_cell}"
                            partial = records.pop(prefix, None)
                            if partial is not None:
                                partial["display_name"] = combined
                                partial["mode"] = _mode(combined)
                                records[combined] = partial
                            current_variant = combined
                        else:
                            current_variant = variant_cell
                    elif variant_cell:
                        current_variant = variant_cell
                    stat = _at(clean_row, layout["stat"])
                    if current_variant is None:
                        continue
                    record = records.setdefault(
                        current_variant,
                        {
                            "display_name": current_variant,
                            "extraction_method": "pdf_table_text",
                            "mode": _mode(current_variant),
                            "source_pages": [],
                            "stats": [],
                            "overcharge_effects": [],
                        },
                    )
                    effect = _at(clean_row, layout["effects"])
                    if effect and effect not in record["overcharge_effects"]:
                        record["overcharge_effects"].append(effect)
                    if not stat or stat.startswith("Tier "):
                        continue
                    tier_columns = layout["tiers"]
                    if not isinstance(tier_columns, list):
                        raise ValueError("Skill Tier columns are missing from the source table")
                    if page_number not in record["source_pages"]:
                        record["source_pages"].append(page_number)
                    record["stats"].append(
                        {
                            "stat": stat,
                            "base": _at(clean_row, layout["base"]),
                            **{
                                f"skill_tier_{index}": _at(clean_row, column)
                                for index, column in enumerate(tier_columns, start=1)
                            },
                            "overcharge": _at(clean_row, layout["overcharge"]),
                        }
                    )
    _repair_page_breaks(records)
    for record in records.values():
        record["overcharge_effect"] = " ".join(record["overcharge_effects"])
    return records


def render_module(records: dict[str, dict[str, Any]], source_pdf: str) -> str:
    payload = pformat(records, width=100, sort_dicts=True)
    return (
        '"""Generated current Red Horizon Skill tables; do not edit by hand.\n\n'
        f"Source: {source_pdf}\n"
        'Regenerate with scripts/extract_red_horizon_skills.py.\n"""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n"
        f"RED_HORIZON_SKILL_TABLES: dict[str, dict[str, Any]] = {payload}\n"
    )


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _mode(display_name: str) -> str:
    if "(PvP)" in display_name:
        return "pvp"
    if "(PvE)" in display_name:
        return "pve"
    return "current"


def _layout(row: list[str]) -> dict[str, int | list[int]]:
    overcharge = row.index("Overcharge")
    return {
        "variant": row.index("Skill Variant"),
        "stat": row.index("Stats") + 1,
        "base": row.index("Base Stats") + 1,
        "tiers": [index for index, value in enumerate(row) if value == "Skill"],
        "overcharge": overcharge + 1,
        "effects": row.index("Overcharge Effects"),
    }


def _at(row: list[str], index: int | list[int]) -> str:
    if not isinstance(index, int) or index >= len(row):
        return ""
    return row[index]


def _repair_page_breaks(records: dict[str, dict[str, Any]]) -> None:
    """Repair one label split across pages 4-5 in Ubisoft's final source PDF."""

    pve_name = "Pulse (PvE) Jammer / EMP"
    pvp_name = "Pulse (PvP) Jammer / EMP"
    pve = records[pve_name]
    pve["stats"] = pve["stats"][:4]
    records[pvp_name] = {
        "display_name": pvp_name,
        "extraction_method": "pdf_table_text",
        "mode": "pvp",
        "source_pages": [4, 5],
        "stats": [
            _stat("Cooldown / Skill Haste", "45s", overcharge="---"),
            _stat(
                "EMP Effect Duration",
                "4s",
                tiers=("+10%", "+20%", "+30%", "+40%", "+50%", "+60%"),
                overcharge="+100%",
            ),
            _stat(
                "Radius",
                "20m",
                tiers=("+10%", "+20%", "+30%", "+40%", "+50%", "+60%"),
                overcharge="+100%",
            ),
            _stat("Charging Time", "2s", overcharge="---"),
        ],
        "overcharge_effects": ["Overcharge has no functionality in PvP environments."],
    }


def _stat(
    name: str,
    base: str,
    *,
    tiers: tuple[str, str, str, str, str, str] = ("---",) * 6,
    overcharge: str,
) -> dict[str, str]:
    return {
        "stat": name,
        "base": base,
        **{f"skill_tier_{index}": value for index, value in enumerate(tiers, start=1)},
        "overcharge": overcharge,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Ubisoft's final Red Horizon Skill PDF into package data."
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-url", required=True)
    arguments = parser.parse_args()
    records = extract_skill_tables(arguments.pdf)
    if not records:
        raise SystemExit("No Skill records were extracted; the source layout may have changed.")
    arguments.output.write_text(
        render_module(records, arguments.source_url),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
