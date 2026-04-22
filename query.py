import openmeteo_requests

import pandas as pd
import requests_cache
from retry_requests import retry
from matplotlib import pyplot as plt
from matplotlib import dates as mdates
import numpy as np
from math import radians, sin, cos

locations = [
    {"latitude": 44.87, "longitude": -93.76, "name": "Waconia"},
    {"latitude": 45.09, "longitude": -92.99, "name": "White_Bear_Lake"},
    {"latitude": 46.36, "longitude": -93.59, "name": "Mille_Lacs_Reddy"},
    {"latitude": 45.07, "longitude": -94.35, "name": "Lake_Washington"},
    {"latitude": 45.01, "longitude": -93.43, "name": "Medicine_Lake"},
    {"latitude": 44.49, "longitude": -92.29, "name": "Lake_Pepin"},
    {"latitude": 44.51, "longitude": -92.96, "name": "Byllesby"},
    {"latitude": 44.27, "longitude": -93.35, "name": "Cannon"},
    {"latitude": 43.13, "longitude": -93.40, "name": "Clear_Lake_IA"},
    {"latitude": 43.48, "longitude": -95.10, "name": "Spirit_Lake_IA"},
    
]
consecutive_hours = 2
min_wind = 13
max_rain = 0.01
min_temp = 50
forecast_days = 4

def is_rideable(wind, precip, is_day, temp, min_wind, max_rain, min_temp):
    if wind >= min_wind and precip <= max_rain and temp >= min_temp and is_day:
        return True
    else:
        return False

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)


# f"{location['latitude']}, {location['longitude']} ({location['name']}),\n"

with open("README.md","w") as f:  
    print(f"Text recommendations will contain rideable periods in the upcoming {forecast_days}."
        "'Rideable' means\n"
        f"at least {consecutive_hours} consecutive daytime hours with:\n"
        f"-- At least {min_wind}kts sustained wind\n"
        f"-- At least {min_temp}F air temp\n"
        f"-- At most {max_rain}in precipitation\n", file=f)
    
    for location in locations:
        # Make sure all required weather variables are listed here
        # The order of variables in hourly or daily is important to assign them correctly below
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "models": "gfs_seamless",
            "hourly": [
                "temperature_2m",
                "wind_gusts_10m",
                "wind_direction_10m",
                "wind_speed_10m",
                "is_day",
                "precipitation",
            ],
            "timezone": "auto",
            "forecast_days": forecast_days,
            "wind_speed_unit": "kn",
            "precipitation_unit": "inch",
            "temperature_unit": "fahrenheit",
            "daily": ["sunrise", "sunset"],
        }
        responses = openmeteo.weather_api(url, params=params)

        # Process first location. Add a for-loop for multiple locations or weather models
        response = responses[0]

        # Process hourly data. The order of variables needs to be the same as requested.
        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
        hourly_wind_gusts_10m = hourly.Variables(1).ValuesAsNumpy()
        hourly_wind_direction_10m = hourly.Variables(2).ValuesAsNumpy()
        hourly_wind_speed_10m = hourly.Variables(3).ValuesAsNumpy()
        hourly_is_day = hourly.Variables(4).ValuesAsNumpy()
        hourly_precipitation = hourly.Variables(5).ValuesAsNumpy()

        hourly_u_10m = []
        hourly_v_10m = []
        for speed, dir in zip(hourly_wind_speed_10m, hourly_wind_direction_10m):
            hourly_u_10m.append(-speed * cos(radians(90 - dir)))
            hourly_v_10m.append(-speed * sin(radians(90 - dir)))

        hourly_date = pd.date_range(
            start=pd.to_datetime(
                hourly.Time() + response.UtcOffsetSeconds(), unit="s", utc=True
            ),
            end=pd.to_datetime(
                hourly.TimeEnd() + response.UtcOffsetSeconds(), unit="s", utc=True
            ),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left",
        )

        # Process daily data. The order of variables needs to be the same as requested.
        daily = response.Daily()
        daily_sunrise = daily.Variables(0).ValuesInt64AsNumpy()
        daily_sunset = daily.Variables(1).ValuesInt64AsNumpy()

        # Look for windy periods
        windy_periods = []
        windy_period_start = None
        windy_hours = 0  # I don't feel like figuring out how to subtract dates
        for date, wind, precip, is_day, temp in zip(hourly_date, hourly_wind_speed_10m, hourly_precipitation, hourly_is_day, hourly_temperature_2m):
            if is_rideable(wind, precip, is_day, temp, min_wind, max_rain, min_temp):
                if windy_period_start is None:
                    # Starting windy period
                    assert windy_hours == 0
                    windy_period_start = date
                    windy_hours = 1
                else:
                    # Still rideable
                    windy_hours += 1
            else:
                # Not rideable anymore
                if windy_hours >= 2:
                    windy_periods.append((windy_period_start, date))
                windy_period_start = None
                windy_hours = 0

        imname = f"{location['name']}.png"
        
        print(f"![]({imname})", file=f)
        print(file=f)
        print(file=f)
        if len(windy_periods) == 0:
            print("No rideable periods found :(", file=f)
        else:
            print("Rideable periods:\n", file=f)
            for windy_period in windy_periods:
                print(f"{windy_period[0].date()} from {windy_period[0].hour}:00 to {windy_period[1].hour}:00", file=f)
        print(file=f)
        print(file=f)
        print(file=f)
        print(file=f)

        plt.figure(figsize=(16, 10))

        ax1 = plt.subplot(212)
        ax1.plot(hourly_date, hourly_temperature_2m, color="r")
        ax1.set_xlim(
            left=(np.datetime64("now") + np.timedelta64(response.UtcOffsetSeconds())),
            right=hourly_date[-1],
        )
        secax = ax1.twinx()
        secax.bar(hourly_date, hourly_precipitation, width=0.025, color="g")

        locator = mdates.HourLocator(interval=3)
        ax1.xaxis.set_major_locator(locator)
        ax1.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

        ax2 = plt.subplot(211, sharex=ax1)

        # Plot gusts first to auto-set limits, then set day-night, then plot barbs
        ax2.plot(hourly_date, hourly_wind_gusts_10m, color="blue", marker=".")

        for ax in ax1, ax2:
            ax.axvspan(ax.get_xlim()[0], ax.get_xlim()[1], color="b", alpha=0.18)
            for sunrise, sunset in zip(daily_sunrise, daily_sunset):
                ax.axvspan(
                    np.datetime64(int(sunrise), "s")
                    + np.timedelta64(response.UtcOffsetSeconds()),
                    np.datetime64(int(sunset), "s")
                    + np.timedelta64(response.UtcOffsetSeconds()),
                    color="w",
                )

        ax2.barbs(hourly_date, hourly_wind_speed_10m, hourly_u_10m, hourly_v_10m, color="gray")
        ax2.plot(hourly_date, hourly_wind_speed_10m, color="purple", marker=".")

        ax1.grid()
        ax2.grid()

        ax1.set_ylabel("Temp (F)")
        secax.set_ylabel("Precipitation (in)")
        ax2.set_ylabel("Wind (kt)")
        ax1.set_xlabel("Local time")

        ax2.set_title(f"Wind speed at {location['latitude']}, {location['longitude']} ({location['name']})")

        plt.savefig(imname)
