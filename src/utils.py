import os
import json
import logging

logger = logging.getLogger(__name__)

def is_running_in_docker() -> bool:
    """Check if the code is running inside a Docker container."""
    try:
        # Check for Docker-specific file
        if os.path.exists('/.dockerenv'):
            return True
        
        # Check cgroup for Docker
        with open('/proc/1/cgroup', 'r') as f:
            if 'docker' in f.read():
                return True
        
        return False
    except:
        return False


def load_data_from_gcs(bucket_name: str, gcs_prefix: str = "ratp_travaux") -> dict:
    """Load the latest data snapshot from GCS bucket."""
    try:
        from google.cloud import storage
    except ImportError:
        logger.error("google-cloud-storage is not installed. Cannot load from GCS.")
        return None
    
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # Read latest pointer
        latest_blob = bucket.blob(f"{gcs_prefix}/latest.json")
        latest_metadata = json.loads(latest_blob.download_as_string())
        run_id = latest_metadata["run_id"]
        # data_file = latest_metadata["data_file"]
        
        # Load data snapshot from the run folder
        data_blob = bucket.blob(f"{gcs_prefix}/runs/{run_id}/data.json")
        data = json.loads(data_blob.download_as_string())
        
        logger.info(f"Loaded data from GCS: {bucket_name}/{gcs_prefix}/runs/{run_id}")
        return data
    except Exception as e:
        logger.error(f"Failed to load data from GCS: {e}")
        return None


def get_ics_from_gcs(ics_filename: str, bucket_name: str, gcs_prefix: str = "ratp_travaux") -> bytes:
    """Download ICS file from GCS bucket. Returns bytes for download button."""
    try:
        from google.cloud import storage
    except ImportError:
        logger.error("google-cloud-storage is not installed. Cannot load ICS from GCS.")
        return None
    
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # Get the current run_id from latest metadata
        latest_blob = bucket.blob(f"{gcs_prefix}/latest.json")
        latest_metadata = json.loads(latest_blob.download_as_string())
        run_id = latest_metadata["run_id"]
        
        # Download ICS file from the run folder
        ics_blob = bucket.blob(f"{gcs_prefix}/runs/{run_id}/event_ics/{ics_filename}")
        ics_content = ics_blob.download_as_bytes()
        
        logger.info(f"Loaded ICS from GCS: {ics_filename}")
        return ics_content
    except Exception as e:
        logger.error(f"Failed to load ICS from GCS: {e}")
        return None