import requests
import time
import os

BASE_URL = "http://127.0.0.1:5001"

def test_bulk_process():
    print("Testing Bulk Process...")
    csv_path = "test_bulk.csv"
    with open(csv_path, 'rb') as f:
        files = {'file': f}
        r = requests.post(f"{BASE_URL}/api/bulk-upload", files=files)
        
    if r.status_code != 200:
        print(f"FAILED to upload: {r.text}")
        return
        
    task_id = r.json()['task_id']
    print(f"Task ID: {task_id}")
    
    while True:
        r = requests.get(f"{BASE_URL}/api/task-status/{task_id}")
        data = r.json()
        print(f"Status: {data['status']} | Progress: {data['progress']}/{data['total']} ({data['percent']}% )")
        
        if data['status'] in ['completed', 'stopped']:
            break
        time.sleep(2)
        
    print("Downloading results...")
    r = requests.get(f"{BASE_URL}/api/task-download/{task_id}")
    with open("test_results.csv", "wb") as f:
        f.write(r.content)
    print("Results saved to test_results.csv")
    
    # Check content
    with open("test_results.csv", "r") as f:
        print("\n--- RESULTS CONTENT ---")
        print(f.read())
        print("-----------------------")

if __name__ == "__main__":
    try:
        test_bulk_process()
    except Exception as e:
        print(f"ERROR: {e}")
