import os
import time
import requests
import sys

def get_token():
    """Fetches the OAuth2 token from BarentsWatch. (Çağatay will make this robust later)"""
    client_id = os.environ.get("BW_CLIENT_ID")
    client_secret = os.environ.get("BW_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("ERROR: BW_CLIENT_ID or BW_CLIENT_SECRET not found in environment.")
        sys.exit(1)
        
    url = "https://id.barentswatch.no/connect/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": "api"
    }
    
    response = requests.post(url, data=data, timeout=10)
    if response.status_code != 200:
        print(f"ERROR: Failed to authenticate (HTTP {response.status_code}). Check your credentials.")
        sys.exit(1)
        
    return response.json().get("access_token")

def make_request(url, token, timeout=10, max_retries=5):
    """
    Robust request layer (Egemen's Task).
    Handles timeouts, 429/5xx backoffs, and strict 401/403 stops.
    """
    headers = {"Authorization": f"Bearer {token}"}
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            
            # Real 401/403: Stop immediately
            if response.status_code in (401, 403):
                print(f"FATAL: Authentication error {response.status_code} on {url}. Stopping.")
                sys.exit(1)
                
            # 429 or 5xx: Wait and retry
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                print(f"WARNING: HTTP {response.status_code} on {url}. Retrying in {retry_after}s...")
                time.sleep(retry_after)
                continue
                
            # Success or other client errors
            return response
            
        except requests.exceptions.Timeout:
            print(f"WARNING: Timeout on {url}. Retrying in {2 ** attempt}s...")
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            print(f"WARNING: Network error on {url}: {e}. Retrying in {2 ** attempt}s...")
            time.sleep(2 ** attempt)
            
    print(f"ERROR: Max retries ({max_retries}) exceeded for {url}.")
    return None
