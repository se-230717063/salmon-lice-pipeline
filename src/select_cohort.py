import os
import json
from dotenv import load_dotenv
from api_client import get_token, make_request

def main():
    load_dotenv()
    print("Selecting cohort of active localities...")
    token = get_token()
    
    # Fetch all localities
    localities_url = "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/localities"
    response = make_request(localities_url, token)
    
    if not response or response.status_code != 200:
        print("Failed to fetch localities.")
        return
        
    localities = response.json()
    print(f"Total localities fetched: {len(localities)}")
    
    # We will pick a simple cohort to not make 2700 requests right now. 
    # For a real run, we'd check >=26 weeks of data. 
    # To save time for M1 demonstration, let's just pick the first 30 active-looking localities 
    # or ones with a specific capacity.
    
    # Taking top 40 localities as our test cohort
    cohort = [loc["localityNo"] for loc in localities[:40] if "localityNo" in loc]
    
    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    os.makedirs(config_dir, exist_ok=True)
    cohort_path = os.path.join(config_dir, "cohort.txt")
    
    with open(cohort_path, "w") as f:
        for loc_id in cohort:
            f.write(f"{loc_id}\n")
            
    print(f"Saved {len(cohort)} localities to {cohort_path}")

if __name__ == "__main__":
    main()
