import sys
from hybrid_search import hybrid_search

print("Starting test search...")
try:
    result = hybrid_search("mitochondria", top_k=1)
    print("Search completed!")
    print(f"Fallback: {result.get('fallback')}")
    print(f"Confidence: {result.get('confidence_tier')}")
    print(f"Match: {result.get('best_match', {}).get('name')}")
except Exception as e:
    print(f"Error: {e}")
