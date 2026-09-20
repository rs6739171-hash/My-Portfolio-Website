import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.openweathermap.org/data/2.5"

def get_weather_bundle(city: str) -> str:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not configured.")

    city = (city or "").strip()
    if not city:
        raise ValueError("A destination city is required for weather lookup.")

    current = requests.get(
        f"{BASE_URL}/weather",
        params={"q": city, "appid": api_key, "units": "metric"},
        timeout=20,
    )
    current.raise_for_status()
    current_data = current.json()

    forecast = requests.get(
        f"{BASE_URL}/forecast",
        params={"q": city, "appid": api_key, "units": "metric"},
        timeout=20,
    )
    forecast.raise_for_status()
    forecast_data = forecast.json()

    weather = current_data.get("weather", [{}])[0].get("description", "unknown")
    temp = current_data.get("main", {}).get("temp")
    feels = current_data.get("main", {}).get("feels_like")
    humidity = current_data.get("main", {}).get("humidity")

    points = []
    for item in forecast_data.get("list", [])[:5]:
        description = item.get("weather", [{}])[0].get("description", "unknown")
        points.append(
            f"- {item.get('dt_txt', 'Forecast')}: "
            f"{item.get('main', {}).get('temp', '?')}°C, {description}"
        )

    return (
        f"Current weather for {city}: {temp}°C, feels like {feels}°C, "
        f"{weather}, humidity {humidity}%.\n\n"
        "Near-term forecast:\n" + "\n".join(points)
    )
