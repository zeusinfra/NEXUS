import chromadb
client = chromadb.PersistentClient(path="test_db")
col = client.get_or_create_collection(name="test")
col.upsert(ids=["1"], embeddings=[[0.1, 0.2, 0.3]], documents=["hello world"])
res = col.query(query_embeddings=[[0.1, 0.2, 0.3]], n_results=1)
print(res)
