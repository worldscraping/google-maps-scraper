import json
import logging
import random
import time
import urllib.parse

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.google.com/search"


def safe_get(obj, *indices, default=None):
    current = obj
    for idx in indices:
        try:
            if current is None:
                return default
            current = current[idx]
        except (IndexError, KeyError, TypeError):
            return default
    return current if current is not None else default


def build_search_url(query, lat, lng, viewport_meters, offset=0, lang="es"):
    params = {
        "tbm": "map",
        "authuser": "0",
        "hl": lang,
        "q": query,
        "pb": (
            f"!1m3!1d{viewport_meters}!2d{lng}!3d{lat}"
            f"!2i1024!3i768!4f13.1"
            f"!7i20!8i{offset}!10b1"
        ),
    }
    return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"


def parse_response(text):
    cleaned = text
    for prefix in [")]}'", ")]}'\n", ")]}\n"]:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse response as JSON (length: %d)", len(text))
        return []

    entries = safe_get(data, 0, 1, default=[])
    if not entries:
        return []

    businesses = []
    for entry in entries:
        inner = safe_get(entry, 14)
        if inner is None:
            continue

        name = safe_get(inner, 11)
        if not name:
            continue

        cid = safe_get(inner, 10)
        place_id = safe_get(inner, 78)
        dedup_key = cid or place_id or name

        # Address
        address = safe_get(inner, 39, default="")
        if not address:
            addr_parts = safe_get(inner, 2, default=[])
            address = ", ".join(addr_parts) if addr_parts else ""

        # Phone
        phone = safe_get(inner, 178, 0, 0, default="")

        # Category
        categories = safe_get(inner, 13, default=[])
        category = categories[0] if categories else ""

        # Rating
        rating = safe_get(inner, 4, 7, default="")

        # Website
        website = safe_get(inner, 7, 0, default="")

        # Opening hours / current status
        opening_hours = safe_get(inner, 203, 1, 4, 0, default="")

        # Coordinates
        lat = safe_get(inner, 9, 2, default="")
        lng = safe_get(inner, 9, 3, default="")

        # Google Maps URL
        if place_id:
            gmaps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        elif cid:
            gmaps_url = f"https://maps.google.com/?cid={cid}"
        else:
            gmaps_url = ""

        businesses.append({
            "name": name,
            "address": address,
            "phone": phone,
            "category": category,
            "rating": rating,
            "review_count": "",
            "google_maps_url": gmaps_url,
            "website": website,
            "opening_hours": opening_hours,
            "latitude": lat,
            "longitude": lng,
            "_dedup_key": dedup_key,
        })

    return businesses


def scrape_cell(proxy, query, lat, lng, viewport_meters, country=None, city=None,
                lang="es", delay_min=2.0, delay_max=5.0, max_pages=10):
    all_results = []
    cell_completed = True
    session_id = proxy.new_session()

    for page in range(max_pages):
        offset = page * 20
        url = build_search_url(query, lat, lng, viewport_meters, offset, lang)

        response = proxy.make_request(
            url, country=country, city=city, session_id=session_id
        )

        if response is None:
            logger.warning(
                "Failed to get response for cell (%.4f, %.4f) page %d",
                lat, lng, page,
            )
            cell_completed = False
            break

        businesses = parse_response(response.text)

        if not businesses:
            logger.debug(
                "No results at cell (%.4f, %.4f) page %d — stopping pagination",
                lat, lng, page,
            )
            break

        all_results.extend(businesses)
        logger.debug(
            "Cell (%.4f, %.4f) page %d: %d results",
            lat, lng, page, len(businesses),
        )

        if len(businesses) < 20:
            break

        time.sleep(random.uniform(delay_min, delay_max))

    return all_results, cell_completed


def deduplicate(businesses, seen_keys):
    unique = []
    for biz in businesses:
        key = biz["_dedup_key"]
        if key and key not in seen_keys:
            seen_keys.add(key)
            unique.append(biz)
    return unique


MAX_CELL_RETRIES = 2


def scrape_grid(proxy, query, grid_cells, seen_keys, country=None, city=None,
                lang="es", delay_min=2.0, delay_max=5.0, completed_cells=None,
                on_cell_done=None, max_results=None, request_counter=None,
                failed_cells_from_checkpoint=None):
    if completed_cells is None:
        completed_cells = set()
    if request_counter is None:
        request_counter = [0]

    all_results = []
    failed_cells = []
    total_cells = len(grid_cells)

    # Restore failed cells from a previous checkpoint
    if failed_cells_from_checkpoint:
        for fc in failed_cells_from_checkpoint:
            cell_id = fc["cell_id"]
            for cell in grid_cells:
                if cell["cell_id"] == cell_id:
                    failed_cells.append((cell, fc.get("retry_count", 0)))
                    break

    # --- Main pass ---
    for cell in grid_cells:
        cell_id = cell["cell_id"]

        if cell_id in completed_cells:
            continue

        if max_results and len(all_results) >= max_results:
            logger.info("Reached max_results (%d), stopping", max_results)
            break

        logger.info(
            "Scraping cell %d/%d (%.4f, %.4f)...",
            cell_id + 1, total_cells, cell["lat"], cell["lng"],
        )

        cell_results, cell_completed = scrape_cell(
            proxy, query, cell["lat"], cell["lng"], cell["viewport_meters"],
            country=country, city=city, lang=lang,
            delay_min=delay_min, delay_max=delay_max,
        )

        new_results = deduplicate(cell_results, seen_keys)
        all_results.extend(new_results)
        completed_cells.add(cell_id)

        if not cell_completed:
            failed_cells.append((cell, 0))

        request_counter[0] += 1

        logger.info(
            "Cell %d/%d done: %d raw, %d new unique (total: %d)%s",
            cell_id + 1, total_cells, len(cell_results),
            len(new_results), len(all_results),
            "" if cell_completed else " [INCOMPLETE - queued for retry]",
        )

        if on_cell_done:
            on_cell_done(cell_id, new_results, failed_cells)

        # Adaptive inter-cell delay
        if proxy.consecutive_failures >= 2:
            pause = random.uniform(30, 60)
            logger.info("Extended pause (proxy struggling): %.1fs", pause)
            time.sleep(pause)
            proxy.health_check(country=country, city=city)
        elif request_counter[0] % 50 == 0:
            pause = random.uniform(20, 45)
            logger.info("Periodic pause: %.1fs", pause)
            time.sleep(pause)
            proxy.rotate_headers()
        else:
            time.sleep(random.uniform(5, 15))

    # --- Retry pass for failed cells ---
    while failed_cells:
        retry_batch = failed_cells
        failed_cells = []

        logger.info("Retrying %d failed cells...", len(retry_batch))
        cooldown = random.uniform(30, 60)
        logger.info("Cooldown before retry pass: %.1fs", cooldown)
        time.sleep(cooldown)
        proxy.health_check(country=country, city=city)

        for cell, retry_count in retry_batch:
            if retry_count >= MAX_CELL_RETRIES:
                logger.warning(
                    "Cell %d abandoned after %d retries",
                    cell["cell_id"] + 1, retry_count,
                )
                continue

            if max_results and len(all_results) >= max_results:
                break

            logger.info(
                "Retry %d/%d for cell %d (%.4f, %.4f)...",
                retry_count + 1, MAX_CELL_RETRIES,
                cell["cell_id"] + 1, cell["lat"], cell["lng"],
            )

            cell_results, cell_completed = scrape_cell(
                proxy, query, cell["lat"], cell["lng"], cell["viewport_meters"],
                country=country, city=city, lang=lang,
                delay_min=delay_min, delay_max=delay_max,
            )

            new_results = deduplicate(cell_results, seen_keys)
            all_results.extend(new_results)

            if not cell_completed:
                failed_cells.append((cell, retry_count + 1))

            logger.info(
                "Retry cell %d: %d raw, %d new unique (total: %d)%s",
                cell["cell_id"] + 1, len(cell_results),
                len(new_results), len(all_results),
                "" if cell_completed else " [still incomplete]",
            )

            if on_cell_done:
                on_cell_done(cell["cell_id"], new_results, failed_cells)

            time.sleep(random.uniform(5, 15))

    return all_results
