"""Ad-hoc probe: inspect dense vs hybrid retrieval for a single query."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.chroma_vector_store import ChromaVectorStore
from app.infrastructure.hybrid_retriever import HybridRetriever
from app.infrastructure.openrouter_embedding import OpenRouterEmbedding

query = sys.argv[1] if len(sys.argv) > 1 else "چطور با تست لامپ سری برد سوئیچینگ را تست کنیم؟"

vs = ChromaVectorStore()
emb = OpenRouterEmbedding()

print(f"QUERY: {query}\n")
print("--- DENSE (top 5 of 20) ---")
vec = emb.embed_query(query)
for i, x in enumerate(vs.search(vec, 20)[:5], 1):
    m = x.chunk.metadata or {}
    print(
        f"{i}. score={x.score:.4f} src={m.get('original_filename')} "
        f"lamp={'lamp' in x.chunk.text.lower()} :: {x.chunk.text[:60]!r}"
    )

print("\n--- HYBRID (top 5 of 20) ---")
h = HybridRetriever(vs)
for i, x in enumerate(h.search(query, vec, 5, 20), 1):
    m = x.chunk.metadata or {}
    print(
        f"{i}. score={x.score:.4f} src={m.get('original_filename')} "
        f"lamp={'lamp' in x.chunk.text.lower()} :: {x.chunk.text[:60]!r}"
    )
