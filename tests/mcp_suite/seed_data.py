import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models
from fastembed import TextEmbedding, SparseTextEmbedding

def seed():
    client = QdrantClient(host="localhost", port=6334)
    collection_name = "sage_docs"
    
    # Ensure collection exists
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": models.VectorParams(size=384, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams()
        }
    )
    
    # Create payload indices for faceting and filtering
    client.create_payload_index(collection_name, "library", models.PayloadSchemaType.KEYWORD)
    client.create_payload_index(collection_name, "file_path", models.PayloadSchemaType.KEYWORD)
    client.create_payload_index(collection_name, "chunk_index", models.PayloadSchemaType.INTEGER)
    
    dense_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    
    docs = [
        {
            "library": "react",
            "version": "18",
            "file_path": "react/18/reconciliation.md",
            "content": "React 18 reconciliation uses the Fiber architecture. The diffing algorithm compares the Virtual DOM trees to minimize updates. key concepts include Fiber, Virtual DOM, and Diffing.",
            "chunk_index": 0
        },
        {
            "library": "vue",
            "version": "latest",
            "file_path": "vue/latest/composition-api.md",
            "content": "Vue composition API provides a way to structure components using setup() and reactive() functions. It is similar to React hooks but has its own unique reactive system.",
            "chunk_index": 0
        },
        {
            "library": "react",
            "version": "latest",
            "file_path": "react/latest/hooks.md",
            "content": "React hooks like useState and useEffect allow functional components to use state and lifecycle features. They were introduced in React 16.8.",
            "chunk_index": 0
        }
    ]
    
    for doc in docs:
        dense_vec = list(dense_model.embed([doc["content"]]))[0].tolist()
        sparse_vec = list(sparse_model.embed([doc["content"]]))[0]
        
        client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector={
                        "dense": dense_vec,
                        "sparse": models.SparseVector(
                            indices=sparse_vec.indices.tolist(),
                            values=sparse_vec.values.tolist()
                        )
                    },
                    payload={
                        "library": doc["library"],
                        "version": doc["version"],
                        "file_path": doc["file_path"],
                        "content": doc["content"],
                        "title": doc["file_path"].split("/")[-1],
                        "type": "markdown",
                        "chunk_index": doc["chunk_index"]
                    }
                )
            ]
        )
    
    print(f"Successfully seeded {len(docs)} documents into {collection_name} with indices")

if __name__ == "__main__":
    seed()
