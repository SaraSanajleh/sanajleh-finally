"""
ReTour Retriever — API configuration (Pydantic Settings).
Env-driven so nothing path-specific is hard-coded.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: str = "./data"                 # folder with the 4 JSON files
    index_path: str = "./chroma_index"       # persistent Chroma path
    embedder_model: str = "all-MiniLM-L6-v2" # swappable
    rest_per_poi: int = 3
    hotels_per_cluster: int = 3
    events_per_cluster: int = 3

    class Config:
        env_file = ".env"
        env_prefix = "RETOUR_"


settings = Settings()
