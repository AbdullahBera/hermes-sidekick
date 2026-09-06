# Weather Anywhere — keyless

"weather in Tokyo?", "is it going to rain in London tomorrow?" — current conditions and a short
forecast for any place, no API key or card. Read-only. It's the reactive counterpart to the morning
brief's weather line (which uses your fixed home coords).

## Security posture
- **Keyless:** open-meteo's geocoding + forecast APIs are free and public — no signup, no key, no card.
- **Read-only:** it only looks up weather; no account actions.
- **Privacy:** the place name and its coordinates go to the public open-meteo servers
  (`geocoding-api.open-meteo.com`, `api.open-meteo.com`). Nothing personal is sent.
- **Units are YOUR choice:** it reports in `connectors.weather.units` — never inferred from the
  place (asking about a °C country doesn't override your imperial setting).

## Setup
Keyless — nothing to configure. Optionally tune in the profile:
```yaml
connectors:
  weather:
    enabled: true
    units: imperial      # imperial (°F, mph) | metric (°C, km/h)
    forecast_days: 3
```

## The two calls (what the prompt runs)
1. Geocode the place name → lat/lon (open-meteo geocoding, keyless, no header needed):
```bash
curl -s "https://geocoding-api.open-meteo.com/v1/search?name=<url-encoded place>&count=1&language=en&format=json"
# -> results[0].latitude / .longitude / .name / .country
```
2. Current conditions + short forecast at those coords (units per the profile):
```bash
curl -s "https://api.open-meteo.com/v1/forecast?latitude=<lat>&longitude=<lon>\
&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m\
&daily=temperature_2m_max,temperature_2m_min,weather_code&forecast_days=3&timezone=auto\
&temperature_unit=fahrenheit&wind_speed_unit=mph"
# metric -> temperature_unit=celsius & wind_speed_unit=kmh
```

## Reading `weather_code` (WMO)
`0` clear · `1–3` mainly clear→overcast · `45/48` fog · `51–57` drizzle · `61–67` rain ·
`71–77` snow · `80–82` rain showers · `85/86` snow showers · `95` thunderstorm · `96/99` thunderstorm w/ hail.

## Verify
- "weather in Tokyo" → current temp + condition + today's high/low, in your units.
- "will it rain in Seattle this weekend?" → a short forecast citing the daily outlook.
