import pytest
import time
from backend.app.core.algorithms import (
    EpisodicMemoryIndex,
    PriorityTriageQueue,
    ServiceTopologyGraph,
    ErrorSignatureTrie
)


# ============================================================================
# Vector Similarity Index Tests
# ============================================================================

def test_episodic_memory_index_exact_match():
    index = EpisodicMemoryIndex()
    index.add_document("doc1", "Postgres database connection pool exhausted", {"title": "DB Pool"})
    index.add_document("doc2", "Redis cache eviction memory full error", {"title": "Redis OOM"})
    index.add_document("doc3", "Kafka rebalance lag in consumer group", {"title": "Kafka Lag"})

    results = index.search_similar("connection pool exhausted in database", top_k=2)
    assert len(results) > 0
    assert results[0]["incident_id"] == "doc1"
    assert results[0]["similarity_score"] > 0.3


def test_episodic_memory_index_empty_query():
    index = EpisodicMemoryIndex()
    index.add_document("doc1", "Network timeout error", {})
    results = index.search_similar("", top_k=2)
    assert results == []


def test_episodic_memory_ranking_order():
    index = EpisodicMemoryIndex()
    index.add_document("d1", "dns resolution failed in coredns pod", {"title": "DNS"})
    index.add_document("d2", "payment provider dns timeout during checkout", {"title": "Payment DNS"})
    index.add_document("d3", "disk space full on log partition", {"title": "Disk"})

    results = index.search_similar("coredns dns resolution timeout", top_k=3)
    assert len(results) >= 2
    # The first result should be either d1 or d2, having higher score than d3
    top_ids = [r["incident_id"] for r in results]
    assert "d1" in top_ids[:2]
    assert "d3" not in top_ids[:1]


# ============================================================================
# Priority Queue (Max-Heap) Tests
# ============================================================================

def test_priority_triage_queue_ordering():
    queue = PriorityTriageQueue()
    now = time.time()

    # Low severity, Tier 3, few users
    queue.push("inc-low", "Minor UI glitch", "LOW", "TIER_3", 10, now)
    # Critical severity, Tier 0, high users
    queue.push("inc-crit", "Payment Gateway Down", "CRITICAL", "TIER_0", 15000, now + 1)
    # High severity, Tier 1, medium users
    queue.push("inc-high", "Auth Latency High", "HIGH", "TIER_1", 2000, now + 2)

    top = queue.pop()
    assert top is not None
    assert top.incident_id == "inc-crit"

    second = queue.pop()
    assert second is not None
    assert second.incident_id == "inc-high"

    third = queue.pop()
    assert third is not None
    assert third.incident_id == "inc-low"


def test_priority_triage_soft_delete():
    queue = PriorityTriageQueue()
    queue.push("inc-1", "Alert 1", "HIGH", "TIER_1", 100, time.time())
    queue.push("inc-2", "Alert 2", "CRITICAL", "TIER_0", 1000, time.time())

    assert queue.size() == 2
    removed = queue.remove("inc-2")
    assert removed is True
    assert queue.size() == 1

    remaining = queue.pop()
    assert remaining is not None
    assert remaining.incident_id == "inc-1"


# ============================================================================
# Graph Blast Radius & Cycle Detection Tests
# ============================================================================

def test_service_topology_blast_radius():
    graph = ServiceTopologyGraph()
    # A depends on B; B depends on C
    # When C fails: B is impacted, then A is impacted
    graph.add_service("A", "TIER_1")
    graph.add_service("B", "TIER_1")
    graph.add_service("C", "TIER_0")

    graph.add_dependency("A", "B")
    graph.add_dependency("B", "C")

    blast = graph.calculate_blast_radius("C")
    assert blast["origin_service"] == "C"
    assert blast["total_impacted_services"] == 2
    impacted_names = [item["service"] for item in blast["impacted_services"]]
    assert "B" in impacted_names
    assert "A" in impacted_names
    assert blast["max_depth"] == 2


def test_service_topology_cycle_detection():
    graph = ServiceTopologyGraph()
    graph.add_service("svc-x")
    graph.add_service("svc-y")
    graph.add_service("svc-z")

    # Create cycle: X -> Y -> Z -> X
    graph.add_dependency("svc-x", "svc-y")
    graph.add_dependency("svc-y", "svc-z")
    graph.add_dependency("svc-z", "svc-x")

    cycles = graph.detect_cycles()
    assert len(cycles) > 0


# ============================================================================
# Trie Error Signature Tests
# ============================================================================

def test_error_signature_trie():
    trie = ErrorSignatureTrie()
    trie.insert("err_503", "SERVICE_UNAVAILABLE", "CRITICAL")
    trie.insert("oom_killed", "MEMORY_EXHAUSTION", "CRITICAL")
    trie.insert("err_500", "INTERNAL_ERROR", "HIGH")

    match1 = trie.match_prefix("err_503_connection_refused")
    assert match1 is not None
    assert match1[0] == "SERVICE_UNAVAILABLE"
    assert match1[1] == "CRITICAL"

    match_none = trie.match_prefix("info_log_normal")
    assert match_none is None

    log_line = "2026-11-09T12:00:00Z pod container was oom_killed while handling request"
    matches = trie.scan_log_line(log_line)
    assert len(matches) == 1
    assert matches[0][1] == "MEMORY_EXHAUSTION"
