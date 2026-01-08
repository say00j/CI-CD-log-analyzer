# import requests

# url = "http://localhost:8000/webhook/ci"

# payload = {
#     "log_text": "Running tests...\nFAILED test_api.py::test_login"
# }

# res = requests.post(url, json=payload)
# print(res.json())

import requests

res = requests.post(
    "http://localhost:8000/analyze",
    json={
        "log_key": "5aabfee6-fbd6-4a5f-9be3-db88b424f673.log"
    }
)

print(res.json())
