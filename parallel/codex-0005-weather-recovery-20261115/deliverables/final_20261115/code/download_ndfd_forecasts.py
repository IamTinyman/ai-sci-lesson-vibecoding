from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time as day_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT = Path("/root/autodl-tmp/ai-sci")
TASK = PROJECT / "parallel/codex-0005-weather-recovery-20261115"
RAW = PROJECT / "data/raw/ndfd/residual_snow_study"
INDEX = RAW / "s3-index"
CACHE = RAW / "grib2"
RESULTS = TASK / "results/final_20261115"
MANIFEST = RESULTS / "ndfd_forecast_manifest.csv"
BUCKET = "https://noaa-ndfd-pds.s3.amazonaws.com/"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
PRODUCTS = {"temp": "YEUZ88", "qpf": "YIUZ88", "snow": "YSUZ88"}
LOCAL_TZ = ZoneInfo("America/Chicago")


def winter_dates() -> list[date]:
    dates: list[date] = []
    for winter in range(2022, 2026):
        current = date(winter - 1, 12, 1)
        end = date(winter, 3, 31)
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
    return dates


def inspect_sample(sample_dir: Path) -> None:
    import numpy as np
    import xarray as xr

    for product in PRODUCTS:
        path = sample_dir / f"{product}.grib2"
        dataset = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
        variable = next(iter(dataset.data_vars))
        values = np.asarray(dataset[variable].values)
        latitude = np.asarray(dataset.latitude.values)
        longitude = ((np.asarray(dataset.longitude.values) + 180) % 360) - 180
        distance = (latitude - 41.995) ** 2 + (np.cos(np.deg2rad(41.995)) * (longitude + 87.933)) ** 2
        y_index, x_index = np.unravel_index(np.nanargmin(distance), distance.shape)
        summary = {
            "product": product,
            "source_time_utc": str(dataset.time.values),
            "variable": variable,
            "variable_attributes": dataset[variable].attrs,
            "grid_shape": list(values.shape),
            "nearest_grid_point": [float(latitude[y_index, x_index]), float(longitude[y_index, x_index])],
            "forecast_steps": [str(item) for item in dataset.step.values],
            "valid_times_utc": [str(item) for item in dataset.valid_time.values],
            "values_at_ORD_grid": values[..., y_index, x_index].tolist(),
            "field_min": float(np.nanmin(values)),
            "field_max": float(np.nanmax(values)),
        }
        print(json.dumps(summary, ensure_ascii=False, default=str), flush=True)
        dataset.close()


def request_bytes(url: str, attempts: int = 4) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ai-sci-divvy-study/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Request failed after {attempts} attempts: {url}") from last_error


def list_product_objects(issue_date: date, product: str, code: str) -> list[dict[str, str]]:
    cache_path = INDEX / f"{issue_date:%Y%m%d}-{product}-{code}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    prefix = f"wmo/{product}/{issue_date:%Y/%m/%d}/{code}_KWBN_"
    params = urllib.parse.urlencode({"list-type": "2", "prefix": prefix})
    root = ET.fromstring(request_bytes(BUCKET + "?" + params))
    objects = []
    for item in root.findall("s3:Contents", NS):
        objects.append({
            "key": item.findtext("s3:Key", namespaces=NS) or "",
            "size": item.findtext("s3:Size", default="", namespaces=NS),
        })
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(objects, ensure_ascii=False), encoding="utf-8")
    return objects


def choose_products(target_date: date, objects: list[dict[str, str]]) -> list[dict[str, str]]:
    cutoff_local = datetime.combine(target_date - timedelta(days=1), day_time(12, 0), tzinfo=LOCAL_TZ)
    cutoff_utc = cutoff_local.astimezone(timezone.utc)
    chosen: list[dict[str, str]] = []
    for product, code in PRODUCTS.items():
        candidates = []
        for item in objects:
            key = item["key"]
            if f"/{(target_date - timedelta(days=1)):%Y/%m/%d}/" not in key:
                continue
            name = key.rsplit("/", 1)[-1]
            if not name.startswith(code + "_KWBN_"):
                continue
            timestamp = name[-12:]
            try:
                issued = datetime.strptime(timestamp, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if issued <= cutoff_utc:
                candidates.append((issued, item))
        if candidates:
            issued, item = max(candidates, key=lambda pair: pair[0])
            chosen.append({
                "target_date": target_date.isoformat(),
                "product": product,
                "issue_utc": issued.isoformat(),
                "key": item["key"],
                "url": urllib.parse.urljoin(BUCKET, urllib.parse.quote(item["key"])),
                "expected_bytes": item["size"],
            })
        else:
            chosen.append({
                "target_date": target_date.isoformat(),
                "product": product,
                "issue_utc": "",
                "key": "",
                "url": "",
                "expected_bytes": "",
            })
    return chosen


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(entry: dict[str, str]) -> dict[str, str]:
    if not entry["key"]:
        status = "error" if entry.get("listing_error") else "missing"
        return {**entry, "status": status, "bytes": "", "sha256": "", "local_file": ""}
    target = CACHE / entry["target_date"].replace("-", "") / f"{entry['product']}.grib2"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 1000:
        size = target.stat().st_size
    else:
        partial = target.with_suffix(".part")
        partial.unlink(missing_ok=True)
        body = request_bytes(entry["url"])
        partial.write_bytes(body)
        if len(body) < 1000:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"Unexpectedly small forecast object: {entry['url']}")
        partial.replace(target)
        size = len(body)
    return {
        **entry,
        "status": "downloaded_or_cached",
        "bytes": str(size),
        "sha256": sha256_file(target),
        "local_file": str(target),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-date", help="List the selected forecast objects for one target date without downloading")
    parser.add_argument("--inspect-sample", type=Path, help="Inspect the temperature, QPF, and snow GRIB2 files in a sample directory")
    args = parser.parse_args()
    INDEX.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    if args.inspect_sample:
        inspect_sample(args.inspect_sample)
        return
    if args.check_date:
        target_date = date.fromisoformat(args.check_date)
        issue_date = target_date - timedelta(days=1)
        objects = []
        for product, code in PRODUCTS.items():
            objects.extend(list_product_objects(issue_date, product, code))
        print(json.dumps(choose_products(target_date, objects), indent=2, ensure_ascii=False))
        return
    dates = winter_dates()
    selected: list[dict[str, str]] = []
    listing_results: dict[tuple[date, str], list[dict[str, str]]] = {}
    listing_errors: dict[tuple[date, str], str] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(list_product_objects, target - timedelta(days=1), product, code):
                (target - timedelta(days=1), product)
            for target in dates
            for product, code in PRODUCTS.items()
        }
        for index, future in enumerate(as_completed(futures), start=1):
            listing_key = futures[future]
            try:
                listing_results[listing_key] = future.result()
            except Exception as error:
                listing_errors[listing_key] = str(error)
            if index % 75 == 0:
                print(f"Listed {index}/{len(futures)} product-date prefixes", flush=True)

    for target_date in dates:
        issue_date = target_date - timedelta(days=1)
        objects = []
        for product in PRODUCTS:
            listing_key = (issue_date, product)
            objects.extend(listing_results.get(listing_key, []))
        selected.extend(choose_products(target_date, objects))
        for row in selected[-len(PRODUCTS):]:
            error = listing_errors.get((issue_date, row["product"]))
            if error:
                row["listing_error"] = error

    print(f"Selected {sum(bool(row['key']) for row in selected)} of {len(selected)} forecast objects", flush=True)
    results: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(download, entry): entry for entry in selected}
        for index, future in enumerate(as_completed(futures), start=1):
            try:
                results.append(future.result())
            except Exception as error:
                entry = futures[future]
                results.append({**entry, "status": "error", "bytes": "", "sha256": "", "local_file": "", "error": str(error)})
            if index % 50 == 0:
                print(f"Downloaded or checked {index}/{len(futures)} forecast objects", flush=True)

    results.sort(key=lambda row: (row.get("target_date", ""), row.get("product", "")))
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in results for key in row})
    with MANIFEST.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    by_product = {
        product: {
            "rows": sum(row.get("product") == product for row in results),
            "available": sum(row.get("product") == product and row.get("status") == "downloaded_or_cached" for row in results),
            "missing": sum(row.get("product") == product and row.get("status") == "missing" for row in results),
            "errors": sum(row.get("product") == product and row.get("status") == "error" for row in results),
        }
        for product in PRODUCTS
    }
    summary = {"target_dates": len(dates), "products": by_product, "manifest": str(MANIFEST)}
    (RESULTS / "ndfd_forecast_download_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
