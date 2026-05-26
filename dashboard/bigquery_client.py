from google.cloud import bigquery
import pandas as pd
from config import PROJECT_ID, DATASET_ID, TABLE_ID


def get_client():
    """Return a BigQuery client."""
    return bigquery.Client(project=PROJECT_ID)


def get_latest_reading():
    """Fetch the most recent sensor reading."""
    client = get_client()
    query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        ORDER BY measurement_time DESC
        LIMIT 1
    """
    df = client.query(query).to_dataframe()
    if df.empty:
        return None
    return df.iloc[0]

def get_historical_data(hours: int = 24):
    """Fetch sensor readings for the past N hours."""
    client = get_client()
    query = f"""
        SELECT
            measurement_time,
            indoor_temp,
            indoor_humidity,
            indoor_air_quality,
            outdoor_temp,
            outdoor_humidity
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE measurement_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
        ORDER BY measurement_time ASC
    """
    df = client.query(query).to_dataframe()
    if not df.empty:
        df["measurement_time"] = pd.to_datetime(df["measurement_time"], utc=True).dt.tz_convert('Europe/Zurich')
    return df


def get_daily_stats(days: int = 7):
    """Fetch daily min/max/avg stats for the past N days."""
    client = get_client()
    query = f"""
        SELECT
            DATE(measurement_time)        AS day,
            ROUND(AVG(indoor_temp),  1)   AS avg_indoor_temp,
            ROUND(MIN(indoor_temp),  1)   AS min_indoor_temp,
            ROUND(MAX(indoor_temp),  1)   AS max_indoor_temp,
            ROUND(AVG(indoor_humidity),1) AS avg_indoor_humidity,
            ROUND(AVG(indoor_air_quality),1) AS avg_air_quality,
            ROUND(AVG(outdoor_temp), 1)   AS avg_outdoor_temp
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE measurement_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        GROUP BY day
        ORDER BY day ASC
    """
    return client.query(query).to_dataframe()
