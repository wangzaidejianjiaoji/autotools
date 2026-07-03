import requests
import json
from bson import json_util

url = "http://localhost:8080/events"

# Simulate browser's AppInitializer payload
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
        "_cls": "fiftyone.core.session.events.AppInitializer",
        "dataset": "minimal_test",
        "group_id": None,
        "group_slice": None,
        "sample_id": None,
        "view": None,
        "workspace": None,
    },
    "subscription": "test-subscription-123",
}

print(f"POST {url}")
try:
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

    # Read first few chunks
    for i, line in enumerate(response.iter_lines()):
        if i > 20:
            break
        if line:
            print(line.decode('utf-8', errors='replace')[:500])
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
