# Data

Source datasets are never destructively modified.

## Tourism catalog

Directory: `data/customized_packages/knowledge/`

| File | Type | Notes |
|---|---|---|
| `poi.json` | POIs | Nested schema, GPS in `location.coordinates` |
| `restaurant.json` | Restaurants | Mostly nested; a few legacy flat records |
| `hotel.json` | Hotels | Some records have null coordinates |

The retriever indexes these files. Raw per-governorate sources may exist in git under `raw/` and must stay usable.

## SME directory

Directory: `data/sme data/`

- `guide/` — tour guides by governorate
- `شركاتتت/` — tour operators by governorate

Operator files may contain concatenated JSON arrays. The loader repairs them in memory and does not rewrite the source files.

SME records have city/region but no native GPS. Map pins use city centroids marked `precision: city_centroid`.

## North, center, and south

Planning geography lives in `app/planning/geo.py` (not a rewrite of the catalog files):

- **North / center** (Amman day-trip belt): Irbid, Ajloun, Jerash, Amman, Madaba, Dead Sea, and nearby governorates
- **South**: Petra, Wadi Rum, Aqaba, Karak, Tafilah, Ma'an

Airport pins: Queen Alia (AMM) and King Hussein (AQJ). The first-night hotel is chosen from listings in that city, preferring GPS closest to the airport.

## Missing information

If a field is absent it stays `unknown` / `not_available`. The Brain does not invent opening hours, prices, or capabilities.
