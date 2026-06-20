---
name: mr-rag-09-ingestion-pipeline
description: Document processing pipeline — Load, Split, Embed, Store
---

# mr-rag-09-ingestion-pipeline

## Usage

Use this skill when modifying the ingestion pipeline, adding a new document source, changing chunking parameters, or troubleshooting ingestion issues.

## Steps

1. Load documents from source using `DocumentLoaderPort` (LangChain-based adapters)
2. Split documents into chunks using `TextSplitterPort` (LangChain RecursiveCharacterTextSplitter)
3. Generate embeddings for each chunk using `EmbeddingPort`
4. Validate that embedding count matches chunk count
5. Store chunks with embeddings in `VectorStorePort`

## Pipeline Flow

```
JSON File → JsonDocumentLoader (LangChain JSONLoader)
         → List[Document]
         → LangChainTextSplitter.split() (RecursiveCharacterTextSplitter)
         → List[Chunk]
         → OpenRouterEmbedding.embed_documents()
         → List[List[float]]
         → ChromaVectorStore.add()
         → int (count)
```

## Document Loaders (LangChain-based)

All document loaders implement `DocumentLoaderPort` and use LangChain internally:

| Loader | LangChain Component | File Format | Features |
|--------|-------------------|-------------|----------|
| `JsonDocumentLoader` | `JSONLoader` with jq schema + `metadata_func` | `.json` | Auto-detects content key from priority list; normalizes wrapped/string structures via temp file |
| `MarkdownDocumentLoader` | `MarkdownHeaderTextSplitter` (heading hierarchy) | `.md` | Splits by `#` / `##` / ... / `######` headings |
| `TextDocumentLoader` | `TextLoader` | `.txt` | Single document per file |
| `AutoDocumentLoader` | Composite — dispatches by extension | auto-detect | Delegates to the above based on `.json`, `.md`, `.txt` |

## JsonDocumentLoader Details

The `JsonDocumentLoader` handles a wide variety of JSON structures automatically:

### Content Key Detection (`_detect_content_key`)

Priority list of common content-field keys (checked in order):
`content`, `text`, `body`, `description`, `article`, `markdown`, `html`, `summary`, `text_content`, `page_content`

If none match, falls back to the longest string-valued field. If no string fields exist, defaults to `"content"`.

### JSON Structure Normalization (`_normalize_json_structure`)

| Input | Behavior |
|-------|----------|
| `[{"content": "..."}, ...]` | Used as-is |
| `{"content": "..."}` (single dict) | Wrapped in a list |
| `{"data": [{"body": "..."}]}` | Wrapper key (`data`, `results`, `items`, `documents`, `records`, `recipes`, `posts`, `articles`, `entries`, `rows`) — unwrapped automatically |
| `["str1", "str2", ...]` (list of strings) | Each string converted to `{"content": str}` |
| `"just a string"` (single string) | Converted to `[{"content": "just a string"}]` |

### Temp-file Strategy

Since LangChain's `JSONLoader` re-reads the original file directly, the loader writes normalised records to a temporary file (automatically cleaned up in `finally`) before passing it to `JSONLoader`. This ensures a consistently flat `[{...}, ...]` format regardless of the original structure.

## Code Structure

```python
class IngestionPipeline:
    def __init__(self, loader, splitter, embedding, vector_store):
        self._loader = loader
        self._splitter = splitter
        self._embedding = embedding
        self._vector_store = vector_store
    
    def run(self, file_path: str) -> int:
        documents = self._loader.load(file_path)
        if not documents:
            return 0
        
        chunks = self._splitter.split(documents)
        if not chunks:
            return 0
        
        texts = [chunk.text for chunk in chunks]
        embeddings = self._embedding.embed_documents(texts)
        
        if len(embeddings) != len(chunks):
            raise IngestionError("Embedding count mismatch")
        
        return self._vector_store.add(chunks, embeddings)
```

## Error Handling

Each stage uses its own try/except block:

```python
try:
    embeddings = self._embedding.embed_documents(texts)
except Exception as e:
    logger.error("Embedding generation failed: %s", str(e))
    raise IngestionError(f"Failed to generate embeddings: {e}") from e
```

## LangChain Priority Rule

When adding a new document loader:
1. First check if LangChain provides a suitable loader (`langchain_community.document_loaders`)
2. If found, wrap it behind `DocumentLoaderPort` and convert results to domain models
3. Only write custom parsing if no LangChain loader exists

## Should / Should Not

✅ Do: Validate embedding count matches chunk count before storing
✅ Do: Log progress at each stage
✅ Do: Return early with 0 for empty documents/chunks
✅ Do: Use try/except around each stage independently
✅ Do: Prefer LangChain loaders over custom file parsing
❌ Don't: Add file-format-specific logic in the pipeline
❌ Don't: Skip validation — always check counts match
❌ Don't: Catch exceptions silently — always log and re-raise