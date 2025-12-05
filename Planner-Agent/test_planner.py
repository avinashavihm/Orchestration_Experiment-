import urllib.request
import urllib.parse
import json
import time
import sys

PLANNER_URL = "http://localhost:8002"

def wait_for_service():
    print("Waiting for Planner Agent to be ready...")
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{PLANNER_URL}/health") as response:
                if response.getcode() == 200:
                    print("Planner Agent is ready!")
                    return True
        except Exception:
            pass
        time.sleep(2)
    print("Planner Agent failed to start.")
    return False

def upload_file(filename, content, content_type):
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    data = []
    data.append(f'--{boundary}')
    data.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"')
    data.append(f'Content-Type: {content_type}')
    data.append('')
    data.append(content)
    data.append(f'--{boundary}--')
    data.append('')
    
    body = '\r\n'.join(data).encode('utf-8')
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }
    
    req = urllib.request.Request(f"{PLANNER_URL}/analyze", data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            return response.getcode(), json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))
    except Exception as e:
        return 500, {"error": str(e)}

def test_recruitment_routing():
    print("\nTesting Recruitment Routing...")
    status, data = upload_file('protocol_v1.pdf', 'dummy pdf content', 'application/pdf')
    
    print(f"Status: {status}")
    print(f"Response: {json.dumps(data, indent=2)}")
    
    if data.get("planner_decision") == "recruitment":
        print("✅ SUCCESS: Routed to Recruitment Agent")
    else:
        print(f"❌ FAILURE: Routed to {data.get('planner_decision')}")

def test_supply_routing():
    print("\nTesting Supply Routing...")
    status, data = upload_file('site_supply_data.csv', 'dummy csv content', 'text/csv')
    
    print(f"Status: {status}")
    print(f"Response: {json.dumps(data, indent=2)}")
    
    if data.get("planner_decision") == "supply":
        print("✅ SUCCESS: Routed to Supply Agent")
    else:
        print(f"❌ FAILURE: Routed to {data.get('planner_decision')}")

if __name__ == "__main__":
    if wait_for_service():
        test_recruitment_routing()
        test_supply_routing()
