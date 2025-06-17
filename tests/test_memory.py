#!/usr/bin/env python3
"""
Memory Management Test Script for Chatterbox TTS API
Tests memory usage patterns and cleanup functionality
"""

import requests
import json
import time
import concurrent.futures
from typing import Dict, List

# Configuration
API_BASE_URL = "http://localhost:4123"

def get_memory_status() -> Dict:
    """Get current memory status from the API"""
    try:
        response = requests.get(f"{API_BASE_URL}/memory")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to get memory status: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error getting memory status: {e}")
        return {}

def perform_cleanup() -> Dict:
    """Trigger manual memory cleanup"""
    try:
        response = requests.get(f"{API_BASE_URL}/memory?cleanup=true&force_cuda_clear=true")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to perform cleanup: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error performing cleanup: {e}")
        return {}

def reset_memory_tracking() -> Dict:
    """Reset memory tracking (with confirmation)"""
    try:
        response = requests.post(f"{API_BASE_URL}/memory/reset?confirm=true")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to reset memory tracking: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error resetting memory tracking: {e}")
        return {}

def generate_speech(text: str, request_id: int) -> Dict:
    """Generate speech and return timing/memory info"""
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/audio/speech",
            json={"input": text},
            headers={"Content-Type": "application/json"}
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if response.status_code == 200:
            return {
                "request_id": request_id,
                "success": True,
                "duration": duration,
                "audio_size": len(response.content),
                "text_length": len(text)
            }
        else:
            return {
                "request_id": request_id,
                "success": False,
                "duration": duration,
                "error": response.text
            }
            
    except Exception as e:
        return {
            "request_id": request_id,
            "success": False,
            "duration": time.time() - start_time,
            "error": str(e)
        }

def test_memory_baseline():
    """Test baseline memory usage"""
    print("=" * 60)
    print("Memory Baseline Test")
    print("=" * 60)
    
    # Reset memory tracking
    print("Resetting memory tracking...")
    reset_result = reset_memory_tracking()
    print(f"Reset result: {reset_result.get('status', 'unknown')}")
    
    # Get initial memory status
    initial_memory = get_memory_status()
    print(f"Initial memory status:")
    if 'memory_info' in initial_memory:
        memory_info = initial_memory['memory_info']
        print(f"  CPU: {memory_info.get('cpu_memory_mb', 0):.1f}MB")
        if 'gpu_memory_allocated_mb' in memory_info:
            print(f"  GPU: {memory_info.get('gpu_memory_allocated_mb', 0):.1f}MB allocated")
    
    return initial_memory

def test_sequential_requests(num_requests: int = 10):
    """Test memory usage with sequential requests"""
    print(f"\n{'='*60}")
    print(f"Sequential Requests Test ({num_requests} requests)")
    print(f"{'='*60}")
    
    test_texts = [
        "This is a short test sentence.",
        "This is a medium length test sentence that contains more words and should take more processing time.",
        "This is a much longer test sentence that contains significantly more words and should demonstrate how the system handles longer text inputs with multiple chunks and memory management across extended processing periods.",
    ]
    
    memory_snapshots = []
    request_results = []
    
    for i in range(num_requests):
        text = test_texts[i % len(test_texts)]
        print(f"\nRequest {i+1}/{num_requests}: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        
        # Get memory before request
        memory_before = get_memory_status()
        
        # Generate speech
        result = generate_speech(text, i+1)
        
        # Get memory after request
        memory_after = get_memory_status()
        
        # Store results
        request_results.append(result)
        memory_snapshots.append({
            "request_id": i+1,
            "memory_before": memory_before.get('memory_info', {}),
            "memory_after": memory_after.get('memory_info', {}),
            "request_counter": memory_after.get('request_counter', 0)
        })
        
        # Print status
        if result['success']:
            print(f"  ✓ Success: {result['duration']:.2f}s, {result['audio_size']:,} bytes")
        else:
            print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
        
        # Print memory change
        if 'memory_info' in memory_before and 'memory_info' in memory_after:
            cpu_before = memory_before['memory_info'].get('cpu_memory_mb', 0)
            cpu_after = memory_after['memory_info'].get('cpu_memory_mb', 0)
            cpu_diff = cpu_after - cpu_before
            
            print(f"  📊 CPU Memory: {cpu_before:.1f}MB → {cpu_after:.1f}MB ({cpu_diff:+.1f}MB)")
            
            if 'gpu_memory_allocated_mb' in memory_before['memory_info']:
                gpu_before = memory_before['memory_info'].get('gpu_memory_allocated_mb', 0)
                gpu_after = memory_after['memory_info'].get('gpu_memory_allocated_mb', 0)
                gpu_diff = gpu_after - gpu_before
                print(f"  📊 GPU Memory: {gpu_before:.1f}MB → {gpu_after:.1f}MB ({gpu_diff:+.1f}MB)")
        
        # Small delay between requests
        time.sleep(0.5)
    
    return memory_snapshots, request_results

def test_concurrent_requests(num_concurrent: int = 3):
    """Test memory usage with concurrent requests"""
    print(f"\n{'='*60}")
    print(f"Concurrent Requests Test ({num_concurrent} concurrent)")
    print(f"{'='*60}")
    
    test_text = "This is a test sentence for concurrent processing to evaluate memory usage patterns."
    
    # Get memory before concurrent requests
    memory_before = get_memory_status()
    
    # Run concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        futures = [
            executor.submit(generate_speech, test_text, i+1) 
            for i in range(num_concurrent)
        ]
        
        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                if result['success']:
                    print(f"  ✓ Request {result['request_id']}: {result['duration']:.2f}s")
                else:
                    print(f"  ✗ Request {result['request_id']}: {result.get('error', 'Failed')}")
            except Exception as e:
                print(f"  ✗ Concurrent request failed: {e}")
    
    # Get memory after concurrent requests
    memory_after = get_memory_status()
    
    # Print memory comparison
    if 'memory_info' in memory_before and 'memory_info' in memory_after:
        cpu_before = memory_before['memory_info'].get('cpu_memory_mb', 0)
        cpu_after = memory_after['memory_info'].get('cpu_memory_mb', 0)
        cpu_diff = cpu_after - cpu_before
        
        print(f"\n📊 Concurrent Memory Impact:")
        print(f"  CPU: {cpu_before:.1f}MB → {cpu_after:.1f}MB ({cpu_diff:+.1f}MB)")
        
        if 'gpu_memory_allocated_mb' in memory_before['memory_info']:
            gpu_before = memory_before['memory_info'].get('gpu_memory_allocated_mb', 0)
            gpu_after = memory_after['memory_info'].get('gpu_memory_allocated_mb', 0)
            gpu_diff = gpu_after - gpu_before
            print(f"  GPU: {gpu_before:.1f}MB → {gpu_after:.1f}MB ({gpu_diff:+.1f}MB)")
    
    return results

def test_manual_cleanup():
    """Test manual memory cleanup functionality"""
    print(f"\n{'='*60}")
    print("Manual Cleanup Test")
    print(f"{'='*60}")
    
    # Get memory before cleanup
    memory_before = get_memory_status()
    print("Memory before cleanup:")
    if 'memory_info' in memory_before:
        memory_info = memory_before['memory_info']
        print(f"  CPU: {memory_info.get('cpu_memory_mb', 0):.1f}MB")
        if 'gpu_memory_allocated_mb' in memory_info:
            print(f"  GPU: {memory_info.get('gpu_memory_allocated_mb', 0):.1f}MB")
    
    # Perform cleanup
    print("\nPerforming manual cleanup...")
    cleanup_result = perform_cleanup()
    
    if cleanup_result.get('cleanup_performed'):
        print(f"✓ Cleanup performed: {cleanup_result.get('collected_objects', 0)} objects collected")
        if cleanup_result.get('cuda_cache_cleared'):
            print("✓ CUDA cache cleared")
        
        # Show memory after cleanup
        if 'memory_info_after_cleanup' in cleanup_result:
            memory_after = cleanup_result['memory_info_after_cleanup']
            print(f"\nMemory after cleanup:")
            print(f"  CPU: {memory_after.get('cpu_memory_mb', 0):.1f}MB")
            if 'gpu_memory_allocated_mb' in memory_after:
                print(f"  GPU: {memory_after.get('gpu_memory_allocated_mb', 0):.1f}MB")
    else:
        print("✗ Cleanup not performed or failed")
        if 'cleanup_error' in cleanup_result:
            print(f"Error: {cleanup_result['cleanup_error']}")

def analyze_memory_trends(memory_snapshots: List[Dict]):
    """Analyze memory usage trends"""
    print(f"\n{'='*60}")
    print("Memory Trend Analysis")
    print(f"{'='*60}")
    
    if not memory_snapshots:
        print("No memory snapshots to analyze")
        return
    
    # Calculate trends
    cpu_values = []
    gpu_values = []
    
    for snapshot in memory_snapshots:
        cpu_after = snapshot['memory_after'].get('cpu_memory_mb', 0)
        cpu_values.append(cpu_after)
        
        if 'gpu_memory_allocated_mb' in snapshot['memory_after']:
            gpu_after = snapshot['memory_after'].get('gpu_memory_allocated_mb', 0)
            gpu_values.append(gpu_after)
    
    if cpu_values:
        print(f"CPU Memory Trend:")
        print(f"  Min: {min(cpu_values):.1f}MB")
        print(f"  Max: {max(cpu_values):.1f}MB")
        print(f"  Avg: {sum(cpu_values)/len(cpu_values):.1f}MB")
        print(f"  Growth: {cpu_values[-1] - cpu_values[0]:+.1f}MB")
        
        # Check for concerning trends
        if cpu_values[-1] > cpu_values[0] * 1.2:  # 20% growth
            print("  ⚠️  Warning: Significant CPU memory growth detected")
    
    if gpu_values:
        print(f"\nGPU Memory Trend:")
        print(f"  Min: {min(gpu_values):.1f}MB")
        print(f"  Max: {max(gpu_values):.1f}MB")
        print(f"  Avg: {sum(gpu_values)/len(gpu_values):.1f}MB")
        print(f"  Growth: {gpu_values[-1] - gpu_values[0]:+.1f}MB")
        
        # Check for concerning trends
        if gpu_values[-1] > gpu_values[0] * 1.2:  # 20% growth
            print("  ⚠️  Warning: Significant GPU memory growth detected")

def main():
    """Run comprehensive memory management tests"""
    print("🧪 Chatterbox TTS API - Memory Management Test Suite")
    print(f"API URL: {API_BASE_URL}")
    
    # Check if API is running
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code != 200:
            print("❌ API is not responding. Please start the server first.")
            return
        print("✓ API is running")
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return
    
    # Run tests
    initial_memory = test_memory_baseline()
    memory_snapshots, request_results = test_sequential_requests(15)
    concurrent_results = test_concurrent_requests(3)
    test_manual_cleanup()
    analyze_memory_trends(memory_snapshots)
    
    # Final summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    
    successful_requests = sum(1 for r in request_results if r['success'])
    total_requests = len(request_results)
    
    print(f"Sequential Requests: {successful_requests}/{total_requests} successful")
    
    concurrent_success = sum(1 for r in concurrent_results if r['success'])
    print(f"Concurrent Requests: {concurrent_success}/{len(concurrent_results)} successful")
    
    # Memory management recommendations
    final_memory = get_memory_status()
    if 'memory_info' in initial_memory and 'memory_info' in final_memory:
        initial_cpu = initial_memory['memory_info'].get('cpu_memory_mb', 0)
        final_cpu = final_memory['memory_info'].get('cpu_memory_mb', 0)
        cpu_growth = final_cpu - initial_cpu
        
        print(f"\nOverall Memory Growth: {cpu_growth:+.1f}MB CPU")
        
        if cpu_growth > 100:  # 100MB growth
            print("🚨 Recommendation: Consider reducing MEMORY_CLEANUP_INTERVAL")
        elif cpu_growth > 50:   # 50MB growth
            print("⚠️  Recommendation: Monitor memory usage in production")
        else:
            print("✅ Memory usage appears stable")
    
    print(f"\n🔧 Memory Management Endpoints:")
    print(f"  Monitor: GET {API_BASE_URL}/memory")
    print(f"  Cleanup: GET {API_BASE_URL}/memory?cleanup=true")
    print(f"  Reset: POST {API_BASE_URL}/memory/reset?confirm=true")

if __name__ == "__main__":
    main() 