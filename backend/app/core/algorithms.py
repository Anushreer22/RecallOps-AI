"""
Core Data Structures and Algorithms for RecallOps-AI.
Covers:
- Vector Similarity Engine (k-NN Cosine Similarity) for Episodic Memory Recall
- Max-Heap Priority Queue for Dynamic Incident Triage
- Directed Acyclic Graph (DAG) for Microservice Topology & Blast Radius Propagation
- Trie (Prefix Tree) for High-throughput Error Signature & Log Token Matching
"""

from __future__ import annotations
import math
import re
import heapq
import threading
from collections import defaultdict, deque
from typing import List, Dict, Tuple, Set, Any, Optional


# ============================================================================
# 1. VECTOR SIMILARITY ENGINE (Cosine Similarity & k-NN Retrieval)
# ============================================================================

class EpisodicMemoryIndex:
    """
    In-memory vector space model implementing TF-IDF tokenization and
    Cosine Similarity k-NN retrieval for fast historical incident recall.
    Synchronized with a re-entrant lock (RLock) for concurrent access.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.doc_vectors: Dict[str, Dict[str, float]] = {}
        self.doc_magnitudes: Dict[str, float] = {}
        self.idf: Dict[str, float] = {}
        self.df: Dict[str, int] = defaultdict(int)
        self.total_docs: int = 0

    def clear(self) -> None:
        """Resets the vector index and document collection completely."""
        with self._lock:
            self.documents.clear()
            self.doc_vectors.clear()
            self.doc_magnitudes.clear()
            self.idf.clear()
            self.df.clear()
            self.total_docs = 0

    def _tokenize(self, text: str) -> List[str]:
        """Normalize and tokenize log/incident text."""
        return re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())

    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        tf: Dict[str, float] = defaultdict(float)
        for token in tokens:
            tf[token] += 1.0
        total = float(len(tokens)) if tokens else 1.0
        for token in tf:
            tf[token] = tf[token] / total
        return tf

    def _recalculate_idf(self):
        """Recompute inverse document frequencies across indexed incidents."""
        self.idf.clear()
        for term, doc_count in self.df.items():
            # Standard smooth IDF formula
            self.idf[term] = math.log((self.total_docs + 1) / (doc_count + 1)) + 1.0

        # Update all doc vectors and precompute magnitudes
        for doc_id, data in self.documents.items():
            tokens = data["tokens"]
            tf = self._compute_tf(tokens)
            vector: Dict[str, float] = {}
            squared_sum = 0.0
            for term, tf_val in tf.items():
                tfidf_val = tf_val * self.idf.get(term, 1.0)
                vector[term] = tfidf_val
                squared_sum += tfidf_val * tfidf_val
            
            self.doc_vectors[doc_id] = vector
            self.doc_magnitudes[doc_id] = math.sqrt(squared_sum) or 1.0

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> None:
        """Indexes an incident text into the vector memory space."""
        with self._lock:
            tokens = self._tokenize(text)
            unique_terms = set(tokens)
            
            # If doc_id already exists, cleanly remove previous document term frequencies
            # to prevent duplicate counting and artificial IDF inflation
            if doc_id in self.documents:
                old_tokens = set(self.documents[doc_id]["tokens"])
                for term in old_tokens:
                    if self.df[term] > 1:
                        self.df[term] -= 1
                    else:
                        self.df.pop(term, None)
                self.total_docs -= 1

            for term in unique_terms:
                self.df[term] += 1

            self.documents[doc_id] = {
                "text": text,
                "tokens": tokens,
                "metadata": metadata
            }
            self.total_docs += 1
            self._recalculate_idf()

    def cosine_similarity(self, vec_a: Dict[str, float], mag_a: float,
                          vec_b: Dict[str, float], mag_b: float) -> float:
        """
        Computes cosine similarity between two sparse vector representations:
        cos(theta) = (A . B) / (||A|| * ||B||)
        """
        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0
        
        # Iterate over the smaller dictionary for optimal O(min(|A|, |B|))
        if len(vec_a) > len(vec_b):
            vec_a, vec_b = vec_b, vec_a

        dot_product = sum(val * vec_b.get(term, 0.0) for term, val in vec_a.items())
        raw_score = dot_product / (mag_a * mag_b)
        return min(1.0, max(0.0, raw_score))

    def search_similar(self, query_text: str, top_k: int = 3, threshold: float = 0.05) -> List[Dict[str, Any]]:
        """
        Retrieves the top-k most similar incidents using k-NN with a min-heap.
        Time Complexity: O(N * |Q| + N log k)
        """
        with self._lock:
            query_tokens = self._tokenize(query_text)
            if not query_tokens or self.total_docs == 0:
                return []

            query_tf = self._compute_tf(query_tokens)
            query_vec: Dict[str, float] = {}
            squared_sum = 0.0
            for term, tf_val in query_tf.items():
                tfidf_val = tf_val * self.idf.get(term, 1.0)
                query_vec[term] = tfidf_val
                squared_sum += tfidf_val * tfidf_val

            query_mag = math.sqrt(squared_sum) or 1.0

            # Min-heap to maintain top-k elements: elements stored as (score, doc_id)
            heap: List[Tuple[float, str]] = []

            for doc_id, doc_vec in self.doc_vectors.items():
                doc_mag = self.doc_magnitudes[doc_id]
                score = self.cosine_similarity(query_vec, query_mag, doc_vec, doc_mag)
                
                if score >= threshold:
                    if len(heap) < top_k:
                        heapq.heappush(heap, (score, doc_id))
                    elif score > heap[0][0]:
                        heapq.heapreplace(heap, (score, doc_id))

            # Sort descending by score
            results = []
            for score, doc_id in sorted(heap, key=lambda x: x[0], reverse=True):
                doc_info = self.documents[doc_id]
                results.append({
                    "incident_id": doc_id,
                    "similarity_score": round(score, 4),
                    "text": doc_info["text"],
                    "metadata": doc_info["metadata"]
                })

            return results


# ============================================================================
# 2. PRIORITY QUEUE / MAX-HEAP (Dynamic Incident Triage)
# ============================================================================

class TriageItem:
    """Encapsulates an incident with its calculated priority score for heap sorting."""
    
    SEVERITY_WEIGHTS = {"CRITICAL": 100.0, "HIGH": 75.0, "MEDIUM": 50.0, "LOW": 20.0}
    CRITICALITY_WEIGHTS = {"TIER_0": 100.0, "TIER_1": 70.0, "TIER_2": 40.0, "TIER_3": 10.0}

    def __init__(self, incident_id: str, title: str, severity: str,
                 service_tier: str, impacted_users: int, timestamp: float):
        self.incident_id = incident_id
        self.title = title
        self.severity = severity.upper()
        self.service_tier = service_tier.upper()
        self.impacted_users = impacted_users
        self.timestamp = timestamp
        self.score = self._compute_score()

    def _compute_score(self) -> float:
        """
        Multivariate priority score calculation:
        Score = 0.40 * Sev + 0.30 * Tier + 0.20 * Log(Impact+1) + 0.10 * Urgency
        """
        sev_score = self.SEVERITY_WEIGHTS.get(self.severity, 30.0)
        tier_score = self.CRITICALITY_WEIGHTS.get(self.service_tier, 20.0)
        user_impact_score = min(100.0, math.log10(max(1, self.impacted_users) + 1) * 20.0)
        
        return round((0.40 * sev_score) + (0.30 * tier_score) + (0.20 * user_impact_score), 2)

    def __lt__(self, other: TriageItem) -> bool:
        # Higher score takes priority (Max-heap behavior in Python's min-heap via inverted comparator)
        if self.score != other.score:
            return self.score > other.score
        # Tie-breaker: older timestamp comes first
        return self.timestamp < other.timestamp


class PriorityTriageQueue:
    """Thread-safe max-heap queue for active incident triage synchronized with RLock."""

    def __init__(self):
        self._lock = threading.RLock()
        self._heap: List[TriageItem] = []
        self._entry_map: Dict[str, TriageItem] = {}

    def push(self, incident_id: str, title: str, severity: str,
             service_tier: str, impacted_users: int, timestamp: float) -> TriageItem:
        with self._lock:
            item = TriageItem(incident_id, title, severity, service_tier, impacted_users, timestamp)
            heapq.heappush(self._heap, item)
            self._entry_map[incident_id] = item
            return item

    def pop(self) -> Optional[TriageItem]:
        with self._lock:
            while self._heap:
                item = heapq.heappop(self._heap)
                if item.incident_id in self._entry_map:
                    del self._entry_map[item.incident_id]
                    return item
            return None

    def peek(self) -> Optional[TriageItem]:
        with self._lock:
            while self._heap:
                item = self._heap[0]
                if item.incident_id in self._entry_map:
                    return item
                heapq.heappop(self._heap)
            return None

    def remove(self, incident_id: str) -> bool:
        """Soft-removes an incident when resolved or acknowledged."""
        with self._lock:
            if incident_id in self._entry_map:
                del self._entry_map[incident_id]
                return True
            return False

    def list_all_sorted(self) -> List[Dict[str, Any]]:
        """Returns all items currently in queue sorted by highest priority."""
        with self._lock:
            valid_items = [item for item in self._heap if item.incident_id in self._entry_map]
            sorted_items = sorted(valid_items, key=lambda x: (x.score, -x.timestamp), reverse=True)
            return [
                {
                    "incident_id": it.incident_id,
                    "title": it.title,
                    "severity": it.severity,
                    "service_tier": it.service_tier,
                    "impacted_users": it.impacted_users,
                    "score": it.score,
                    "timestamp": it.timestamp
                }
                for it in sorted_items
            ]

    def size(self) -> int:
        with self._lock:
            return len(self._entry_map)


# ============================================================================
# 3. DIRECTED ACYCLIC GRAPH (DAG) - Service Topology & Blast Radius Analysis
# ============================================================================

class ServiceTopologyGraph:
    """
    Directed Graph representing microservice dependencies.
    Used for:
    - Blast radius estimation (Breadth-First Search downstream)
    - Root cause failure path isolation (Topological ordering & upstream DFS)
    - Cyclic dependency detection (Tarjan's / 3-color DFS)
    """

    def __init__(self):
        # adjacency: service -> set of services that depend on it (downstream dependents)
        self.downstream: Dict[str, Set[str]] = defaultdict(set)
        # reverse adjacency: service -> dependencies it relies upon (upstream dependencies)
        self.upstream: Dict[str, Set[str]] = defaultdict(set)
        self.node_metadata: Dict[str, Dict[str, Any]] = {}

    def add_service(self, service_name: str, tier: str = "TIER_1", owner: str = "SRE") -> None:
        self.node_metadata[service_name] = {"tier": tier, "owner": owner}

    def add_dependency(self, source_service: str, target_service: str) -> None:
        """
        source_service depends on target_service.
        If target_service fails, source_service is impacted downstream.
        """
        self.upstream[source_service].add(target_service)
        self.downstream[target_service].add(source_service)
        if source_service not in self.node_metadata:
            self.add_service(source_service)
        if target_service not in self.node_metadata:
            self.add_service(target_service)

    def calculate_blast_radius(self, failed_service: str) -> Dict[str, Any]:
        """
        Calculates downstream services impacted if `failed_service` fails,
        using BFS with distance/hop penalty.
        Time Complexity: O(V + E)
        """
        if failed_service not in self.node_metadata and failed_service not in self.downstream:
            return {
                "origin_service": failed_service,
                "total_impacted_services": 0,
                "impacted_services": [],
                "max_depth": 0
            }

        visited: Set[str] = {failed_service}
        queue: deque[Tuple[str, int]] = deque([(failed_service, 0)])
        impacted: List[Dict[str, Any]] = []
        max_depth = 0

        while queue:
            curr_service, depth = queue.popleft()
            max_depth = max(max_depth, depth)

            for neighbor in self.downstream.get(curr_service, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    tier = self.node_metadata.get(neighbor, {}).get("tier", "TIER_2")
                    owner = self.node_metadata.get(neighbor, {}).get("owner", "Engineering")
                    impacted.append({
                        "service": neighbor,
                        "hop_distance": depth + 1,
                        "tier": tier,
                        "owner": owner,
                        "impact_weight": round(1.0 / (depth + 1), 2)
                    })
                    queue.append((neighbor, depth + 1))

        return {
            "origin_service": failed_service,
            "total_impacted_services": len(impacted),
            "impacted_services": impacted,
            "max_depth": max_depth
        }

    def detect_cycles(self) -> List[List[str]]:
        """
        Detects circular dependencies in architecture using DFS 3-color marking.
        Colors: 0=WHITE (unvisited), 1=GREY (currently in recursion stack), 2=BLACK (visited).
        """
        WHITE, GREY, BLACK = 0, 1, 2
        colors: Dict[str, int] = {node: WHITE for node in self.node_metadata}
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(node: str):
            colors[node] = GREY
            path.append(node)
            for dep in self.upstream.get(node, []):
                if colors.get(dep, WHITE) == GREY:
                    # Cycle detected: extract subpath
                    idx = path.index(dep)
                    cycles.append(path[idx:] + [dep])
                elif colors.get(dep, WHITE) == WHITE:
                    dfs(dep)
            path.pop()
            colors[node] = BLACK

        for node in list(self.node_metadata.keys()):
            if colors[node] == WHITE:
                dfs(node)

        return cycles


# ============================================================================
# 4. TRIE (Prefix Tree for High-Throughput Log Token & Error Matching)
# ============================================================================

class TrieNode:
    def __init__(self):
        self.children: Dict[str, TrieNode] = {}
        self.is_terminal: bool = False
        self.category: Optional[str] = None
        self.severity: Optional[str] = None


class ErrorSignatureTrie:
    """
    Prefix tree for fast string search and matching of error signatures in log streams.
    Time Complexity: O(L) where L is length of error string.
    """

    def __init__(self):
        self.root = TrieNode()

    def insert(self, pattern: str, category: str, severity: str = "HIGH") -> None:
        node = self.root
        for char in pattern.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_terminal = True
        node.category = category
        node.severity = severity

    def match_prefix(self, text: str) -> Optional[Tuple[str, str]]:
        """Matches prefix against registered error patterns."""
        node = self.root
        for char in text.lower():
            if char not in node.children:
                break
            node = node.children[char]
            if node.is_terminal:
                return (node.category, node.severity)
        return None

    def scan_log_line(self, log_line: str) -> List[Tuple[str, str, str]]:
        """
        Scans a raw log line and extracts all matched error signatures.
        Returns: list of (matched_pattern, category, severity)
        """
        matches = []
        tokens = log_line.split()
        for token in tokens:
            result = self.match_prefix(token)
            if result:
                matches.append((token, result[0], result[1]))
        return matches
