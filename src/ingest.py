import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from api_client import get_token, make_request

def main():
    load_dotenv()
    print("Ingestion starting...")
    token = get_token()
    
    # Read cohort
    cohort_path = os.path.join(os.path.dirname(__file__), "..", "config", "cohort.txt")
    if not os.path.exists(cohort_path):
        print(f"Cohort file not found at {cohort_path}. Run select_cohort.py first.")
        return
        
    with open(cohort_path, "r") as f:
        cohort = [line.strip() for line in f.readlines() if line.strip()]
        
    print(f"Loaded {len(cohort)} localities from cohort.")
    
    # Example ingestion loop (Çağatay will expand this to all endpoints & pagination)
    now_utc_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    
    # Let's create subfolders for types as planned
    for dtype in ["lice", "temperature", "treatments", "localities"]:
        os.makedirs(os.path.join(raw_dir, dtype), exist_ok=True)
        
    for loc_id in cohort:
        # Fetching Lice as an example (Çağatay will complete the flow)
        year = 2025 # Çağatay will make this a loop over 2022-2026
        url = f"https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/{loc_id}/avgfemalelice/{year}"
        
        response = make_request(url, token)
        if response and response.status_code == 200:
            # Save strictly using 'xb' to NEVER overwrite
            file_path = os.path.join(raw_dir, "lice", f"{loc_id}_{year}_{now_utc_str}.json")
            try:
                with open(file_path, "xb") as out_file:
                    out_file.write(response.content)
            except FileExistsError:
                print(f"File {file_path} already exists. Skipping to avoid overwrite.")
                
    # Run summary will be implemented by Çağatay
    print("Ingestion partial run complete.")

if __name__ == "__main__":
    main()
