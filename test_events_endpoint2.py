import requests
from bson import json_util

url = "http://localhost:8080/events"

# Correct AppInitializer payload (no _cls/_CLS)
payload = {
    "events": [
        "capture_notebook_cell",
        "close_session",
        "reactivate_notebook_cell",
        "refresh",
        "reload_session",
        "select_labels",
        "select_samples",
        "set_color_scheme",
        "set_dataset_color_scheme",
        "set_group_slice",
        "set_sample",
        "set_spaces",
        "state_update",
    ],
    "initializer": {
        "dataset": "minimal_test",
        "group_id": None,
        "group_slice": None,
        "sample_id": None,
        "view": None,
        "workspace": None,
    },
    "subscription": "test-subscription-456",
}

print(f"POST {url}")
response = requests.post(
    url,
    stream=True,
    headers={
        "Accept": "text/event-stream",
        "Content-type": "application/json",
    },
    data=json_util.dumps(payload),
    timeout=10,
)
print(f"Status: {response.status_code}")
print(f"Headers: {dict(response.headers)}")

for i, line in enumerate(response.iter_lines()):
    if i > 30:
        break
    if line:
        decoded = line.decode('utf-8', errors='replace')
        print(decoded[:500])
        if "state_update" in decoded.lower():
            print("FOUND STATE UPDATE!")
