import argparse
import csv
import hashlib
import json
import logging
import os
import signal
import sys
import time

from proxy import MagneticProxy
from geo import geocode_city, generate_grid
from scraper import scrape_grid

CSV_FIELDS = [
    "name", "address", "phone", "category", "rating",
    "review_count", "google_maps_url", "website", "opening_hours",
]

# Graceful shutdown flag
_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    _shutdown = True
    print("\nShutdown requested — saving checkpoint and exiting...")


def get_checkpoint_path(query, city):
    key = f"{query}:{city}"
    h = hashlib.md5(key.encode()).hexdigest()[:10]
    return f"checkpoint_{h}.json"


def load_checkpoint(path):
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_checkpoint(path, query, city, completed_cells, seen_keys, results_count,
                    failed_cells=None):
    data = {
        "query": query,
        "city": city,
        "completed_cells": sorted(completed_cells),
        "seen_keys": sorted(seen_keys),
        "results_count": results_count,
        "failed_cells": failed_cells or [],
    }
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def append_to_csv(output_path, results, write_header=False):
    mode = "w" if write_header else "a"
    with open(output_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(results)


def infer_country_code(city_display_name):
    country_map = {
        "colombia": "co", "argentina": "ar", "mexico": "mx", "méxico": "mx",
        "chile": "cl", "peru": "pe", "perú": "pe", "ecuador": "ec",
        "venezuela": "ve", "bolivia": "bo", "uruguay": "uy", "paraguay": "py",
        "brazil": "br", "brasil": "br", "españa": "es", "spain": "es",
        "united states": "us", "estados unidos": "us",
    }
    name_lower = city_display_name.lower()
    for country, code in country_map.items():
        if country in name_lower:
            return code
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Google Maps business scraper via MagneticProxy"
    )
    parser.add_argument("--query", required=True, help="Search query (e.g., 'dentistas')")
    parser.add_argument("--city", required=True, help="City for bounding box (e.g., 'Bogota, Colombia')")
    parser.add_argument("--output", default=None, help="Output CSV path (default: results_{timestamp}.csv)")
    parser.add_argument("--cell-size", type=float, default=2.0, help="Grid cell size in km (default: 2.0)")
    parser.add_argument("--max-results", type=int, default=None, help="Stop after N results")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--delay-min", type=float, default=2.0, help="Min delay between requests (seconds)")
    parser.add_argument("--delay-max", type=float, default=5.0, help="Max delay between requests (seconds)")
    parser.add_argument("--lang", default="es", help="Language for results (default: es)")
    parser.add_argument("--proxy-country", default=None, help="Proxy exit country (default: auto-detect)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Output path
    if args.output:
        output_path = args.output
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = f"results_{ts}.csv"

    # Init proxy
    logging.info("Initializing MagneticProxy...")
    proxy = MagneticProxy()

    # Geocode city
    logging.info("Geocoding '%s'...", args.city)
    geo = geocode_city(args.city)
    logging.info("City: %s", geo["display_name"])
    logging.info("Center: %.4f, %.4f", geo["lat"], geo["lon"])

    # Determine proxy country
    country = args.proxy_country or infer_country_code(geo["display_name"])
    if country:
        logging.info("Proxy exit country: %s", country)

    # Generate grid
    grid_cells = generate_grid(geo["bbox"], args.cell_size)
    logging.info("Grid: %d cells", len(grid_cells))

    # Warmup: verify proxy connectivity before starting
    proxy.warmup(country=country)

    # Checkpoint
    checkpoint_path = get_checkpoint_path(args.query, args.city)
    completed_cells = set()
    seen_keys = set()
    total_results = 0
    failed_cells_from_checkpoint = []

    if args.resume:
        cp = load_checkpoint(checkpoint_path)
        if cp:
            completed_cells = set(cp["completed_cells"])
            seen_keys = set(cp["seen_keys"])
            total_results = cp["results_count"]
            failed_cells_from_checkpoint = cp.get("failed_cells", [])
            logging.info(
                "Resumed: %d cells done, %d results, %d dedup keys, %d failed cells pending",
                len(completed_cells), total_results, len(seen_keys),
                len(failed_cells_from_checkpoint),
            )
        else:
            logging.info("No checkpoint found, starting fresh")

    # Write CSV header if starting fresh
    if not args.resume or total_results == 0:
        append_to_csv(output_path, [], write_header=True)

    # Build the search query
    search_query = f"{args.query} en {args.city.split(',')[0].strip()}"

    # Callback: save after each cell
    def on_cell_done(cell_id, new_results, current_failed_cells=None):
        nonlocal total_results
        if new_results:
            append_to_csv(output_path, new_results)
            total_results += len(new_results)
        failed_for_checkpoint = [
            {"cell_id": c["cell_id"], "retry_count": rc}
            for c, rc in (current_failed_cells or [])
        ]
        save_checkpoint(
            checkpoint_path, args.query, args.city,
            completed_cells, seen_keys, total_results,
            failed_cells=failed_for_checkpoint,
        )
        if _shutdown:
            logging.info("Checkpoint saved. Exiting gracefully.")
            sys.exit(0)

    # Scrape
    start_time = time.time()
    logging.info("Saving results to: %s", os.path.abspath(output_path))
    logging.info("Starting scrape: '%s'", search_query)

    results = scrape_grid(
        proxy=proxy,
        query=search_query,
        grid_cells=grid_cells,
        seen_keys=seen_keys,
        country=country,
        lang=args.lang,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        completed_cells=completed_cells,
        on_cell_done=on_cell_done,
        max_results=args.max_results,
        failed_cells_from_checkpoint=failed_cells_from_checkpoint,
    )

    elapsed = time.time() - start_time
    logging.info("Done! %d unique results in %.1f seconds", total_results, elapsed)
    logging.info("Output: %s", output_path)

    # Clean up checkpoint on successful completion
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
        logging.info("Checkpoint removed (run completed)")


if __name__ == "__main__":
    main()
