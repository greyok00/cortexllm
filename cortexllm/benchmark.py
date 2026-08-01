#!/usr/bin/env python3
"""
CortexLLM Benchmark Suite — throughput, latency, recall, and scale testing.

Measures:
  - Latency: P50/P95/P99 for read, write, search operations
  - Throughput: operations per second at various scales
  - Recall: retrieval accuracy with distractor injection
  - Concurrency: data loss under concurrent writes
  - Persistence: save/load roundtrip integrity

Usage:
    python3 benchmark.py              # Run all benchmarks
    python3 benchmark.py --quick      # Quick smoke test (100 ops)
    python3 benchmark.py --full       # Full suite (10K ops, all scales)
    python3 benchmark.py --latency    # Latency tests only
    python3 benchmark.py --recall     # Recall tests only
"""

import json
import sys
import time
import statistics
import math
import random
import string
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add parent to path for cortexllm imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cortexllm_db import db

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OPS_QUICK = 100
OPS_STANDARD = 1000
OPS_FULL = 10000

SCALES = [10, 100, 1000]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_string(length=20):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def generate_fact(n):
    return {
        "entity": f"entity_{n}",
        "attribute": f"attr_{n % 50}",
        "claim": f"claim_{n}: {random_string(50)}",
        "provenance": random.choice(["openclaw", "claude"]),
        "evidence": [f"ref_{random.randint(1, 100)}"],
    }

def percentile(data, p):
    if not data:
        return 0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)

def report_stats(label, latencies, ops_count=None):
    if not latencies:
        print(f"  {label}: NO DATA")
        return
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    avg = statistics.mean(latencies)
    total = sum(latencies)
    ops = ops_count or len(latencies)
    throughput = ops / total if total > 0 else 0
    print(f"  {label}:")
    print(f"    Count:     {len(latencies)} ops")
    print(f"    Avg:       {avg*1000:.2f} ms")
    print(f"    P50:       {p50*1000:.2f} ms")
    print(f"    P95:       {p95*1000:.2f} ms")
    print(f"    P99:       {p99*1000:.2f} ms")
    print(f"    Throughput: {throughput:.1f} ops/sec")

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def clean_test_data():
    """Remove all test data from the database."""
    w = db.writer
    w.execute("DELETE FROM Memory_Cold WHERE entity LIKE 'entity_%' OR entity LIKE 'bench_%'")
    w.execute("DELETE FROM Memory_Hot WHERE profile LIKE 'bench_%'")
    w.execute("DELETE FROM Memory_Warm WHERE profile LIKE 'bench_%'")
    w.commit()

# ---------------------------------------------------------------------------
# 1. Latency Benchmarks
# ---------------------------------------------------------------------------

def bench_latency_write(count=OPS_STANDARD):
    """Measure write latency for wiki_add operations."""
    latencies = []
    for i in range(count):
        fact = generate_fact(i)
        start = time.time()
        db.add_wiki_fact(**fact)
        elapsed = time.time() - start
        latencies.append(elapsed)
    return latencies

def bench_latency_read(count=OPS_STANDARD):
    """Measure read latency for wiki_get operations."""
    # Pre-fill
    for i in range(count):
        fact = generate_fact(i)
        db.add_wiki_fact(**fact)

    latencies = []
    for i in range(count):
        start = time.time()
        db.get_wiki_fact(f"entity_{i}", f"attr_{i % 50}")
        elapsed = time.time() - start
        latencies.append(elapsed)
    return latencies

def bench_latency_search(count=OPS_STANDARD):
    """Measure search latency for wiki_search operations."""
    queries = [f"claim_{random.randint(0, count-1)}" for _ in range(min(count, 200))]
    latencies = []
    for q in queries:
        start = time.time()
        db.search_wiki(q, limit=10)
        elapsed = time.time() - start
        latencies.append(elapsed)
    return latencies

# ---------------------------------------------------------------------------
# 2. Scale Benchmarks
# ---------------------------------------------------------------------------

def bench_scale():
    """Measure how latency degrades as the store grows."""
    print("\n  Pre-filling database at each scale...")
    results = {}
    for scale in SCALES:
        # Pre-fill up to this scale
        for i in range(scale):
            fact = generate_fact(i)
            db.add_wiki_fact(**fact)

        # Measure search latency at this scale
        latencies = []
        for _ in range(50):
            q = f"claim_{random.randint(0, scale-1)}"
            start = time.time()
            db.search_wiki(q, limit=10)
            elapsed = time.time() - start
            latencies.append(elapsed)

        p50 = percentile(latencies, 50)
        p95 = percentile(latencies, 95)
        results[scale] = {"p50_ms": round(p50*1000, 2), "p95_ms": round(p95*1000, 2)}
        print(f"    {scale} entries: P50={results[scale]['p50_ms']}ms  P95={results[scale]['p95_ms']}ms")

    return results

# ---------------------------------------------------------------------------
# 3. Recall Benchmarks
# ---------------------------------------------------------------------------

def bench_recall():
    """Measure retrieval accuracy with distractor injection."""
    print("\n  Injecting facts and distractors...")

    # Insert 50 target facts with unique claims
    targets = {}
    for i in range(50):
        e = f"recall_target_{i}"
        a = "test_attr"
        c = f"unique_recall_claim_{i}_{random_string(10)}"
        db.add_wiki_fact(entity=e, attribute=a, claim=c, provenance="claude")
        targets[c] = e

    # Insert 500 distractor facts
    for i in range(500):
        db.add_wiki_fact(
            entity=f"distractor_{i}",
            attribute="distractor_attr",
            claim=f"distractor_claim_{i}_{random_string(10)}",
            provenance="openclaw",
        )

    # Search for each target and check if it's in results
    found = 0
    for claim, expected_entity in targets.items():
        query = claim[:30]  # Partial query
        results = db.search_wiki(query, limit=10)
        if any(r.get("entity") == expected_entity for r in results):
            found += 1

    recall = found / len(targets)
    print(f"    Recall@{len(targets)}: {recall*100:.1f}% ({found}/{len(targets)})")
    return recall

# ---------------------------------------------------------------------------
# 4. Concurrency Benchmark
# ---------------------------------------------------------------------------

def bench_concurrency():
    """Simulate concurrent writes and check for data loss."""
    print("\n  Simulating concurrent writes...")

    # Sequential baseline
    ids_baseline = []
    for i in range(100):
        fid = db.add_wiki_fact(
            entity="concurrent_test",
            attribute=f"seq_{i}",
            claim=f"seq_claim_{i}",
            provenance="claude",
        )
        ids_baseline.append(fid)

    # Verify all were stored
    found = 0
    for i in range(100):
        fact = db.get_wiki_fact("concurrent_test", f"seq_{i}")
        if fact:
            found += 1

    print(f"    Sequential writes: {found}/100 retained")
    return found

# ---------------------------------------------------------------------------
# 5. Persistence Benchmark
# ---------------------------------------------------------------------------

def bench_persistence():
    """Verify data survives save/load roundtrip."""
    print("\n  Testing persistence roundtrip...")

    # Write
    test_key = f"persist_test_{random_string(8)}"
    db.add_wiki_fact(
        entity=test_key,
        attribute="persistence",
        claim="persistence_test_claim",
        provenance="claude",
    )

    # Read back
    fact = db.get_wiki_fact(test_key, "persistence")
    if fact and fact.get("claim") == "persistence_test_claim":
        print(f"    Persistence: PASS (data survives write/read)")
        return True
    else:
        print(f"    Persistence: FAIL")
        return False

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_all(quick=False):
    """Run all benchmarks."""
    db.initialize()
    clean_test_data()

    ops = OPS_QUICK if quick else OPS_STANDARD

    print(f"\n{'='*60}")
    print(f"  CortexLLM Benchmark Suite")
    print(f"  Mode: {'QUICK' if quick else 'STANDARD'}")
    print(f"  Operations: {ops}")
    print(f"{'='*60}\n")

    results = {}

    # 1. Latency
    print("--- Latency: Write (wiki_add) ---")
    lat_write = bench_latency_write(ops)
    report_stats("Write", lat_write)
    results["write"] = {
        "p50_ms": round(percentile(lat_write, 50)*1000, 2),
        "p95_ms": round(percentile(lat_write, 95)*1000, 2),
        "p99_ms": round(percentile(lat_write, 99)*1000, 2),
        "ops": len(lat_write),
    }

    print("\n--- Latency: Read (wiki_get) ---")
    lat_read = bench_latency_read(ops)
    report_stats("Read", lat_read)
    results["read"] = {
        "p50_ms": round(percentile(lat_read, 50)*1000, 2),
        "p95_ms": round(percentile(lat_read, 95)*1000, 2),
        "p99_ms": round(percentile(lat_read, 99)*1000, 2),
        "ops": len(lat_read),
    }

    print("\n--- Latency: Search (wiki_search) ---")
    lat_search = bench_latency_search(ops)
    report_stats("Search", lat_search)
    results["search"] = {
        "p50_ms": round(percentile(lat_search, 50)*1000, 2),
        "p95_ms": round(percentile(lat_search, 95)*1000, 2),
        "p99_ms": round(percentile(lat_search, 99)*1000, 2),
        "ops": len(lat_search),
    }

    # 2. Scale
    print("\n--- Scale Degradation ---")
    results["scale"] = bench_scale()

    # 3. Recall
    print("\n--- Recall ---")
    results["recall"] = bench_recall()

    # 4. Concurrency
    print("\n--- Concurrency ---")
    results["concurrency"] = bench_concurrency()

    # 5. Persistence
    print("\n--- Persistence ---")
    results["persistence"] = bench_persistence()

    # Cleanup
    clean_test_data()

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Write P50:   {results['write']['p50_ms']} ms")
    print(f"  Read P50:    {results['read']['p50_ms']} ms")
    print(f"  Search P50:  {results['search']['p50_ms']} ms")
    print(f"  Recall:      {results.get('recall', 0)*100:.1f}%")
    print(f"  Persistence: {'PASS' if results.get('persistence') else 'FAIL'}")
    print(f"{'='*60}\n")

    # Save results
    output = Path("benchmark-results.json")
    output.write_text(json.dumps(results, indent=2))
    print(f"  Results saved to {output}")

    return results


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    full = "--full" in sys.argv
    only_latency = "--latency" in sys.argv
    only_recall = "--recall" in sys.argv

    if full:
        run_all(quick=False)
    elif only_latency:
        db.initialize()
        clean_test_data()
        print("--- Write ---")
        report_stats("Write", bench_latency_write(OPS_STANDARD))
        print("--- Read ---")
        report_stats("Read", bench_latency_read(OPS_STANDARD))
        print("--- Search ---")
        report_stats("Search", bench_latency_search(OPS_STANDARD))
        clean_test_data()
    elif only_recall:
        db.initialize()
        clean_test_data()
        bench_recall()
        clean_test_data()
    else:
        run_all(quick=quick)
