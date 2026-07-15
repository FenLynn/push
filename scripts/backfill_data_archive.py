"""Backfill canonical Finance/Estate series without plotting or sending."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_archive import DataArchive
from sources.estate.source import EstateSource
from sources.finance.archive_catalog import ARCHIVE_CATALOG
from sources.finance.indicators import (
    BondIndicator,
    CPIIndicator,
    ForexIndicator,
    GDPIndicator,
    LPRIndicator,
    M2Indicator,
    PMIIndicator,
    PPIIndicator,
    RealEstateIndicator,
    ShiborIndicator,
)


FINANCE_COLLECTORS = (
    CPIIndicator,
    PPIIndicator,
    PMIIndicator,
    GDPIndicator,
    M2Indicator,
    LPRIndicator,
    ShiborIndicator,
    BondIndicator,
    ForexIndicator,
    RealEstateIndicator,
)


def backfill_finance(archive: DataArchive, only=None) -> None:
    for collector_type in FINANCE_COLLECTORS:
        collector = collector_type(None, None)
        name = collector.name
        if only and name not in only:
            continue
        spec = ARCHIVE_CATALOG[name]
        try:
            frame = collector.fetch_data()
            count = archive.store_dataframe(
                domain="finance",
                group_name=name,
                frame=frame,
                metrics=spec["metrics"],
                label=spec["label"],
                source=spec["source"],
                frequency=spec["frequency"],
                quality="official",
            )
            print(f"finance/{name}: {count} observations")
        except Exception as exc:
            logging.exception("finance/%s backfill failed: %s", name, exc)
            archive.record_run("finance", name, "failed", 0, str(exc))


def backfill_estate(archive: DataArchive) -> None:
    source = EstateSource()
    source.archive = archive
    frame = source._fetch_price_index_history()
    items = source._archive_price_index(frame)
    print(f"estate/city_price_index: {len(frame)} source rows, {len(items)} latest values")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=("finance", "estate", "all"), default="all")
    parser.add_argument("--only", help="comma-separated Finance collector names")
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    archive = DataArchive()
    if not archive.ensure_schema():
        print("D1 archive is not configured", file=sys.stderr)
        return 1
    only = {item.strip() for item in str(args.only or "").split(",") if item.strip()}
    if args.domain in {"finance", "all"}:
        backfill_finance(archive, only or None)
    if args.domain in {"estate", "all"}:
        backfill_estate(archive)
    archive.run_retention()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
