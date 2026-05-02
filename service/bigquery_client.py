import sys
import os

# Add the project root to sys.path so we can import config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from google.cloud import bigquery
from datetime import datetime, timezone

import config

class BigQueryClient:
    def __init__(self):
        # Tell google where to find the service account key
        import os
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = config.GOOGLE_APPLICATION_CREDENTIALS

        #create a BigQuery client
        self.client = bigquery.Client(project=config.PROJECT_ID)

        # build the full table name (project.dataset.table)
        self.table_id = f"{config.PROJECT_ID}.{config.DATASET_NAME}.{config.SENSOR_TABLE}"

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