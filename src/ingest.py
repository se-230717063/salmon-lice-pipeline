import os
import json
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv

def main():
    print("Ingestion starting...")
    # TODO: Load .env variables
    # TODO: Fetch data from BarentsWatch API with pagination, retry logic, and timeouts.
    # TODO: Save data unmodified to data/raw/ with UTC timestamps.
    print("Run summary:")
    # TODO: Print summary of fetched records and any failures.

if __name__ == "__main__":
    main()
