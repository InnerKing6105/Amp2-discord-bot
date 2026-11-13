"""Safe AMP API connection check: never prints credentials or API response bodies."""
import os
from dotenv import load_dotenv
from amp_client import AMPClient, AMPError

load_dotenv()
try:
    client = AMPClient(os.environ["AMP_URL"], os.environ["AMP_USERNAME"], os.environ["AMP_PASSWORD"], os.getenv("AMP_INSTANCE_ID", ""))
    result = client.status()
    print("AMP login and status request: SUCCESS")
    print("AMP state code:", result.get("State", "unknown"))
    print("Make sure this is Mineverse's instance, not the ADS dashboard.")
except (AMPError, KeyError) as exc:
    print("AMP connection check FAILED:", exc)
    raise SystemExit(1)
