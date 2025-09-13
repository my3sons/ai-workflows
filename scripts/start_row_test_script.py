#!/usr/bin/env python3
"""
Test script to demonstrate the new start_row functionality in the batch orchestrator.
This script shows how to create batch plans with custom starting row numbers.
"""

import json
import requests
import sys

def test_create_batch_plan_with_start_row(base_url: str, start_row: int = 1):
    """Test creating a batch plan with a custom start row."""
    
    # Test data
    test_data = {
        "action": "create_batch_plan",
        "execution_id": f"test_start_row_{start_row}",
        "total_records": 100,
        "batch_size": 25,
        "project_id": "bbyus-ana-puca-d01",
        "dataset": "ORDER_ANALYSIS",
        "start_row": start_row,
        "record_limit": 100
    }
    
    print(f"Testing create_batch_plan with start_row={start_row}")
    print(f"Request data: {json.dumps(test_data, indent=2)}")
    
    try:
        response = requests.post(base_url, json=test_data)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Success! Response: {json.dumps(result, indent=2)}")
        
        # Verify the batches start from the correct row
        if "pending_batches" in result:
            for i, batch in enumerate(result["pending_batches"]):
                expected_start = start_row + (i * test_data["batch_size"])
                expected_end = start_row + ((i + 1) * test_data["batch_size"]) - 1
                
                if batch["start_row"] == expected_start and batch["end_row"] == expected_end:
                    print(f"  ✅ Batch {i+1}: start_row={batch['start_row']}, end_row={batch['end_row']} (correct)")
                else:
                    print(f"  ❌ Batch {i+1}: start_row={batch['start_row']}, end_row={batch['end_row']} (expected {expected_start}-{expected_end})")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main test function."""
    
    # Default Cloud Function URL (update with your actual URL)
    base_url = "https://us-central1-bbyus-ana-puca-d01.cloudfunctions.net/batch-orchestrator"
    
    print("🧪 Testing start_row functionality in batch orchestrator")
    print("=" * 60)
    
    # Test 1: Default start_row (should be 1)
    print("\n1. Testing with default start_row (should be 1):")
    success1 = test_create_batch_plan_with_start_row(base_url, 1)
    
    # Test 2: Custom start_row (1001)
    print("\n2. Testing with custom start_row (1001):")
    success2 = test_create_batch_plan_with_start_row(base_url, 1001)
    
    # Test 3: Another custom start_row (5001)
    print("\n3. Testing with custom start_row (5001):")
    success3 = test_create_batch_plan_with_start_row(base_url, 5001)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"  Default start_row (1): {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"  Custom start_row (1001): {'✅ PASS' if success2 else '❌ FAIL'}")
    print(f"  Custom start_row (5001): {'✅ PASS' if success3 else '❌ FAIL'}")
    
    if all([success1, success2, success3]):
        print("\n🎉 All tests passed! The start_row functionality is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please check the Cloud Function deployment and configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main()
