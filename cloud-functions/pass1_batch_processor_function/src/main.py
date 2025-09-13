import functions_framework
import json
import re
import base64
import logging
import time
import psutil
import os
from typing import Dict, List, Tuple, Optional

# from google.cloud import storage
from google.cloud import bigquery
from google.cloud.exceptions import NotFound, BadRequest
from google.api_core import retry
from google.api_core.exceptions import GoogleAPIError
from json_repair import repair_json
from datetime import datetime
from decimal import Decimal
import logging

# Import your custom helper function from the local module
from gcp_clients import get_bq_client, get_storage_client

# # Set up logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# Pre-compiled regexes
RE_KEY = re.compile(r'"key"\s*:\s*"([^"]+)"')
RE_PART1 = re.compile(
    r'"parts"\s*:\s*\[\s*{\s*"text"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.DOTALL,
)

# Configuration constants
DEFAULT_BATCH_SIZE = 100
DEFAULT_TIMEOUT_SECONDS = 3300  # 55 minutes (leave 5 min buffer for 60 min limit)
MAX_MEMORY_USAGE_PERCENT = 80
CHUNK_SIZE = 1000  # Process files in chunks if too large
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


class ProcessingConfig:
    """Configuration class for processing parameters."""

    def __init__(self, request_data: dict):
        # Get output info from the completed batch job
        self.output_info = request_data.get("output_info", {})

        self.project_id = request_data.get("project_id")
        self.dataset = request_data.get("dataset")
        self.workflow_id = request_data.get("workflow_id")
        self.lookup_table = request_data.get("lookup_table")
        self.output_table = request_data.get("output_table")
        self.region = request_data.get(
            "region", "us-central1"
        )  # Default to us-central1

        # Parse the actual output location from batch job results
        self.actual_bucket_name, self.actual_prefix = self._parse_output_location()

        # Configurable parameters with defaults
        self.batch_size = request_data.get("batch_size", DEFAULT_BATCH_SIZE)
        self.timeout_seconds = request_data.get(
            "timeout_seconds", DEFAULT_TIMEOUT_SECONDS
        )
        self.enable_chunked_processing = request_data.get(
            "enable_chunked_processing", True
        )
        self.max_retries = request_data.get("max_retries", MAX_RETRIES)
        self.chunk_size = request_data.get("chunk_size", CHUNK_SIZE)

        # Validate required parameters
        required = [
            "project_id",
            "dataset",
            "lookup_table",
            "output_table",
            "workflow_id",
        ]
        missing = [param for param in required if not getattr(self, param)]
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")

        if not self.actual_bucket_name or not self.actual_prefix:
            raise ValueError("Could not parse output location from batch job results")

    def _parse_output_location(self) -> Tuple[str, str]:
        """Parse the actual bucket name and prefix from batch job output info."""
        try:
            # The output_info should contain something like:
            # {"gcsOutputDirectory": "gs://bucket-name/path/to/output/"}
            gcs_output_dir = self.output_info.get("gcsOutputDirectory", "")

            if not gcs_output_dir:
                logging.warning(
                    "No gcsOutputDirectory found in output_info, trying fallback"
                )
                # Fallback: check for other possible fields
                for key, value in self.output_info.items():
                    if isinstance(value, str) and value.startswith("gs://"):
                        gcs_output_dir = value
                        break

            if not gcs_output_dir:
                raise ValueError(
                    "No GCS output directory found in batch job output info"
                )

            # Parse "gs://bucket-name/path/to/output/"
            # Remove "gs://" prefix
            path = gcs_output_dir[5:]  # Remove "gs://"

            # Split on first "/" to separate bucket name from path
            parts = path.split("/", 1)
            bucket_name = parts[0]
            prefix = parts[1] if len(parts) > 1 else ""

            # Remove trailing slash from prefix if present
            prefix = prefix.rstrip("/")

            logging.info(
                f"Parsed output location: bucket='{bucket_name}', prefix='{prefix}'"
            )
            return bucket_name, prefix

        except Exception as e:
            print(f"ERROR: Error parsing output location: {e}")
            logging.error(f"Error parsing output location: {e}")
            logging.error(f"Output info received: {self.output_info}")
            raise ValueError(f"Could not parse output location: {e}")


def monitor_memory_usage() -> Tuple[float, float]:
    """Monitor current memory usage and return (used_percent, available_mb)."""
    try:
        memory = psutil.virtual_memory()
        used_percent = memory.percent
        available_mb = memory.available / (1024 * 1024)
        return used_percent, available_mb
    except Exception as e:
        print(f"ERROR: Could not get memory info: {e}")
        logging.warning(f"Could not get memory info: {e}")
        return 0.0, 0.0


def check_memory_threshold() -> bool:
    """Check if memory usage is approaching limits."""
    used_percent, available_mb = monitor_memory_usage()
    if used_percent > MAX_MEMORY_USAGE_PERCENT:
        logging.warning(
            f"High memory usage: {used_percent:.1f}% used, {available_mb:.1f}MB available"
        )
        return False
    return True


class RetryableError(Exception):
    """Exception for errors that should be retried."""

    pass


def with_retry(max_retries: int = MAX_RETRIES, delay: float = RETRY_DELAY):
    """Decorator for retrying operations with exponential backoff."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (GoogleAPIError, RetryableError) as e:
                    last_exception = e
                    print(
                        f"ERROR: Retryable error in {func.__name__} (attempt {attempt + 1}): {e}"
                    )
                    if attempt == max_retries:
                        print(
                            f"ERROR: Max retries ({max_retries}) exceeded for {func.__name__}"
                        )
                        logging.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}"
                        )
                        raise

                    wait_time = delay * (2**attempt)  # Exponential backoff
                    print(f"WARNING: Retrying {func.__name__} in {wait_time}s...")
                    logging.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                except Exception as e:
                    # Check if this is a retryable HTTP error (429, 502, 503)
                    error_str = str(e).lower()
                    if any(
                        keyword in error_str
                        for keyword in [
                            "429",
                            "502",
                            "503",
                            "timeout",
                            "deadline",
                            "unavailable",
                        ]
                    ):
                        last_exception = e
                        print(
                            f"ERROR: Retryable HTTP error in {func.__name__} (attempt {attempt + 1}): {e}"
                        )
                        if attempt == max_retries:
                            print(
                                f"ERROR: Max retries ({max_retries}) exceeded for {func.__name__}"
                            )
                            logging.error(
                                f"Max retries ({max_retries}) exceeded for {func.__name__}"
                            )
                            raise

                        wait_time = delay * (2**attempt)  # Exponential backoff
                        print(f"WARNING: Retrying {func.__name__} in {wait_time}s...")
                        logging.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        # Non-retryable error
                        print(f"ERROR: Non-retryable error in {func.__name__}: {e}")
                        logging.error(f"Non-retryable error in {func.__name__}: {e}")
                        raise

            raise last_exception

        return wrapper

    return decorator


@functions_framework.http
def pass1_batch_processor(request):
    """Process batch prediction results from GCS and upload to BigQuery."""
    start_time = time.time()

    try:
        request_json = request.get_json()
        logging.info(f"Received request JSON: {json.dumps(request_json, default=str)}")
        config = ProcessingConfig(request_json)

        print(f"Starting batch result processing for workflow {config.workflow_id}")

        # Debug: Check what project the default credentials are associated with
        try:
            from google.auth import default

            credentials, default_project = default()
            print(f"Default credentials project: {default_project}")
            print(
                f"Service account email: {credentials.service_account_email if hasattr(credentials, 'service_account_email') else 'Not a service account'}"
            )
        except Exception as e:
            print(f"ERROR: Could not check default credentials: {e}")
        print(
            f"Output location: gs://{config.actual_bucket_name}/{config.actual_prefix}"
        )
        print(
            f"Configuration: batch_size={config.batch_size}, timeout={config.timeout_seconds}s, chunked={config.enable_chunked_processing}"
        )

        # Monitor initial memory
        used_percent, available_mb = monitor_memory_usage()
        logging.info(
            f"Initial memory usage: {used_percent:.1f}% used, {available_mb:.1f}MB available"
        )

        # Step 1: Download JSONL file from GCS using the actual bucket and prefix
        logging.info("Downloading batch results from GCS...")
        jsonl_content = download_batch_results_from_gcs(
            config.actual_bucket_name, config.actual_prefix, config.project_id
        )
        if jsonl_content:
            print(f"downloaded jsonl_content (last 100 chars): {jsonl_content[-100:]}")
        else:
            print("downloaded jsonl_content: (empty or None)")

        # Check memory after download
        if not check_memory_threshold():
            logging.warning(
                "High memory usage after download, enabling chunked processing"
            )
            config.enable_chunked_processing = True

        # Step 2: Process the data (with chunking if enabled)
        if (
            config.enable_chunked_processing and len(jsonl_content) > 1024 * 1024
        ):  # > 1MB
            print("Large file detected, using chunked processing")
            total_processed, parsed_responses = process_large_file_chunked(
                jsonl_content, config, start_time
            )
        else:
            print("Processing entire file in memory")
            total_processed, parsed_responses = process_entire_file(
                jsonl_content, config, start_time
            )

        elapsed_time = time.time() - start_time
        logging.info(
            f"Processing completed successfully in {elapsed_time:.2f}s. Total processed: {total_processed} records."
        )

        logging.info("Batch processing completed successfully")

        return {
            "status": "success",
            "processed_records": total_processed,
            "processing_time_seconds": elapsed_time,
            "workflow_id": config.workflow_id,
        }, 200

    except Exception as e:
        elapsed_time = time.time() - start_time
        print(
            f"ERROR: Error processing batch results after {elapsed_time:.2f}s: {str(e)}"
        )
        logging.error(
            f"Error processing batch results after {elapsed_time:.2f}s: {str(e)}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": str(e),
            "processing_time_seconds": elapsed_time,
        }, 500


def process_entire_file(
    jsonl_content: str, config: ProcessingConfig, start_time: float
) -> Tuple[int, dict]:
    """Process the entire file in memory."""
    # Check timeout
    if time.time() - start_time > config.timeout_seconds:
        raise TimeoutError(f"Processing timeout ({config.timeout_seconds}s) exceeded")

    print(f"jsonl_content: {jsonl_content}")

    # Extract and parse data
    logging.info("Extracting batch data...")
    extracted_data = extract_batch_from_content(jsonl_content)

    if not extracted_data:
        raise ValueError("No records successfully extracted")

    # Parse JSON responses
    logging.info("Parsing JSON responses...")
    parsed_responses = parse_responses(extracted_data)

    if not parsed_responses:
        raise ValueError("No records successfully parsed")

    # Process and upload
    total_processed = process_and_upload_data(parsed_responses, config, start_time)
    return total_processed, parsed_responses


def process_large_file_chunked(
    jsonl_content: str, config: ProcessingConfig, start_time: float
) -> Tuple[int, dict]:
    """Process large files in chunks to manage memory usage."""
    lines = jsonl_content.strip().split("\n")
    total_processed = 0
    all_parsed_responses = {}

    print(f"Processing {len(lines)} lines in chunks of {config.chunk_size}")

    for i in range(0, len(lines), config.chunk_size):
        # Check timeout
        if time.time() - start_time > config.timeout_seconds:
            raise TimeoutError(
                f"Processing timeout ({config.timeout_seconds}s) exceeded"
            )

        chunk_lines = lines[i : i + config.chunk_size]
        chunk_content = "\n".join(chunk_lines)

        print(
            f"Processing chunk {i//config.chunk_size + 1}/{(len(lines) + config.chunk_size - 1)//config.chunk_size} ({len(chunk_lines)} lines)"
        )

        # Extract and parse chunk
        extracted_data = extract_batch_from_content(chunk_content)
        if not extracted_data:
            logging.warning(f"No data extracted from chunk {i//config.chunk_size + 1}")
            continue

        parsed_responses = parse_responses(extracted_data)
        if not parsed_responses:
            logging.warning(
                f"No responses parsed from chunk {i//config.chunk_size + 1}"
            )
            continue

        # Process chunk
        chunk_processed = process_and_upload_data(parsed_responses, config, start_time)
        total_processed += chunk_processed

        # Collect all parsed responses for return value
        all_parsed_responses.update(parsed_responses)

        # Check memory between chunks
        if not check_memory_threshold():
            logging.warning("High memory usage detected, forcing garbage collection")
            import gc

            gc.collect()

    return total_processed, all_parsed_responses


def process_and_upload_data(
    parsed_responses: dict, config: ProcessingConfig, start_time: float
) -> int:
    """Process parsed responses and upload to BigQuery."""
    # Check timeout
    if time.time() - start_time > config.timeout_seconds:
        raise TimeoutError(f"Processing timeout ({config.timeout_seconds}s) exceeded")

    # Fetch interaction details from BigQuery
    logging.info(f"Fetching interaction details for {len(parsed_responses)} tokens...")
    phone_tokens = set()
    for composite_key in parsed_responses.keys():
        phone_token, _ = decode_base64_key(composite_key)
        phone_tokens.add(phone_token)

    bq_interaction_map = fetch_interaction_details_from_bq_by_phone_tokens(
        phone_tokens, config.project_id, config.lookup_table
    )

    # Build rows for output table
    logging.info("Building rows for BigQuery insertion...")
    rows = build_analyzed_transcript_rows(parsed_responses, bq_interaction_map)

    if not rows:
        raise ValueError("No rows built for insertion")

    # Insert into BigQuery
    logging.info(
        f"Inserting {len(rows)} rows into BigQuery with batch size {config.batch_size}..."
    )
    logging.info(
        f"Target table: {config.project_id}.{config.dataset}.{config.output_table}"
    )
    success_count = insert_rows_to_bq_with_retry(
        rows,
        config.project_id,
        config.dataset,
        config.output_table,
        config.batch_size,
        config.max_retries,
    )

    return success_count


@with_retry()
def download_batch_results_from_gcs(
    bucket_name: str, prefix: str, project_id: str
) -> str:
    """Download batch prediction results from GCS with retry logic."""
    try:
        # storage_client = storage.Client()
        storage_client = get_storage_client(project_id)
        bucket = storage_client.bucket(bucket_name)

        logging.info(
            f"Looking for prediction files in bucket '{bucket_name}' with prefix '{prefix}'"
        )

        # List blobs with the prefix
        blobs = list(bucket.list_blobs(prefix=prefix))

        if not blobs:
            raise ValueError(
                f"No files found in bucket '{bucket_name}' with prefix '{prefix}'"
            )

        logging.info(f"Found {len(blobs)} files with prefix '{prefix}':")
        for blob in blobs:
            logging.info(f"  - {blob.name} ({blob.size} bytes)")

        # Look for prediction files - Vertex AI creates files like "predictions.jsonl" or "predictions_000.jsonl"
        prediction_blobs = []

        for blob in blobs:
            blob_filename = blob.name.split("/")[-1]  # Get just the filename part
            if blob_filename.startswith("predictions") and blob_filename.endswith(
                ".jsonl"
            ):
                prediction_blobs.append(blob)

        if not prediction_blobs:
            raise ValueError(
                f"No prediction files (predictions*.jsonl) found in bucket '{bucket_name}' with prefix '{prefix}'"
            )
            # # Fallback: look for any .jsonl files
            # jsonl_blobs = [blob for blob in blobs if blob.name.endswith(".jsonl")]
            # if jsonl_blobs:
            #     logging.warning(
            #         "No 'predictions*.jsonl' files found, using available .jsonl files"
            #     )
            #     prediction_blobs = jsonl_blobs
            # else:
            #     raise ValueError(
            #         f"No prediction files (predictions*.jsonl) found in bucket '{bucket_name}' with prefix '{prefix}'"
            #     )

        # Sort prediction files by name to ensure consistent ordering
        prediction_blobs.sort(key=lambda b: b.name)

        logging.info(f"Found {len(prediction_blobs)} prediction files:")
        for blob in prediction_blobs:
            logging.info(f"  - {blob.name} ({blob.size} bytes)")

        # If multiple prediction files, combine them
        if len(prediction_blobs) == 1:
            results_blob = prediction_blobs[0]
            logging.info(f"Downloading single prediction file: {results_blob.name}")

            if results_blob.size > 100 * 1024 * 1024:  # 100MB
                logging.warning(
                    f"Large file detected: {results_blob.size / (1024*1024):.1f}MB"
                )

            return results_blob.download_as_text(encoding="utf-8")

        else:
            # Multiple prediction files - combine them
            logging.info(f"Combining {len(prediction_blobs)} prediction files")
            combined_content = []
            total_size = 0

            for blob in prediction_blobs:
                logging.info(f"Downloading {blob.name} ({blob.size} bytes)")
                content = blob.download_as_text(encoding="utf-8")
                combined_content.append(content.strip())
                total_size += blob.size

            logging.info(f"Combined total size: {total_size / (1024*1024):.1f}MB")

            if total_size > 100 * 1024 * 1024:  # 100MB
                logging.warning(
                    f"Large combined file detected: {total_size / (1024*1024):.1f}MB"
                )

            return "\n".join(combined_content)

    except Exception as e:
        print(
            f"ERROR: Error downloading from GCS bucket '{bucket_name}' with prefix '{prefix}': {e}"
        )
        logging.error(
            f"Error downloading from GCS bucket '{bucket_name}' with prefix '{prefix}': {e}"
        )
        if "timeout" in str(e).lower() or "deadline" in str(e).lower():
            raise RetryableError(f"Download timeout: {e}")
        raise


def insert_rows_to_bq_with_retry(
    rows: List[dict],
    project_id: str,
    dataset: str,
    table_id: str,
    batch_size: int,
    max_retries: int,
) -> int:
    """Insert rows to BigQuery with retry logic and better error handling."""
    if not rows:
        logging.info("No rows to insert.")
        return 0

    # client = bigquery.Client(project=project_id)
    client = get_bq_client(project_id)
    logging.info(f"BigQuery client created with project: {client.project}")
    logging.info(f"Attempting to access table: {project_id}.{dataset}.{table_id}")

    # Verify table exists
    try:
        # Create explicit table reference with project ID
        table_ref = client.dataset(dataset, project=project_id).table(table_id)
        table = client.get_table(table_ref)
        logging.info(f"Table {table_id} found. Schema has {len(table.schema)} fields.")
        logging.info(f"Table full path: {table.reference.to_api_repr()}")
    except NotFound:
        print(f"ERROR: Table {project_id}.{dataset}.{table_id} not found")
        logging.error(f"Table {project_id}.{dataset}.{table_id} not found")
        # Try to list tables in the dataset to see what's available
        try:
            dataset_ref = client.dataset(dataset, project=project_id)
            tables = list(client.list_tables(dataset_ref))
            logging.info(
                f"Available tables in {dataset}: {[t.table_id for t in tables]}"
            )
        except Exception as list_error:
            print(f"ERROR: Could not list tables: {list_error}")
            logging.error(f"Could not list tables: {list_error}")
        raise ValueError(f"Table {table_id} not found")
    except Exception as e:
        print(f"ERROR: Error accessing table: {e}")
        logging.error(f"Error accessing table: {e}")
        raise RetryableError(f"Error accessing table: {e}")

    total_rows = len(rows)
    successful_rows = 0
    failed_batches = []

    logging.info(f"Inserting {total_rows} rows in batches of {batch_size}...")

    # Process in batches
    for i in range(0, total_rows, batch_size):
        batch = rows[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_rows + batch_size - 1) // batch_size

        logging.info(
            f"Processing batch {batch_num}/{total_batches} ({len(batch)} rows)..."
        )

        # Retry logic for each batch
        batch_success = False
        for attempt in range(max_retries + 1):
            try:
                errors = client.insert_rows_json(table, batch, timeout=120)

                if not errors:
                    successful_rows += len(batch)
                    batch_success = True
                    logging.info(f"✓ Batch {batch_num} succeeded")
                    break
                else:
                    # Check if errors are retryable
                    retryable_errors = [
                        "timeout",
                        "deadline",
                        "unavailable",
                        "internal",
                        "rateLimitExceeded",
                        "429",  # Too Many Requests
                        "502",  # Bad Gateway
                        "503",  # Service Unavailable
                    ]

                    error_str = str(errors).lower()
                    if any(
                        retryable_error in error_str
                        for retryable_error in retryable_errors
                    ):
                        if attempt < max_retries:
                            wait_time = RETRY_DELAY * (2**attempt)
                            print(
                                f"WARNING: Retryable errors in batch {batch_num}, attempt {attempt + 1}. Retrying in {wait_time}s..."
                            )
                            logging.warning(
                                f"Retryable errors in batch {batch_num}, attempt {attempt + 1}. Retrying in {wait_time}s..."
                            )
                            time.sleep(wait_time)
                            continue

                    # Non-retryable or max retries reached
                    failed_batches.append(
                        {
                            "batch_num": batch_num,
                            "errors": errors,
                            "row_count": len(batch),
                        }
                    )
                    logging.error(f"✗ Batch {batch_num} failed: {errors}")
                    break

            except Exception as e:
                print(
                    f"ERROR: Exception in batch {batch_num}, attempt {attempt + 1}: {e}"
                )
                error_str = str(e).lower()
                retryable_keywords = [
                    "timeout",
                    "deadline",
                    "unavailable",
                    "429",
                    "502",
                    "503",
                ]
                if attempt < max_retries and any(
                    keyword in error_str for keyword in retryable_keywords
                ):
                    wait_time = RETRY_DELAY * (2**attempt)
                    print(f"WARNING: Retrying batch {batch_num} in {wait_time}s...")
                    logging.warning(
                        f"Exception in batch {batch_num}, attempt {attempt + 1}: {e}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    failed_batches.append(
                        {
                            "batch_num": batch_num,
                            "errors": str(e),
                            "row_count": len(batch),
                        }
                    )
                    print(f"ERROR: Batch {batch_num} failed after max retries: {e}")
                    logging.error(f"✗ Batch {batch_num} exception: {e}")
                    break

        # Small delay between successful batches to avoid rate limiting
        if batch_success and i + batch_size < total_rows:
            time.sleep(0.1)

    logging.info(
        f"Insertion complete: {successful_rows}/{total_rows} rows successful, {len(failed_batches)} failed batches"
    )

    if failed_batches:
        logging.error(
            f"Failed batch details: {json.dumps(failed_batches[:5])}..."
        )  # Log first 5

        # If more than 50% failed, raise an error
        if len(failed_batches) > total_batches / 2:
            raise ValueError(
                f"Too many failed batches: {len(failed_batches)}/{total_batches}"
            )

    return successful_rows


# Include all your existing helper functions (unchanged):
def decode_base64_key(key: str) -> Tuple[str, str]:
    """Decode base64 encoded key and return (phone_token, interaction_id)."""
    try:
        # Handle composite keys with pipe separator
        if "|" in key:
            phone_token_b64, interaction_id = key.split("|", 1)
            # Decode only the phone token part
            decoded_bytes = base64.b64decode(phone_token_b64)
            phone_token = decoded_bytes.decode("utf-8")
            logging.debug(
                f"Decoded composite key: '{key}' -> phone_token: '{phone_token}', interaction_id: '{interaction_id}'"
            )
            return phone_token, interaction_id
        else:
            # If no pipe, assume it's just a base64 encoded value
            decoded_bytes = base64.b64decode(key)
            decoded_value = decoded_bytes.decode("utf-8")
            logging.debug(f"Decoded simple key: '{key}' -> '{decoded_value}'")
            return decoded_value, None

    except Exception as exc:
        print(f"ERROR: Could not decode base64 key '{key}': {exc}")
        logging.warning(f"Could not decode base64 key '{key}': {exc}")
        return key, None  # return original if decoding fails


def extract_via_json(obj: dict) -> str | None:
    """Extract response text from JSON object."""
    try:
        return obj["response"]["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        print(f"ERROR: Failed to extract response text: {e}")
        return None


def extract_via_regex(line: str) -> Tuple[str | None, str | None]:
    """Extract key and text via regex fallback."""
    key_match = RE_KEY.search(line)
    part_match = RE_PART1.search(line)
    key = key_match.group(1) if key_match else None
    text = part_match.group(1) if part_match else None
    return key, text


def safe_repair_json(text: str) -> str:
    """Safely attempt to repair JSON."""
    try:
        repaired = repair_json(text)
        if repaired is not None:
            return repaired.replace("(", "").replace(")", "")
        return text
    except Exception as exc:
        print(f"ERROR: repair_json failed: {exc}")
        logging.warning(f"repair_json failed: {exc}")
        return text


def extract_batch_from_content(jsonl_content: str) -> dict[str, str]:
    """Extract and process batch data from JSONL content."""
    result = {}
    failures = []

    lines = jsonl_content.strip().split("\n")

    for lineno, raw_line in enumerate(lines, 1):
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        key = text = None

        # Try JSON parse first
        try:
            obj = json.loads(raw_line)
            key = obj.get("key")
            text = extract_via_json(obj)
            if text is not None:
                text = safe_repair_json(text)
        except Exception as exc:
            print(f"ERROR: JSON parse error on line {lineno}: {exc}")
            parse_error = str(exc)
        else:
            parse_error = ""

        # Regex fallback
        if key is None or text is None:
            r_key, r_text = extract_via_regex(raw_line)
            key = key or r_key
            text = text or r_text
            if text is not None:
                text = safe_repair_json(text)

        # Success or failure
        if key is not None and text is not None:
            result[key] = text
        else:
            failure = {
                "lineno": lineno,
                "reason": parse_error or "required field(s) not found",
                "raw": raw_line[:500],  # truncate for logging
            }
            failures.append(failure)

    logging.info(
        f"Processed {len(result)} lines successfully, {len(failures)} failures"
    )

    if failures and len(failures) <= 10:  # Log small number of failures
        logging.warning(f"Processing failures: {json.dumps(failures)}")
    elif failures:
        logging.warning(
            f"{len(failures)} processing failures occurred. Sample: {json.dumps(failures[:3])}"
        )

    return result


def parse_responses(data: Dict[str, str]) -> Dict[str, dict]:
    """Parse JSON response strings."""
    parsed_responses = {}
    processing_errors = []

    for k, response_str in data.items():
        try:
            payload = json.loads(response_str)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected dict, got {type(payload).__name__}")
            parsed_responses[k] = payload
        except Exception as exc:
            print(f"ERROR: Failed to parse response for key '{k}': {exc}")
            error = {
                "key": k,
                "error": str(exc),
                "text": response_str[:300],  # truncate for logging
            }
            processing_errors.append(error)

    if processing_errors:
        if len(processing_errors) <= 5:
            logging.warning(f"Response parsing errors: {json.dumps(processing_errors)}")
        else:
            logging.warning(
                f"{len(processing_errors)} response parsing errors. Sample: {json.dumps(processing_errors[:3])}"
            )

    logging.info(f"Successfully parsed {len(parsed_responses)} responses")
    return parsed_responses


@with_retry()
def fetch_interaction_details_from_bq_by_phone_tokens(
    phone_tokens, project_id, table_id
):
    """Fetch interaction details from BigQuery with retry logic."""
    if not phone_tokens:
        return {}

    try:
        # client = bigquery.Client(project=project_id)
        client = get_bq_client(project_id)
        # table_id already contains the full table path (project.dataset.table)
        query = f"SELECT * FROM `{table_id}` WHERE phone_number_token IN UNNEST(@phone_tokens)"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter(
                    "phone_tokens", "STRING", list(phone_tokens)
                )
            ]
        )

        results = client.query(query, job_config=job_config).result()

        out = {}
        row_count = 0
        for row in results:
            token = row["phone_number_token"]
            out.setdefault(token, []).append(dict(row))
            row_count += 1

        # if out:
        #     sample_token = list(out.keys())[0]
        #     sample_rows = out[sample_token]
        #     print(f"Sample data for token '{sample_token}': {len(sample_rows)} rows")
        #     if sample_rows:
        #         print(f"Sample row fields: {list(sample_rows[0].keys())}")

        return out

    except Exception as e:
        print(f"ERROR: Error fetching from BigQuery: {e}")
        logging.error(f"Error fetching from BigQuery: {e}")
        if "timeout" in str(e).lower() or "deadline" in str(e).lower():
            raise RetryableError(f"BigQuery timeout: {e}")
        raise


def build_analyzed_transcript_rows(parsed_responses, bq_interaction_map):
    """Build rows for transcription_analyzed_transcripts table from parsed responses and BQ data."""
    rows = []
    build_errors = []

    for composite_key, response_content in parsed_responses.items():
        try:
            # Validate that response_content is a dict
            if not isinstance(response_content, dict):
                build_errors.append(
                    {
                        "composite_key": composite_key,
                        "error": f"Expected dict, got {type(response_content).__name__}",
                        "content": str(response_content)[:1000],
                    }
                )
                continue

            # Decode the composite key to get phone_token and interaction_id
            phone_token, interaction_id = decode_base64_key(composite_key)

            # Find the specific interaction record
            bq_rows = bq_interaction_map.get(phone_token, [])
            bq_row = {}

            # If we have an interaction_id, find the specific interaction
            if interaction_id and bq_rows:
                for row in bq_rows:
                    if row.get("interactionId") == interaction_id:
                        bq_row = row
                        break
                # If not found, use the first row as fallback
                if not bq_row and bq_rows:
                    bq_row = bq_rows[0]

            elif bq_rows:
                # No interaction_id, use the first row
                bq_row = bq_rows[0]
            else:
                print(f"No BQ rows found for phone_token: '{phone_token}'")

            # Build row structure
            row = {
                "phone_number_token": phone_token,
                "call_summary": response_content.get("callSummary"),
                "call_sentiment_incoming": response_content.get(
                    "callSentiment", {}
                ).get("incoming"),
                "call_sentiment_outgoing": response_content.get(
                    "callSentiment", {}
                ).get("outgoing"),
                "call_sentiment_summary": response_content.get("callSentimentSummary"),
                "call_tone": response_content.get("callTone"),
                "language_code": response_content.get("languageCode"),
                "reason_for_call_summary": response_content.get(
                    "reasonForCall", {}
                ).get("summary"),
                "reason_for_call_intent": response_content.get("reasonForCall", {}).get(
                    "intent"
                ),
                "reason_for_call_inquiry_question": response_content.get(
                    "reasonForCall", {}
                ).get("inquiryQuestion"),
                "reason_for_call_product": response_content.get(
                    "reasonForCall", {}
                ).get("product"),
                "reason_for_call_product_category": response_content.get(
                    "reasonForCall", {}
                ).get("productCategory"),
                "agent_response_resolved": response_content.get(
                    "agentResponse", {}
                ).get("resolved"),
                "agent_response_summary": response_content.get("agentResponse", {}).get(
                    "summary"
                ),
                "agent_response_action": response_content.get("agentResponse", {}).get(
                    "action"
                ),
                "products": response_content.get(
                    "products", []
                ),  # Fixed: Keep as array instead of JSON string
                # BQ interaction fields
                "referenceId": bq_row.get("referenceId"),
                "interactionId": bq_row.get("interactionId"),
                "event_timestamp": convert_value_for_bq(bq_row.get("event_timestamp")),
                # Fixed: Removed "processed_at": time.time(), since the field doesn't exist in the table
            }
            rows.append(row)

        except Exception as exc:
            print(
                f"ERROR: Unexpected error building row for key '{composite_key}': {exc}"
            )
            build_errors.append(
                {
                    "composite_key": composite_key,
                    "error": f"Unexpected error: {exc}",
                    "content": str(response_content)[:1000],
                }
            )

    if build_errors:
        logging.warning(
            f"{len(build_errors)} build errors occurred. Sample: {json.dumps(build_errors[:3])}"
        )

    return rows


def convert_value_for_bq(value):
    """Convert values to BigQuery-compatible types."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@functions_framework.http
def health_check(request):
    """Health check endpoint for Cloud Function."""
    return "OK", 200
