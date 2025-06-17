#!/usr/bin/env python3
"""
Test script for the Chatterbox TTS API
"""

import requests
import json
import time
import os

# Configuration
API_BASE_URL = "http://localhost:4123"
TEST_TEXTS = [
    "Hello, this is a simple test of the text to speech system.",
    "The quick brown fox jumps over the lazy dog. This sentence contains every letter of the alphabet and is commonly used for testing.",
    "In a hole in the ground there lived a hobbit. Not a nasty, dirty, wet hole, filled with the ends of worms and an oozy smell, nor yet a dry, bare, sandy hole with nothing in it to sit down on or to eat: it was a hobbit-hole, and that means comfort.",
]

def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Health check passed: {data}")
            return True
        else:
            print(f"✗ Health check failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Health check failed with error: {e}")
        return False

def test_models_endpoint():
    """Test the models listing endpoint"""
    print("\nTesting models endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/v1/models")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Models endpoint passed: {data}")
            return True
        else:
            print(f"✗ Models endpoint failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Models endpoint failed with error: {e}")
        return False

def test_api_docs():
    """Test that FastAPI documentation is available"""
    print("\nTesting API documentation endpoints...")
    try:
        # Test OpenAPI schema
        response = requests.get(f"{API_BASE_URL}/openapi.json")
        if response.status_code == 200:
            print("✓ OpenAPI schema available")
        else:
            print(f"✗ OpenAPI schema failed with status {response.status_code}")
        
        # Test Swagger UI
        response = requests.get(f"{API_BASE_URL}/docs")
        if response.status_code == 200:
            print("✓ Swagger UI available at /docs")
        else:
            print(f"✗ Swagger UI failed with status {response.status_code}")
            
        # Test ReDoc
        response = requests.get(f"{API_BASE_URL}/redoc")
        if response.status_code == 200:
            print("✓ ReDoc documentation available at /redoc")
            return True
        else:
            print(f"✗ ReDoc failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Documentation endpoints failed with error: {e}")
        return False

def test_text_to_speech_json(text, output_filename, custom_params=None):
    """Test the main JSON text-to-speech endpoint"""
    print(f"\nTesting TTS JSON endpoint with text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
    
    payload = {
        "input": text,
        "voice": "alloy",  # This will be ignored
        "response_format": "wav",  # This will be ignored
        "speed": 1.0  # This will be ignored
    }
    
    # Add custom parameters if provided
    if custom_params:
        payload.update(custom_params)
        print(f"  Using custom parameters: {custom_params}")
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/v1/audio/speech",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        end_time = time.time()
        
        if response.status_code == 200:
            # Save the audio file
            with open(output_filename, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content)
            duration = end_time - start_time
            
            print(f"✓ TTS JSON generation successful!")
            print(f"  - Duration: {duration:.2f} seconds")
            print(f"  - File size: {file_size:,} bytes")
            print(f"  - Output saved to: {output_filename}")
            return True
        else:
            print(f"✗ TTS JSON generation failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"  Error: {error_data}")
            except:
                print(f"  Raw response: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ TTS JSON generation failed with error: {e}")
        return False

def test_text_to_speech_upload(text, output_filename, custom_params=None):
    """Test the upload endpoint (form data, no file)"""
    print(f"\nTesting TTS upload endpoint with text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
    
    data = {
        "input": text,
        "voice": "alloy",  # This will be ignored
        "response_format": "wav",  # This will be ignored
        "speed": 1.0  # This will be ignored
    }
    
    # Add custom parameters if provided
    if custom_params:
        data.update(custom_params)
        print(f"  Using custom parameters: {custom_params}")
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/v1/audio/speech/upload",
            data=data
        )
        end_time = time.time()
        
        if response.status_code == 200:
            # Save the audio file
            with open(output_filename, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content)
            duration = end_time - start_time
            
            print(f"✓ TTS upload generation successful!")
            print(f"  - Duration: {duration:.2f} seconds")
            print(f"  - File size: {file_size:,} bytes")
            print(f"  - Output saved to: {output_filename}")
            return True
        else:
            print(f"✗ TTS upload generation failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"  Error: {error_data}")
            except:
                print(f"  Raw response: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ TTS upload generation failed with error: {e}")
        return False

def test_error_handling():
    """Test error handling with invalid requests"""
    print("\nTesting error handling...")
    
    # Test missing input field (JSON endpoint)
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/audio/speech",
            json={"voice": "alloy"},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 422:  # FastAPI uses 422 for validation errors
            print("✓ Missing input field error handled correctly (JSON)")
        else:
            print(f"✗ Expected 422 for missing input (JSON), got {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ Error testing missing input (JSON): {e}")
    
    # Test missing input field (upload endpoint)
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/audio/speech/upload",
            data={"voice": "alloy"}
        )
        if response.status_code == 422:  # FastAPI uses 422 for validation errors
            print("✓ Missing input field error handled correctly (upload)")
        else:
            print(f"✗ Expected 422 for missing input (upload), got {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ Error testing missing input (upload): {e}")
    
    # Test empty input (JSON)
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/audio/speech",
            json={"input": ""}
        )
        if response.status_code == 422:  # FastAPI validation error
            print("✓ Empty input error handled correctly (JSON)")
        else:
            print(f"✗ Expected 422 for empty input (JSON), got {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ Error testing empty input (JSON): {e}")
    
    # Test empty input (upload)
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/audio/speech/upload",
            data={"input": ""}
        )
        if response.status_code == 422:  # FastAPI validation error
            print("✓ Empty input error handled correctly (upload)")
        else:
            print(f"✗ Expected 422 for empty input (upload), got {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ Error testing empty input (upload): {e}")
    
    # Test invalid parameter ranges (JSON)
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/audio/speech",
            json={"input": "test", "exaggeration": 5.0}  # Out of range
        )
        if response.status_code == 422:
            print("✓ Invalid parameter range error handled correctly (JSON)")
        else:
            print(f"✗ Expected 422 for invalid parameter (JSON), got {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ Error testing invalid parameters (JSON): {e}")
    
    # Test very long text (JSON)
    try:
        long_text = "This is a test. " * 200  # Should exceed max length
        response = requests.post(
            f"{API_BASE_URL}/v1/audio/speech",
            json={"input": long_text}
        )
        if response.status_code == 400:
            print("✓ Long text error handled correctly (JSON)")
        else:
            print(f"✗ Expected 400 for long text (JSON), got {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ Error testing long text (JSON): {e}")

def test_custom_parameters():
    """Test TTS with various custom parameters"""
    print("\nTesting custom parameters...")
    
    # Test different exaggeration levels
    test_cases = [
        {"exaggeration": 0.3, "description": "Low exaggeration"},
        {"exaggeration": 0.8, "description": "High exaggeration"},
        {"cfg_weight": 0.2, "description": "Fast speech"},
        {"cfg_weight": 0.8, "description": "Slow speech"},
        {"temperature": 0.4, "description": "Low randomness"},
        {"temperature": 1.2, "description": "High randomness"},
        {"exaggeration": 0.7, "cfg_weight": 0.3, "temperature": 0.9, "description": "Combined parameters"}
    ]
    
    base_text = "This is a test of custom parameters for text to speech generation."
    
    for i, test_case in enumerate(test_cases):
        description = test_case.pop("description")
        print(f"\n  Test case {i+1}: {description}")
        
        # Test both JSON and upload endpoints
        json_filename = f"test_custom_{i+1}_json.wav"
        upload_filename = f"test_custom_{i+1}_upload.wav"
        
        # Test JSON endpoint
        success_json = test_text_to_speech_json(base_text, json_filename, test_case.copy())
        
        # Test upload endpoint  
        success_upload = test_text_to_speech_upload(base_text, upload_filename, test_case.copy())
        
        if success_json and success_upload:
            print(f"    ✓ Both endpoints succeeded for {description}")
        elif success_json or success_upload:
            print(f"    ⚠ Only one endpoint succeeded for {description}")
        else:
            print(f"    ✗ Both endpoints failed for {description}")

def main():
    """Main test function"""
    print("=" * 60)
    print("Chatterbox TTS API Test Suite")
    print("=" * 60)
    
    # Check if API is running
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ API not responding properly. Status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to API at {API_BASE_URL}")
        print("   Make sure the API is running with: python main.py")
        return False
    except Exception as e:
        print(f"❌ Error checking API: {e}")
        return False
    
    print("✅ API is running\n")
    
    # Run all tests
    tests_passed = 0
    total_tests = 0
    
    # Basic endpoint tests
    total_tests += 1
    if test_health_check():
        tests_passed += 1
    
    total_tests += 1
    if test_models_endpoint():
        tests_passed += 1
        
    total_tests += 1
    if test_api_docs():
        tests_passed += 1
    
    # Test both JSON and upload endpoints with different texts
    for i, text in enumerate(TEST_TEXTS):
        # JSON endpoint test
        total_tests += 1
        json_filename = f"test_output_{i+1}_json.wav"
        if test_text_to_speech_json(text, json_filename):
            tests_passed += 1
        
        # Upload endpoint test
        total_tests += 1
        upload_filename = f"test_output_{i+1}_upload.wav"
        if test_text_to_speech_upload(text, upload_filename):
            tests_passed += 1
    
    # Error handling tests
    print("\n" + "="*40)
    test_error_handling()
    
    # Custom parameter tests
    print("\n" + "="*40)
    test_custom_parameters()
    
    # Final summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    print(f"Success rate: {(tests_passed/total_tests)*100:.1f}%")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {total_tests - tests_passed} test(s) failed")
    
    print("\nGenerated audio files:")
    for file in os.listdir('.'):
        if (file.startswith('test_output_') or file.startswith('test_custom_')) and file.endswith('.wav'):
            size = os.path.getsize(file)
            print(f"  - {file} ({size:,} bytes)")
    
    print(f"\n💡 Check the generated .wav files to verify audio quality")
    print(f"💡 Visit {API_BASE_URL}/docs for interactive API documentation")
    print(f"💡 Main endpoint: {API_BASE_URL}/v1/audio/speech (JSON)")
    print(f"💡 Upload endpoint: {API_BASE_URL}/v1/audio/speech/upload (form data + voice files)")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 