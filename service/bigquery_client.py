import os
from google.cloud import bigquery
from datetime import datetime, timezone

try:
    import config
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = config.GOOGLE_APPLICATION_CREDENTIALS
    PROJECT_ID = config.PROJECT_ID
    DATASET_NAME = config.DATASET_NAME
    SENSOR_TABLE = config.SENSOR_TABLE
except ImportError:
    PROJECT_ID = os.getenv('PROJECT_ID')
    DATASET_NAME = os.getenv('DATASET_NAME')
    SENSOR_TABLE = os.getenv('SENSOR_TABLE')

class BigQueryClient:
    def __init__(self):
        self.client = bigquery.Client(project=PROJECT_ID)
        self.table_id = f"{PROJECT_ID}.{DATASET_NAME}.{SENSOR_TABLE}"

    def insert_sensor_data(self, data:dict) -> str:
        """
        Insert a single measurement into the sensor_data table. 
        
        Args: 
            data: A dictionary with the measurement values. 
            Returns:Example: {"indoor_temp": 22.5, "indoor_humidity":45.0, ...}

        Returns:
            A success message, or raises an exception on error.
        """
        # if no measurement_time is provided, use the current time
        if 'measurement_time' not in data:
            data['measurement_time'] = datetime.now(timezone.utc).isoformat()

        # Insert the row into BigQuery
        errors = self.client.insert_rows_json(self.table_id, [data])

        if errors:
            raise Exception(f"Failed to insert : {errors}")
            
        return "Data inserted successfully"
    
    def get_latest_sensor_data(self) -> dict:      # ← tu ajoutes ici
        """Return the most recent row from sensor_data for device startup sync."""
        query = f"""
            SELECT *
            FROM `{self.table_id}`
            ORDER BY measurement_time DESC
            LIMIT 1
        """
        result = self.client.query(query).result()
        for row in result:
            return dict(row)
        return {}