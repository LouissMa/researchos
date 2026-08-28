"""Frozen benchmark corpus — 19 papers across four topical clusters.

Do **not** edit lightly: ``benchmarks/scenarios.json`` gold sets and the eval CI
thresholds are keyed to these titles. The corpus is deliberately small and topical so
offline eval with the deterministic local embeddings is meaningful and fast.
"""

PAPERS = [
    # ---- Topic A: LLM agent memory -------------------------------------
    {
        "source": "arxiv",
        "source_id": "2401.00001",
        "title": "Long-Term Memory Architectures for LLM Agents",
        "abstract": "We study long-term memory mechanisms enabling language model agents to "
        "retain and retrieve knowledge across sessions using vector memory.",
        "authors": ["A. One"],
        "url": "http://arxiv.org/abs/2401.00001",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00002",
        "title": "Episodic Memory and Reflection in Autonomous Agents",
        "abstract": "A framework for episodic memory, reflection, and consolidation in "
        "autonomous agents built on large language models.",
        "authors": ["B. Two"],
        "url": "http://arxiv.org/abs/2401.00002",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00003",
        "title": "Memory-Augmented Language Models for Continual Tasks",
        "abstract": "Memory-augmented language models that accumulate episodic knowledge for "
        "continual learning of new tasks without catastrophic forgetting.",
        "authors": ["C. Three"],
        "url": "http://arxiv.org/abs/2401.00003",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00004",
        "title": "Salience-Based Forgetting in Agent Memory Systems",
        "abstract": "We propose salience decay policies that let agent memory systems forget "
        "low-value items while preserving pinned knowledge across long horizons.",
        "authors": ["D. Four"],
        "url": "http://arxiv.org/abs/2401.00004",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00005",
        "title": "Semantic Memory Consolidation for Conversational Agents",
        "abstract": "Consolidation of episodic traces into semantic memory concepts improves "
        "the long-term knowledge retention of conversational agents.",
        "authors": ["E. Five"],
        "url": "http://arxiv.org/abs/2401.00005",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00006",
        "title": "Working Memory Management for Multi-Turn LLM Assistants",
        "abstract": "Efficient working memory management lets multi-turn language model "
        "assistants keep salient context while respecting token budgets.",
        "authors": ["F. Six"],
        "url": "http://arxiv.org/abs/2401.00006",
    },
    # ---- Topic B: retrieval-augmented generation -----------------------
    {
        "source": "arxiv",
        "source_id": "2402.00001",
        "title": "Retrieval-Augmented Generation: A Survey",
        "abstract": "A survey of retrieval-augmented generation methods combining dense "
        "retrieval with generative language models for knowledge-intensive tasks.",
        "authors": ["G. Seven"],
        "url": "http://arxiv.org/abs/2402.00001",
    },
    {
        "source": "arxiv",
        "source_id": "2402.00002",
        "title": "Dense Passage Retrieval for Open-Domain Question Answering",
        "abstract": "Dense passage retrieval learns vector representations of passages and "
        "questions, dramatically improving retrieval-augmented generation pipelines for "
        "knowledge-intensive open-domain question answering.",
        "authors": ["H. Eight"],
        "url": "http://arxiv.org/abs/2402.00002",
    },
    {
        "source": "arxiv",
        "source_id": "2402.00003",
        "title": "Fusion-in-Decoder for Generative QA over Retrieved Passages",
        "abstract": "A fusion-in-decoder architecture that attends jointly over retrieved "
        "passages to generate accurate answers for retrieval-augmented generation on "
        "knowledge-intensive question answering tasks.",
        "authors": ["I. Nine"],
        "url": "http://arxiv.org/abs/2402.00003",
    },
    {
        "source": "arxiv",
        "source_id": "2402.00004",
        "title": "Self-RAG: Learning to Retrieve, Generate, and Critique",
        "abstract": "Self-RAG trains a language model to decide when to retrieve, generating "
        "with self-reflective critique tokens for retrieval-augmented generation on "
        "knowledge-intensive tasks.",
        "authors": ["J. Ten"],
        "url": "http://arxiv.org/abs/2402.00004",
    },
    {
        "source": "arxiv",
        "source_id": "2402.00005",
        "title": "Adaptive Retrieval in Long-Context Language Models",
        "abstract": "Adaptive retrieval schedules selective retrieval within long-context "
        "language models, reducing cost while keeping retrieval-augmented generation "
        "quality high on knowledge-intensive tasks.",
        "authors": ["K. Eleven"],
        "url": "http://arxiv.org/abs/2402.00005",
    },
    # ---- Topic C: knowledge graphs -------------------------------------
    {
        "source": "arxiv",
        "source_id": "2403.00001",
        "title": "Knowledge Graphs for Multi-Hop Reasoning in LLMs",
        "abstract": "Leveraging knowledge graphs enables language models to perform multi-hop "
        "reasoning over structured relations with verifiable paths.",
        "authors": ["L. Twelve"],
        "url": "http://arxiv.org/abs/2403.00001",
    },
    {
        "source": "arxiv",
        "source_id": "2403.00002",
        "title": "GraphRAG: Combining Knowledge Graphs with Retrieval-Augmented Generation",
        "abstract": "GraphRAG augments retrieval-augmented generation with knowledge graph "
        "structure, improving grounded multi-hop reasoning for language models on "
        "private corpora.",
        "authors": ["M. Thirteen"],
        "url": "http://arxiv.org/abs/2403.00002",
    },
    {
        "source": "arxiv",
        "source_id": "2403.00003",
        "title": "Querying Knowledge Graphs with Natural Language",
        "abstract": "Translating natural language questions into structured queries over "
        "knowledge graphs enables multi-hop reasoning and unlocks answerable analytics "
        "for non-experts.",
        "authors": ["N. Fourteen"],
        "url": "http://arxiv.org/abs/2403.00003",
    },
    {
        "source": "arxiv",
        "source_id": "2403.00004",
        "title": "Neural Graph Databases for Reasoning over Learned Graphs",
        "abstract": "Neural graph databases learn to reason over large-scale graph structures, "
        "generalizing classical query engines and boosting multi-hop reasoning for "
        "language models.",
        "authors": ["O. Fifteen"],
        "url": "http://arxiv.org/abs/2403.00004",
    },
    {
        "source": "arxiv",
        "source_id": "2403.00005",
        "title": "Constructing Domain Knowledge Graphs from Scientific Literature",
        "abstract": "Automatic construction of domain-specific knowledge graphs from scientific "
        "literature via entity and relation extraction with provenance tracking, enabling "
        "multi-hop reasoning over scientific claims.",
        "authors": ["P. Sixteen"],
        "url": "http://arxiv.org/abs/2403.00005",
    },
    # ---- Topic D: vector databases -------------------------------------
    {
        "source": "arxiv",
        "source_id": "2404.00001",
        "title": "Benchmarking Vector Databases for Semantic Search",
        "abstract": "A benchmark of vector database backends for semantic search workloads, "
        "measuring recall, latency, and scalability on dense embeddings.",
        "authors": ["Q. Seventeen"],
        "url": "http://arxiv.org/abs/2404.00001",
    },
    {
        "source": "arxiv",
        "source_id": "2404.00002",
        "title": "Approximate Nearest Neighbor Search in Vector Databases",
        "abstract": "Approximate nearest neighbor algorithms power vector database search; we "
        "survey index structures and trade-offs for semantic retrieval.",
        "authors": ["R. Eighteen"],
        "url": "http://arxiv.org/abs/2404.00002",
    },
    {
        "source": "arxiv",
        "source_id": "2404.00003",
        "title": "Hybrid Vector Search with Metadata Filtering",
        "abstract": "Combining dense vector search with structured metadata filtering improves "
        "precision in semantic search over heterogeneous document collections.",
        "authors": ["S. Nineteen"],
        "url": "http://arxiv.org/abs/2404.00003",
    },
]

# Frozen cluster structure used to build the knowledge graph for eval.
CLUSTERS = [
    {
        "id": "cA",
        "label": "agent memory",
        "keywords": ["memory", "agents", "language", "models"],
        "titles": [
            "Long-Term Memory Architectures for LLM Agents",
            "Episodic Memory and Reflection in Autonomous Agents",
            "Memory-Augmented Language Models for Continual Tasks",
            "Salience-Based Forgetting in Agent Memory Systems",
            "Semantic Memory Consolidation for Conversational Agents",
            "Working Memory Management for Multi-Turn LLM Assistants",
        ],
    },
    {
        "id": "cB",
        "label": "retrieval-augmented generation",
        "keywords": ["retrieval", "generation", "passages", "question"],
        "titles": [
            "Retrieval-Augmented Generation: A Survey",
            "Dense Passage Retrieval for Open-Domain Question Answering",
            "Fusion-in-Decoder for Generative QA over Retrieved Passages",
            "Self-RAG: Learning to Retrieve, Generate, and Critique",
            "Adaptive Retrieval in Long-Context Language Models",
        ],
    },
    {
        "id": "cC",
        "label": "knowledge graphs",
        "keywords": ["knowledge", "graphs", "reasoning", "relations"],
        "titles": [
            "Knowledge Graphs for Multi-Hop Reasoning in LLMs",
            "GraphRAG: Combining Knowledge Graphs with Retrieval-Augmented Generation",
            "Querying Knowledge Graphs with Natural Language",
            "Neural Graph Databases for Reasoning over Learned Graphs",
            "Constructing Domain Knowledge Graphs from Scientific Literature",
        ],
    },
    {
        "id": "cD",
        "label": "vector databases",
        "keywords": ["vector", "databases", "semantic", "search"],
        "titles": [
            "Benchmarking Vector Databases for Semantic Search",
            "Approximate Nearest Neighbor Search in Vector Databases",
            "Hybrid Vector Search with Metadata Filtering",
        ],
    },
]
