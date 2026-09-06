# Nearby Places — keyless, private

"coffee near the ferry building", "nearest pharmacy", "supermarkets around home" — it finds real
places near a point using **OpenStreetMap**, no API key or card. Read-only; it looks things up and
can hand off to the location connector for travel time.

## Security posture
- **Keyless:** Overpass API (nearby search) + Nominatim (geocode the anchor) are free public OSM
  services — no signup, no key, no card.
- **Read-only:** it only looks places up; no bookings, no account actions.
- **Privacy:** the place name you search and the anchor coordinates go to the public OSM servers
  (`overpass-api.de`, `nominatim.openstreetmap.org`). Your **home** coords live only in the VM
  profile — never in the repo.
- **Good-citizen:** Overpass is a shared free service — queries stay small (a bounded radius + a
  single tag filter + a result cap), never a broad unbounded scrape.

## Setup
Keyless — nothing to configure. Optionally tune in the profile:
```yaml
connectors:
  places:
    enabled: true
    radius_m: 1500       # search radius around the anchor
    max_results: 8
```
It uses `connectors.location.home` as the default anchor when you don't name a place.

## The two calls (what the prompt runs)
1. Geocode the anchor to lat/lon (skip if using home coords) — Nominatim, needs a `User-Agent`:
```bash
curl -s -H "User-Agent: hermes-sidekick/1.0" \
  "https://nominatim.openstreetmap.org/search?q=<url-encoded place>&format=json&limit=1"
```
2. Find that kind of place near the anchor — Overpass (`around:<meters>,<lat>,<lon>`):
```bash
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode \
  'data=[out:json][timeout:20];node(around:1500,37.7955,-122.3937)[amenity=cafe];out center 8;'
# -> elements[].tags.name + lat/lon; sort by distance to the anchor
```
Common tags: `amenity=cafe` (coffee), `amenity=pharmacy`, `amenity=restaurant`, `shop=supermarket`,
`amenity=atm`, `amenity=fuel`. Report the closest few (name + rough distance/street); offer
"leave by / how far" via the **location** connector.

## Verify
- "coffee near the Ferry Building in SF" → a few named cafes with rough distances.
- "nearest pharmacy to home" → closest pharmacies using your VM home coords as the anchor.
