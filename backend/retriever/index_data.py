"""
ReTour Retriever — one-off indexing script.
Run ONCE (or whenever the data changes) before starting the API:
    python index_data.py
It builds the persistent Chroma index + embeddings from ./data/*.json.
The API then loads this index at startup.
"""
from api.config import settings
from api.service import RetrieverService

if __name__ == "__main__":
    print(f"Indexing from {settings.data_dir} ...")
    RetrieverService.load(
        data_dir=settings.data_dir,
        embedder_model=settings.embedder_model,
        index_path=settings.index_path,
        rest_per_poi=settings.rest_per_poi,
        hotels_per_cluster=settings.hotels_per_cluster,
        events_per_cluster=settings.events_per_cluster,
    )
    print("Done — index built. Start the API with:  uvicorn api.main:app")
