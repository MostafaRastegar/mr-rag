---
name: mr-rag-10-rag-pipeline
description: Retrieval-Augmented Generation pipeline with caching, streaming, and token reduction
---

# mr-rag-10-rag-pipeline

## Usage

Use this skill when modifying the RAG pipeline, adding new retrieval/generation steps, tuning token reduction parameters, or understanding the cache flow.

## Steps

1. Check exact-match cache first (fastest, no embedding needed)
2. Embed the question
3. Check semantic cache (embedding similarity)
4. Search vector store with query embedding
5. Filter low-relevance chunks using `retrieval_min_score` (default: 0.15)
6. Build context from filtered chunks
7. Call LLM with system prompt and context via LangChain ChatPromptTemplate
8. Store result in both exact and semantic caches

## Pipeline Flow

```
Question
→ [Exact Cache Check] → HIT → return cached Answer
→ MISS:
  → Embedding API
  → [Semantic Cache Check] (cosine ≥ 0.92) → HIT → return cached Answer
  → MISS:
    → ChromaDB search (top_k=3)
    → Filter low-relevance (min_score=0.15)
    → Build context from filtered chunks
    → LLM API (via ChatPromptTemplate)
    → Store in both caches
    → return Answer
```

## Prompt Templates (LangChain ChatPromptTemplate)

All prompts use `ChatPromptTemplate.from_messages()` for structured composition:

```python
from langchain_core.prompts import ChatPromptTemplate

STRICT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant..."),
    ("human", "Context:\n{context}\n\nQuestion: {question}\n\n"
              "Answer based only on the context above:"),
])

LOOSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant..."),
    ("human", "Context:\n{context}\n\nQuestion: {question}\n\n"
              "Use the context as your primary source..."),
])

GENERAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant..."),
    ("human", "Question: {question}"),
])
```

## Prompt Selection Logic

```python
# Select the appropriate prompt based on context availability and cascade stage
if context and not use_loose_prompt:
    formatted = STRICT_PROMPT.format_messages(context=context, question=question)
elif context and use_loose_prompt:
    formatted = LOOSE_PROMPT.format_messages(context=context, question=question)
elif not context and use_loose_prompt:
    formatted = GENERAL_PROMPT.format_messages(question=question)
else:
    formatted = NO_CONTEXT_PROMPT.format_messages(question=question)

# Convert to domain Message objects
messages = [
    Message(role=msg.type, content=str(msg.content))
    for msg in formatted
]
```

## Token Reduction

```python
min_score = settings.retrieval_min_score  # default: 0.15
if min_score > 0:
    filtered = [r for r in results if r.score >= min_score]
    results = filtered if filtered else results[:1]
```

## Context Building

```python
def _build_context(self, results: List[SearchResult]) -> str:
    context_parts = []
    for i, result in enumerate(results, 1):
        context_parts.append(f"[Document {i}] {result.chunk.text}")
    return "\n\n".join(context_parts)
```

## No Results Handling

```python
if not results:
    answer = Answer(text="I couldn't find any relevant information to answer your question.", sources=[])
    if self._cache is not None:
        self._cache.update(question, llm_string, json.dumps({"text": answer.text}))
    return answer
```

## Query Expansion (Stage 2)

Uses LangChain `ChatPromptTemplate` for the expansion prompt:

```python
QUERY_EXPANSION_CHAT = ChatPromptTemplate.from_messages([
    ("system", "Rewrite the following question in {count} different ways..."),
    ("human", "{question}"),
])

def _expand_query(self, question: str) -> List[str]:
    formatted = QUERY_EXPANSION_CHAT.format_messages(
        count=str(count), question=question
    )
    messages = [
        Message(role=msg.type, content=str(msg.content))
        for msg in formatted
    ]
    raw = self._llm.generate(messages, temperature=0.7, max_tokens=512)
    # Parse lines, deduplicate, return variants
```

## LangChain Priority Rule

When adding new prompt logic or message construction:
1. Always use `ChatPromptTemplate.from_messages()` for prompt templates
2. Use `format_messages()` to build message lists
3. Use `StrOutputParser` from `langchain_core.output_parsers` for parsing
4. Only fall back to manual string formatting if LangChain's template system cannot express the pattern

## Should / Should Not

✅ Do: Check exact-match cache first (fastest — no embedding API call)
✅ Do: Cache "no results" answers to avoid repeated empty searches
✅ Do: Validate cached JSON structure with try/except
✅ Do: Use LangChain ChatPromptTemplate for all prompt construction
✅ Do: Use `format_messages()` to generate typed messages
❌ Don't: Include sources in cached answers — sources are not stored
❌ Don't: Forget to check `cache_semantic_enabled` before semantic lookup
❌ Don't: Use raw f-strings for prompt templates when ChatPromptTemplate is available