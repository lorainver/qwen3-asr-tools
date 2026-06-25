import urllib.request
import json
import sys
import time

def test_person_stream(person_name, days=90):
    url = "http://127.0.0.1:8000/api/kb/person_stream"
    payload = {
        "person_name": person_name,
        "days": days
    }
    
    print(f"Testing person stream for person: {person_name}...")
    headers = {'Content-Type': 'application/json'}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            for line in response:
                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue
                if line_str.startswith("data: "):
                    event_data = json.loads(line_str[6:])
                    step = event_data.get("step")
                    msg = event_data.get("msg")
                    print(f"[{step.upper()}] {msg}")
                    if step == "done":
                        print("\nPerson Profile Content:")
                        print("=" * 60)
                        print(event_data.get("answer"))
                        print("=" * 60)
                        print(f"Total messages analyzed: {event_data.get('message_count')}")
    except Exception as e:
        print(f"Error during streaming request: {e}")
    print(f"Elapsed time: {time.time() - t0:.1f}s")

if __name__ == "__main__":
    test_person = "清崇"
    if len(sys.argv) > 1:
        test_person = sys.argv[1]
    test_person_stream(test_person)
