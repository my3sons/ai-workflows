import logging
from typing import Dict

# Import clients from their respective libraries
from google.cloud import bigquery
from google.cloud import storage

# --- BigQuery Client Cache ---
_bq_clients: Dict[str, bigquery.Client] = {}

def get_bq_client(project_id: str) -> bigquery.Client:
    """
    Initializes and returns a BigQuery client from a global cache.
    
    This ensures that a client for a specific project_id is created only
    once per function instance, improving performance and stability.
    """
    global _bq_clients
    if project_id not in _bq_clients:
        logging.info(f"[gcp_clients] Initializing new BigQuery client for project: {project_id}")
        # Create and cache the client
        _bq_clients[project_id] = bigquery.Client(project=project_id)
    
    return _bq_clients[project_id]


# --- Cloud Storage Client Cache ---
_storage_clients: Dict[str, storage.Client] = {}

def get_storage_client(project_id: str) -> storage.Client:
    """
    Initializes and returns a Cloud Storage client from a global cache.

    This ensures that a client for a specific project_id is created only
    once per function instance.
    """
    global _storage_clients
    if project_id not in _storage_clients:
        logging.info(f"[gcp_clients] Initializing new Cloud Storage client for project: {project_id}")
        # Create and cache the client, explicitly setting the project.
        _storage_clients[project_id] = storage.Client(project=project_id)
    
    return _storage_clients[project_id]