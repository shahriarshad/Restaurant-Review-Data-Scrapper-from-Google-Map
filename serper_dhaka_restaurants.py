import os
import csv
import time
import math
import json
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv

# -----------------------------
# CONFIG
# -----------------------------

SERPER_MAPS_URL = "https://google.serper.dev/maps"
SERPER_REVIEWS_URL = "https://google.serper.dev/reviews"

# Default request headers (API key injected later)
BASE_HEADERS = {"Content-Type": "application/json"}


# -----------------------------
# HELPERS
# -----------------------------

def get_api_key() -> str:
    """
    Resolve the Serper API key in a safe way.
    Reads from SERPER_API_KEY in .env or environment.
    """
    load_dotenv()
    key = os.getenv("SERPER_API_KEY")
    if not key:
        raise RuntimeError(
            "Serper API key not found. "
            "Set SERPER_API_KEY in your .env or environment."
        )
    return key


def estimate_credits(max_restaurants: int) -> int:
    """
    Very rough credit estimate:
      - ~1 maps call per 20 businesses
      - 1 reviews call per business
    """
    maps_calls = math.ceil(max_restaurants / 20)
    review_calls = max_restaurants
    return maps_calls + review_calls


def safe_get(d: Dict[str, Any], *keys, default: str = "N/A") -> Any:
    """Helper to safely get nested keys with a default."""
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def normalize_text(s: str) -> str:
    return s.strip().lower() if isinstance(s, str) else ""


def place_matches_area(place: Dict[str, Any], area: str, city: str) -> bool:
    """
    Check if the place seems to belong to the requested area & city
    based on the address / title text.
    """
    addr = normalize_text(place.get("address", ""))
    title = normalize_text(place.get("title", ""))

    area_l = normalize_text(area)
    city_l = normalize_text(city)

    in_area = area_l in addr or area_l in title
    in_city = city_l in addr or city_l in title

    return in_area and in_city


def get_int_input(prompt: str, default: Optional[int] = None) -> int:
    """
    Ask user for a positive integer. If they press enter and default is provided,
    returns default.
    """
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            value = int(raw)
            if value > 0:
                return value
            print("Please enter a positive integer.")
        except ValueError:
            print("Please enter a valid integer.")


def get_ll_for_city(city: str) -> Optional[str]:
    """
    Return a Serper-compatible 'll' (GPS) string for a known city.
    Right now we only configure Dhaka since that's your main use case.
    """
    city_l = city.strip().lower()

    if city_l == "dhaka":
        # Center of Dhaka (lat, lon, zoom 13)
        return "@23.8103,90.4125,13z"

    # For unknown cities we return None → only first page will work
    return None


# -----------------------------
# SERPER API CALLS
# -----------------------------

def fetch_places_in_area(
    api_key: str,
    city: str,
    area: str,
    max_places: int,
    max_pages: int = 30,
    sleep_between: float = 0.8,
) -> List[Dict[str, Any]]:
    """
    Use Serper /maps endpoint to fetch places around a given city+area.

    We page until:
      - we reach max_places
      - or we run out of results
      - or we hit max_pages
    """
    headers = {**BASE_HEADERS, "X-API-KEY": api_key}
    all_places: List[Dict[str, Any]] = []
    seen_place_ids = set()

    query = f"restaurants in {area}, {city}"
    ll = get_ll_for_city(city)

    if ll is None:
        print(
            f"[INFO] No GPS (ll) configured for city '{city}'. "
            "Pagination beyond the first page may not be available for this city."
        )

    for page in range(1, max_pages + 1):
        if len(all_places) >= max_places:
            break

        payload = {
            "q": query,
            "hl": "en",
            "page": page
        }
        if ll:
            payload["ll"] = ll  # required for page > 1

        print(f"[MAPS] Page {page} | Already collected: {len(all_places)}")

        try:
            resp = requests.post(
                SERPER_MAPS_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=20,
            )
        except requests.RequestException as e:
            print(f"  !! Network error on /maps page {page}: {e}")
            break

        if resp.status_code != 200:
            print(f"  !! /maps page {page} returned HTTP {resp.status_code}: {resp.text[:200]}")
            # If we hit the 'll required' error for a city without ll, we stop.
            break

        data = resp.json()
        places = data.get("places", [])
        if not places:
            print("  .. No more places; stopping maps pagination.")
            break

        new_count = 0
        for place in places:
            place_id = place.get("placeId") or place.get("cid") or place.get("fid")
            if not place_id:
                continue
            if place_id in seen_place_ids:
                continue

            # Filter by area & city
            if not place_matches_area(place, area, city):
                continue

            seen_place_ids.add(place_id)
            all_places.append(place)
            new_count += 1
            if len(all_places) >= max_places:
                break

        print(f"  .. Added {new_count} new places from this page.")
        time.sleep(sleep_between)

    print(f"[MAPS] Total unique places collected for {area}, {city}: {len(all_places)}")
    return all_places


def get_review_identifier(place: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Build the minimal body for /reviews.
    Prefer 'cid', then 'fid'. If neither present, return None.
    """
    if "cid" in place:
        return {"cid": place["cid"]}
    if "fid" in place:
        return {"fid": place["fid"]}
    if "placeId" in place:
        return {"placeId": place["placeId"]}
    return None


def fetch_reviews_for_place(
    api_key: str,
    place: Dict[str, Any],
    max_reviews: int = 20,
    sleep_between: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Fetch reviews for a single place using Serper /reviews endpoint.
    """
    ident_body = get_review_identifier(place)
    if ident_body is None:
        print("    !! No cid/fid/placeId for this place; skipping reviews.")
        return []

    headers = {**BASE_HEADERS, "X-API-KEY": api_key}
    payload = {
        **ident_body,
        "hl": "en",
        "gl": "bd",
        "num": max_reviews,
        "page": 1,
    }

    try:
        resp = requests.post(
            SERPER_REVIEWS_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=25,
        )
    except requests.RequestException as e:
        print(f"    !! Network error on /reviews: {e}")
        return []

    if resp.status_code != 200:
        print(f"    !! /reviews HTTP {resp.status_code}: {resp.text[:200]}")
        return []

    data = resp.json()
    reviews_raw = data.get("reviews", [])
    cleaned: List[Dict[str, Any]] = []

    for r in reviews_raw[:max_reviews]:
        reviewer_name = (
            r.get("user")
            or r.get("name")
            or r.get("author")
            or safe_get(r, "source", "name", default="N/A")
        )
        rating = r.get("rating", "N/A")
        date = r.get("date") or r.get("time") or "N/A"
        text = r.get("snippet") or r.get("text") or ""
        additional_info_parts = []

        if "likeCount" in r:
            additional_info_parts.append(f"likes={r['likeCount']}")
        if "reviewId" in r:
            additional_info_parts.append(f"id={r['reviewId']}")
        if "source" in r:
            additional_info_parts.append(f"source={r['source']}")

        additional_info = "; ".join(map(str, additional_info_parts)) if additional_info_parts else ""

        cleaned.append(
            {
                "reviewer_name": reviewer_name,
                "rating": rating,
                "date": date,
                "text": text,
                "additional_info": additional_info,
            }
        )

    time.sleep(sleep_between)
    return cleaned


# -----------------------------
# CSV WRITING
# -----------------------------

CSV_HEADERS = [
    "business_name",
    "business_address",
    "business_phone",
    "business_website",
    "business_rating",
    "business_total_reviews",
    "reviewer_name",
    "review_rating",
    "review_date",
    "review_text",
    "review_additional_info",
]


def save_businesses_to_csv(
    businesses: List[Dict[str, Any]],
    output_file: str,
) -> None:
    """
    Flatten businesses + their reviews into a single CSV.
    One row per review, with business data in each row.
    """
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)

        for biz in businesses:
            if not biz.get("reviews"):
                writer.writerow(
                    [
                        biz.get("name", "N/A"),
                        biz.get("address", "N/A"),
                        biz.get("phone", "N/A"),
                        biz.get("website", "N/A"),
                        biz.get("rating", "N/A"),
                        biz.get("total_reviews", "N/A"),
                        "", "", "", "", "",
                    ]
                )
                continue

            for rev in biz["reviews"]:
                writer.writerow(
                    [
                        biz.get("name", "N/A"),
                        biz.get("address", "N/A"),
                        biz.get("phone", "N/A"),
                        biz.get("website", "N/A"),
                        biz.get("rating", "N/A"),
                        biz.get("total_reviews", "N/A"),
                        rev.get("reviewer_name", ""),
                        rev.get("rating", ""),
                        rev.get("date", ""),
                        rev.get("text", ""),
                        rev.get("additional_info", ""),
                    ]
                )


# -----------------------------
# MAIN
# -----------------------------

def main():
    print("========================================")
    print("  Serper Restaurant Review Scraper")
    print("========================================")

    city = input("City name (e.g., Dhaka): ").strip()
    area = input("Area name (e.g., Gulshan): ").strip()

    num_restaurants = get_int_input(
        "Number of restaurants to scrape (e.g., 500): "
    )
    num_reviews = get_int_input(
        "Number of reviews per restaurant (e.g., 10): "
    )

    safe_area = area.strip().replace(" ", "_").lower()
    safe_city = city.strip().replace(" ", "_").lower()
    output_filename = f"{safe_area}_{safe_city}_restaurant_data.csv"

    api_key = get_api_key()

    est_credits = estimate_credits(num_restaurants)
    print("========================================")
    print(f"City               : {city}")
    print(f"Area               : {area}")
    print(f"Max restaurants    : {num_restaurants}")
    print(f"Reviews / restaurant: {num_reviews}")
    print(f"Output file        : {output_filename}")
    print(f"Estimated credits  : ~{est_credits} (rough)")
    print("NOTE: Real usage may be slightly lower or higher depending on how")
    print("      many pages actually return results.")
    print("========================================")

    # --- Fetch places ---
    places = fetch_places_in_area(
        api_key=api_key,
        city=city,
        area=area,
        max_places=num_restaurants,
    )

    businesses: List[Dict[str, Any]] = []
    for idx, place in enumerate(places, start=1):
        name = place.get("title", "N/A")
        print(f"\n[PLACE {idx}/{len(places)}] {name}")

        address = place.get("address", "N/A")
        phone = place.get("phoneNumber", "N/A")
        website = place.get("website", "N/A")
        rating = place.get("rating", "N/A")
        total_reviews = place.get("ratingCount", "N/A")

        reviews = fetch_reviews_for_place(
            api_key=api_key,
            place=place,
            max_reviews=num_reviews,
        )
        print(f"    -> Collected {len(reviews)} reviews")

        businesses.append(
            {
                "name": name,
                "address": address,
                "phone": phone,
                "website": website,
                "rating": rating,
                "total_reviews": total_reviews,
                "reviews": reviews,
            }
        )

    save_businesses_to_csv(businesses, output_filename)
    print("\n========================================")
    print(f"Done. Saved {len(businesses)} businesses to '{output_filename}'.")
    print("Each row = 1 review with business info.")
    print("========================================")


if __name__ == "__main__":
    main()
