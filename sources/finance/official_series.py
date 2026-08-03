"""Small, strict clients for official macro series mirrored by DBnomics.

DBnomics is used as a transport/cache for the original NBS and BIS datasets.
The series identity is kept in code and every value is validated before it is
allowed into the long-lived D1 archive.
"""

from __future__ import annotations

from io import StringIO
import re
from typing import Iterable

import pandas as pd
import requests
from bs4 import BeautifulSoup


DBNOMICS_API = "https://api.db.nomics.world/v22/series"
BIS_SDMX_API = "https://stats.bis.org/api/v2/data/dataflow/BIS"
OWID_GRAPHER = "https://ourworldindata.org/grapher"
NBS_YEARBOOK_2012 = "https://www.stats.gov.cn/sj/ndsj/2012/html"
REQUEST_HEADERS = {"User-Agent": "PushFinance/2.0 (+official macro archive)"}


def period_end(value: str) -> pd.Timestamp:
    """Convert DBnomics annual/monthly/quarterly labels to period-end dates."""
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}", text):
        return pd.Timestamp(f"{text}-12-31")
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return pd.Timestamp(f"{text}-01") + pd.offsets.MonthEnd(0)
    match = re.fullmatch(r"(\d{4})-?Q([1-4])", text, flags=re.I)
    if match:
        return pd.Period(f"{match.group(1)}Q{match.group(2)}", freq="Q").end_time.normalize()
    return pd.NaT


def fetch_dbnomics_dataset(provider: str, dataset: str, codes: Iterable[str]) -> pd.DataFrame:
    """Fetch selected series without silently accepting renamed/missing fields."""
    requested = set(codes)
    url = f"{DBNOMICS_API}/{provider}/{dataset}"
    response = requests.get(url, params={"observations": 1, "limit": 1000}, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    docs = ((response.json().get("series") or {}).get("docs") or [])
    frames = []
    found = set()
    for doc in docs:
        code = str(doc.get("series_code") or "")
        if code not in requested:
            continue
        periods = doc.get("period") or []
        values = doc.get("value") or []
        frame = pd.DataFrame({
            "date": [period_end(period) for period in periods],
            code: pd.to_numeric(pd.Series(values), errors="coerce"),
        }).dropna(subset=["date"])
        frames.append(frame)
        found.add(code)
    missing = requested - found
    # Large datasets such as BIS/WS_TC contain more than one API page. Fetch
    # an exact series instead of assuming the desired code is in page one.
    for code in sorted(missing):
        exact = requests.get(f"{url}/{code}", params={"observations": 1},
                             headers=REQUEST_HEADERS, timeout=30)
        exact.raise_for_status()
        exact_docs = ((exact.json().get("series") or {}).get("docs") or [])
        if not exact_docs:
            continue
        doc = exact_docs[0]
        frame = pd.DataFrame({
            "date": [period_end(period) for period in (doc.get("period") or [])],
            code: pd.to_numeric(pd.Series(doc.get("value") or []), errors="coerce"),
        }).dropna(subset=["date"])
        frames.append(frame)
        found.add(code)
    missing = requested - found
    if missing:
        raise ValueError(f"DBnomics {provider}/{dataset} missing expected series: {sorted(missing)}")
    if not frames:
        raise ValueError(f"DBnomics {provider}/{dataset} returned no observations")
    result = frames[0]
    for frame in frames[1:]:
        result = result.merge(frame, on="date", how="outer")
    return result.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def parse_bis_sdmx_csv(payload: str) -> pd.DataFrame:
    """Parse a BIS SDMX CSV response without assuming column order."""
    frame = pd.read_csv(StringIO(payload))
    required = {"TIME_PERIOD", "OBS_VALUE"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"BIS SDMX response missing fields: {sorted(missing)}")
    result = pd.DataFrame({
        "date": [period_end(period) for period in frame["TIME_PERIOD"]],
        "value": pd.to_numeric(frame["OBS_VALUE"], errors="coerce"),
    }).dropna(subset=["date", "value"])
    if result.empty:
        raise ValueError("BIS SDMX response returned no usable observations")
    return result.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def fetch_bis_sdmx_series(dataset: str, version: str, key: str) -> pd.DataFrame:
    """Fetch one exact series from the official BIS SDMX v2 API."""
    url = f"{BIS_SDMX_API}/{dataset}/{version}/{key}"
    response = requests.get(url, params={"format": "csv"}, headers=REQUEST_HEADERS, timeout=45)
    response.raise_for_status()
    return parse_bis_sdmx_csv(response.text)


def fetch_owid_grapher(slug: str, country_code: str = "CHN") -> pd.DataFrame:
    """Fetch a documented OWID Grapher CSV and retain one country only."""
    response = requests.get(f"{OWID_GRAPHER}/{slug}.csv", headers=REQUEST_HEADERS, timeout=60)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text))
    required = {"Code", "Year"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"OWID {slug} response missing fields: {sorted(missing)}")
    result = frame.loc[frame["Code"].eq(country_code)].copy()
    if result.empty:
        raise ValueError(f"OWID {slug} returned no rows for {country_code}")
    result["date"] = pd.to_datetime(result["Year"].astype("Int64").astype(str) + "-12-31", errors="coerce")
    return result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def fetch_nbs_yearbook_rows(table: str) -> list[list[float]]:
    """Read a stable NBS yearbook HTML table and return numeric rows only."""
    url = f"{NBS_YEARBOOK_2012}/{table}.HTM"
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    text = response.content.decode("gb18030", errors="ignore")
    soup = BeautifulSoup(text, "lxml")
    rows: list[list[float]] = []
    for tr in soup.select("tr"):
        cells = [" ".join(cell.stripped_strings).replace(",", "") for cell in tr.find_all(["td", "th"])]
        cells = [cell for cell in cells if cell]
        if not cells:
            continue
        try:
            numeric = [float(cell) for cell in cells]
        except ValueError:
            continue
        rows.append(numeric)
    return rows


def merge_official_frames(*frames: pd.DataFrame) -> pd.DataFrame:
    usable = [frame for frame in frames if frame is not None and not frame.empty]
    if not usable:
        return pd.DataFrame()
    return (
        pd.concat(usable, ignore_index=True, sort=False)
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )
