"""Small, strict clients for official macro series mirrored by DBnomics.

DBnomics is used as a transport/cache for the original NBS and BIS datasets.
The series identity is kept in code and every value is validated before it is
allowed into the long-lived D1 archive.
"""

from __future__ import annotations

from io import BytesIO, StringIO
import re
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


DBNOMICS_API = "https://api.db.nomics.world/v22/series"
BIS_SDMX_API = "https://stats.bis.org/api/v2/data/dataflow/BIS"
OWID_GRAPHER = "https://ourworldindata.org/grapher"
NBS_YEARBOOK_2012 = "https://www.stats.gov.cn/sj/ndsj/2012/html"
REQUEST_HEADERS = {"User-Agent": "PushFinance/2.0 (+official macro archive)"}
MCA_STATISTICS_PAGES = (
    "https://www.mca.gov.cn/n156/n2679/index.html",
    "https://www.mca.gov.cn/n156/n2679/index_6934_1.html",
)
# The 2026-Q1 table is an image with no alternative text. These values were
# transcribed once from the linked official table and are only used when OCR is
# unavailable or fails validation. New HTML tables and successful OCR always
# take precedence.
MCA_VERIFIED_IMAGE_VALUES = {
    (2026, 1): {
        "page": "https://www.mca.gov.cn/n156/n2679/c1662004999980010629/content.html",
        "marriages_cumulative": 169.7,
        "divorces_cumulative": 62.2,
    },
}


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


def cumulative_to_period_values(
    frame: pd.DataFrame,
    cumulative_columns: Iterable[str],
) -> pd.DataFrame:
    """Convert official year-to-date observations into un-interpolated periods.

    A missing preceding period is deliberately not guessed. For example, a
    January-February combined release remains a two-month observation instead
    of being split into two fictional months.
    """
    result = frame.copy().sort_values("date").reset_index(drop=True)
    result["period_span"] = pd.NA
    for year, indexes in result.groupby(result["date"].dt.year).groups.items():
        ordered = sorted(indexes, key=lambda index: result.at[index, "date"])
        previous_index = None
        for index in ordered:
            current_period = int(result.at[index, "date"].month)
            previous_period = int(result.at[previous_index, "date"].month) if previous_index is not None else 0
            span = current_period - previous_period
            result.at[index, "period_span"] = span
            for column in cumulative_columns:
                target = column.replace("_cumulative", "_period")
                current = pd.to_numeric(pd.Series([result.at[index, column]]), errors="coerce").iloc[0]
                previous = (
                    pd.to_numeric(pd.Series([result.at[previous_index, column]]), errors="coerce").iloc[0]
                    if previous_index is not None else 0.0
                )
                result.at[index, target] = current - previous if pd.notna(current) and pd.notna(previous) else pd.NA
            previous_index = index
    return result


def _normalized_cells(row) -> list[str]:
    return [
        re.sub(r"\s+", "", "".join(cell.stripped_strings).replace("\xa0", ""))
        for cell in row.find_all(["td", "th"])
    ]


def parse_mca_quarterly_table(payload: bytes | str) -> dict[str, float]:
    """Parse one MCA Excel-HTML quarterly table using labels, not cell offsets."""
    text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
    soup = BeautifulSoup(text, "lxml")
    aliases = {
        "marriages_cumulative": "结婚登记",
        "divorces_cumulative": "离婚登记",
    }
    values: dict[str, float] = {}
    for row in soup.find_all("tr"):
        cells = _normalized_cells(row)
        if not cells:
            continue
        for metric, label in aliases.items():
            if not any(label in cell for cell in cells):
                continue
            for cell in cells[1:]:
                match = re.fullmatch(r"-?\d+(?:\.\d+)?", cell.replace(",", ""))
                if match:
                    values[metric] = float(match.group(0))
                    break
    return values


def parse_mca_ocr_text(text: str) -> dict[str, float]:
    """Extract the two required fields from OCR text with conservative ranges."""
    compact = re.sub(r"[ \t]+", "", str(text or ""))
    values: dict[str, float] = {}
    for metric, pattern in {
        "marriages_cumulative": r"结\s*婚\s*登\s*记[^\n\r\d]{0,20}(\d{1,4}(?:\.\d+)?)",
        "divorces_cumulative": r"离\s*婚\s*登\s*记[^\n\r\d]{0,20}(\d{1,4}(?:\.\d+)?)",
    }.items():
        match = re.search(pattern, compact)
        if match:
            value = float(match.group(1))
            if 0 < value < 5000:
                values[metric] = value
    return values


def _ocr_mca_image(content: bytes) -> dict[str, float]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {}
    image = Image.open(BytesIO(content)).convert("RGB")
    text = pytesseract.image_to_string(image, lang="chi_sim+eng", config="--psm 6")
    return parse_mca_ocr_text(text)


def _mca_quarter_links() -> list[tuple[int, int, str]]:
    found: dict[tuple[int, int], str] = {}
    title_pattern = re.compile(r"(20\d{2})年([1-4])季度民政统计数据")
    for listing_url in MCA_STATISTICS_PAGES:
        response = requests.get(listing_url, headers=REQUEST_HEADERS, timeout=45)
        response.raise_for_status()
        soup = BeautifulSoup(response.content.decode("utf-8", errors="ignore"), "lxml")
        for anchor in soup.find_all("a", href=True):
            title = re.sub(r"\s+", "", anchor.get("title") or "".join(anchor.stripped_strings))
            match = title_pattern.search(title)
            if not match:
                continue
            key = (int(match.group(1)), int(match.group(2)))
            href = re.sub(r"\s+", "", str(anchor.get("href") or ""))
            if href:
                found[key] = urljoin(listing_url, href)
    return [(year, quarter, found[(year, quarter)]) for year, quarter in sorted(found)]


def fetch_mca_quarterly_marriage() -> pd.DataFrame:
    """Fetch official quarterly marriage/divorce registrations from MCA.

    MCA publishes cumulative values. The returned frame contains both the
    official cumulative observation and a derived single-quarter contribution.
    """
    records = []
    for year, quarter, page_url in _mca_quarter_links():
        response = requests.get(page_url, headers=REQUEST_HEADERS, timeout=45)
        response.raise_for_status()
        values = parse_mca_quarterly_table(response.content)
        if len(values) < 2:
            verified = MCA_VERIFIED_IMAGE_VALUES.get((year, quarter), {})
            if verified and verified.get("page") == page_url:
                values = {key: verified[key] for key in ("marriages_cumulative", "divorces_cumulative")}
            else:
                soup = BeautifulSoup(response.content.decode("utf-8", errors="ignore"), "lxml")
                image = next((item for item in soup.find_all("img", src=True) if "/part/" in item["src"]), None)
                if image is not None:
                    image_url = urljoin(page_url, re.sub(r"\s+", "", image["src"]))
                    image_response = requests.get(image_url, headers=REQUEST_HEADERS, timeout=45)
                    image_response.raise_for_status()
                    values = _ocr_mca_image(image_response.content)
        if len(values) < 2:
            continue
        records.append({
            "date": pd.Period(f"{year}Q{quarter}", freq="Q").end_time.normalize(),
            "quarter": quarter,
            "source_url": page_url,
            **values,
        })
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError("MCA quarterly statistics returned no marriage observations")
    frame = cumulative_to_period_values(frame, ["marriages_cumulative", "divorces_cumulative"])
    frame = frame.rename(columns={
        "marriages_period": "marriages_quarter",
        "divorces_period": "divorces_quarter",
    })
    for metric in ("marriages_quarter", "divorces_quarter"):
        previous = frame[["date", "period_span", metric]].copy()
        previous["date"] = previous["date"] + pd.DateOffset(years=1)
        previous = previous.rename(columns={metric: f"_{metric}_prior", "period_span": f"_{metric}_span"})
        frame = frame.merge(previous, on="date", how="left")
        comparable = frame["period_span"].eq(frame.pop(f"_{metric}_span"))
        prior = frame.pop(f"_{metric}_prior").where(comparable)
        frame[f"{metric}_yoy"] = (frame[metric] / prior - 1) * 100
    numeric = frame[["marriages_cumulative", "divorces_cumulative", "marriages_quarter", "divorces_quarter"]]
    if (numeric.dropna() < 0).any().any() or numeric.max().max() > 5000:
        raise ValueError("MCA marriage observations failed cumulative/period plausibility validation")
    return frame.sort_values("date").reset_index(drop=True)
