import urllib.request
import json

url = "http://localhost:5002/api/dashboard"
data = json.dumps({}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        print("Status Code:", response.status)
        print("Response:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTP Error Code:", e.code)
    print("Error Response body:", e.read().decode('utf-8'))
except Exception as e:
    print("Other Error:", e)
