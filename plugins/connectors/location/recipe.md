# Location & Maps — keyless, private

Geocoding + travel time with **no API key** — via public OpenStreetMap services running from
the VM. It powers commute prep ("leave by 2:38 for your 3pm") in the morning brief. Nothing is
brokered by a paid third party; the only data sent out is the address/coords you look up.

## Security posture
- **Keyless:** Nominatim (geocoding) + OSRM (routing) are free public OSM services — no signup,
  no card, no key to store.
- **Read-only:** it only looks things up; no account actions, nothing to write.
- **Privacy:** the address or coordinates in a query go to `nominatim.openstreetmap.org` /
  `router.project-osrm.org`. Your **home** coords live only in the VM profile — never in the repo.
- **Optional upgrade:** set `connectors.location.provider: ors` with a free OpenRouteService key
  (in `~/.hermes/.env`) for higher rate limits / reliability. The keyless path is the default.

## Setup
1. Set your **home** in the profile (VM only) — `connectors.location.home.latitude/longitude`.
   Find your coords by geocoding your address once (step 2), or from any map app.
2. That's it — it's keyless. Verify with the two calls below.

## The two calls (what the prompts run)
Geocode an address → lat/lon (Nominatim needs a `User-Agent`):
```bash
curl -s -H "User-Agent: hermes-sidekick/1.0" \
  "https://nominatim.openstreetmap.org/search?q=<url-encoded address>&format=json&limit=1"
# -> [{ "lat": "...", "lon": "...", "display_name": "..." }]
```
Route home → destination → travel time (OSRM; note lon,lat order):
```bash
curl -s "https://router.project-osrm.org/route/v1/<mode>/<homeLon>,<homeLat>;<dstLon>,<dstLat>?overview=false"
# -> routes[0].duration (seconds), routes[0].distance (meters)
```
"Leave by" = event start − travel time − `buffer_mins`.

## Notes
- Nominatim asks for ≤ ~1 request/second and a real User-Agent — fine for a few daily events.
- Coordinates are `lon,lat` in OSRM URLs (a classic gotcha) but `lat,lon` in Nominatim results.
- Real-time "leave now" alerts (vs the morning heads-up) need an always-on host.
