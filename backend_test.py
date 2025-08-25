#!/usr/bin/env python3
"""
Backend API Testing Suite for Kernel Integration
Tests the backend endpoints after kernel integration.
"""

import requests
import json
import time
import sys
from typing import Dict, Any, List

# Get backend URL from frontend env
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error reading frontend .env: {e}")
        return "http://localhost:8001"
    return "http://localhost:8001"

BASE_URL = get_backend_url()
API_URL = f"{BASE_URL}/api"

print(f"Testing backend at: {API_URL}")

class TestResults:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def add_result(self, test_name: str, passed: bool, details: str = ""):
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        if passed:
            self.passed += 1
            print(f"✅ {test_name}")
        else:
            self.failed += 1
            print(f"❌ {test_name}: {details}")
    
    def summary(self):
        print(f"\n=== TEST SUMMARY ===")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Total: {len(self.results)}")
        return self.failed == 0

def test_sse_stream(url: str, expected_events: List[str] = None) -> Dict[str, Any]:
    """Test SSE streaming endpoint"""
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code != 200:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        
        events = []
        content_parts = []
        session_id = None
        
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])  # Remove 'data: ' prefix
                    events.append(data.get('type', 'unknown'))
                    
                    if data.get('type') == 'session':
                        session_id = data.get('session_id')
                    elif data.get('type') == 'content':
                        content_parts.append(data.get('content', ''))
                    elif data.get('type') == 'complete':
                        break
                    elif data.get('type') == 'error':
                        return {"success": False, "error": f"Stream error: {data.get('error')}"}
                        
                except json.JSONDecodeError as e:
                    continue  # Skip malformed JSON
        
        full_content = ''.join(content_parts).strip()
        
        return {
            "success": True,
            "events": events,
            "content": full_content,
            "session_id": session_id,
            "has_session": 'session' in events,
            "has_content": 'content' in events,
            "has_complete": 'complete' in events
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_json_endpoint(method: str, url: str, data: Dict = None) -> Dict[str, Any]:
    """Test JSON API endpoint"""
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=10)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, timeout=10)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}
        
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    results = TestResults()
    
    print("=== BACKEND KERNEL INTEGRATION TESTS ===\n")
    
    # Test 1: Kernel chat stream with French input
    print("1. Testing kernel chat stream with French input...")
    kernel_url = f"{API_URL}/chat/stream?provider=kernel&model=local&q=Bonjour&sessionId=test123&mode=public&council=2&truth=1"
    kernel_result = test_sse_stream(kernel_url)
    
    if kernel_result["success"]:
        # Check for expected SSE sequence
        has_proper_sequence = (kernel_result["has_session"] and 
                             kernel_result["has_content"] and 
                             kernel_result["has_complete"])
        
        # Check for kernel traits (should handle French, no external calls)
        content = kernel_result["content"]
        has_content = len(content) > 0
        
        if has_proper_sequence and has_content:
            results.add_result("Kernel SSE Stream", True, f"Session: {kernel_result['session_id']}, Content length: {len(content)}")
        else:
            results.add_result("Kernel SSE Stream", False, f"Missing sequence or content. Events: {kernel_result['events']}")
    else:
        results.add_result("Kernel SSE Stream", False, kernel_result["error"])
    
    # Test 2: Chat history persistence
    print("\n2. Testing chat history persistence...")
    if kernel_result.get("session_id"):
        history_url = f"{API_URL}/chat/history?sessionId={kernel_result['session_id']}"
        history_result = test_json_endpoint("GET", history_url)
        
        if history_result["success"]:
            messages = history_result["data"].get("messages", [])
            has_user_msg = any(msg.get("role") == "user" for msg in messages)
            has_assistant_msg = any(msg.get("role") == "assistant" for msg in messages)
            
            if has_user_msg and has_assistant_msg:
                results.add_result("Chat History Persistence", True, f"Found {len(messages)} messages")
            else:
                results.add_result("Chat History Persistence", False, f"Missing user/assistant messages: {messages}")
        else:
            results.add_result("Chat History Persistence", False, history_result["error"])
    else:
        results.add_result("Chat History Persistence", False, "No session ID from previous test")
    
    # Test 3: Kernel memory endpoint
    print("\n3. Testing kernel memory endpoint...")
    memory_result = test_json_endpoint("GET", f"{API_URL}/kernel/memory")
    
    if memory_result["success"]:
        data = memory_result["data"]
        if data.get("ok") and "memory" in data:
            results.add_result("Kernel Memory GET", True, f"Memory object present")
        else:
            results.add_result("Kernel Memory GET", False, f"Invalid response: {data}")
    else:
        results.add_result("Kernel Memory GET", False, memory_result["error"])
    
    # Test 4: Kernel memory approve
    print("\n4. Testing kernel memory approve...")
    approve_data = {"key": "contrainte", "value": "local-first; concision"}
    approve_result = test_json_endpoint("POST", f"{API_URL}/kernel/memory/approve", approve_data)
    
    if approve_result["success"]:
        data = approve_result["data"]
        if data.get("ok"):
            results.add_result("Kernel Memory Approve", True)
            
            # Verify the memory was set
            print("   Verifying memory was set...")
            verify_result = test_json_endpoint("GET", f"{API_URL}/kernel/memory")
            if verify_result["success"]:
                memory_data = verify_result["data"].get("memory", {})
                if "contrainte" in str(memory_data):
                    results.add_result("Memory Approve Verification", True, "Key found in memory")
                else:
                    results.add_result("Memory Approve Verification", False, f"Key not found in memory: {memory_data}")
            else:
                results.add_result("Memory Approve Verification", False, verify_result["error"])
        else:
            results.add_result("Kernel Memory Approve", False, f"Invalid response: {data}")
    else:
        results.add_result("Kernel Memory Approve", False, approve_result["error"])
    
    # Test 5: Kernel feedback
    print("\n5. Testing kernel feedback...")
    feedback_data = {"label": "approve"}
    feedback_result = test_json_endpoint("POST", f"{API_URL}/kernel/feedback", feedback_data)
    
    if feedback_result["success"]:
        data = feedback_result["data"]
        if data.get("ok"):
            results.add_result("Kernel Feedback", True)
        else:
            results.add_result("Kernel Feedback", False, f"Invalid response: {data}")
    else:
        results.add_result("Kernel Feedback", False, feedback_result["error"])
    
    # Test 6: Kernel mutate
    print("\n6. Testing kernel mutate...")
    mutate_data = {"trials": 3}
    mutate_result = test_json_endpoint("POST", f"{API_URL}/kernel/mutate", mutate_data)
    
    if mutate_result["success"]:
        data = mutate_result["data"]
        if data.get("ok") and "result" in data:
            result_obj = data["result"]
            has_adopted = "adopted" in str(result_obj)
            results.add_result("Kernel Mutate", True, f"Result: {result_obj}")
        else:
            results.add_result("Kernel Mutate", False, f"Invalid response: {data}")
    else:
        results.add_result("Kernel Mutate", False, mutate_result["error"])
    
    # Test 7: Regression test - OpenAI provider
    print("\n7. Testing OpenAI provider regression...")
    openai_url = f"{API_URL}/chat/stream?provider=openai&model=gpt-4o-mini&q=Test&sessionId=regression_test"
    openai_result = test_sse_stream(openai_url)
    
    if openai_result["success"]:
        has_proper_sequence = (openai_result["has_session"] and 
                             openai_result["has_content"] and 
                             openai_result["has_complete"])
        
        if has_proper_sequence:
            results.add_result("OpenAI Provider Regression", True, f"Content length: {len(openai_result['content'])}")
        else:
            results.add_result("OpenAI Provider Regression", False, f"Missing sequence. Events: {openai_result['events']}")
    else:
        results.add_result("OpenAI Provider Regression", False, openai_result["error"])
    
    # Summary
    success = results.summary()
    
    print(f"\n=== DETAILED RESULTS ===")
    for result in results.results:
        status = "PASS" if result["passed"] else "FAIL"
        details = f" - {result['details']}" if result["details"] else ""
        print(f"{status}: {result['test']}{details}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())