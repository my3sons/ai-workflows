import functions_framework
import json
import uuid
from datetime import datetime, timedelta
from google.cloud import bigquery
from google.auth import default
import logging
from gcp_clients import get_bq_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@functions_framework.http
def batch_orchestrator(request):
    """HTTP endpoint for batch orchestration and progress tracking."""
    try:
        request_json = request.get_json()
        action = request_json.get("action")

        logger.info(f"Received action: {action}")

        if action == "get_total_records":
            return get_total_records(request_json)
        elif action == "create_batch_plan":
            return create_batch_plan(request_json)

        else:
            return {"error": f"Unknown action: {action}"}, 400

    except Exception as e:
        logger.error(f"Error in batch_orchestrator: {str(e)}", exc_info=True)
        return {"error": str(e)}, 500


def get_total_records(request_data):
    """Get total number of records in the source table."""
    try:
        project_id = request_data.get("project_id")
        dataset = request_data.get("dataset")
        index_table = request_data.get("index_table")

        # client = bigquery.Client(project=project_id)
        client = get_bq_client(project_id)
        query = f"SELECT COUNT(*) as total_records FROM `{project_id}.{dataset}.{index_table}`"

        query_job = client.query(query)
        results = query_job.result()

        for row in results:
            total_records = row.total_records
            break

        logger.info(f"Total records in {index_table}: {total_records}")

        return {
            "total_records": total_records,
            "table": f"{project_id}.{dataset}.{index_table}",
        }, 200

    except Exception as e:
        logger.error(f"Error getting total records: {str(e)}")
        return {"error": str(e)}, 500


def create_batch_plan(request_data):
    """Create a batch plan with row ranges for processing."""
    try:
        # Debug logging to see what parameters are received
        logger.info(
            f"DEBUG - Received request_data: {json.dumps(request_data, indent=2)}"
        )

        execution_id = request_data.get("execution_id")
        total_records = request_data.get("total_records")
        batch_size = request_data.get("batch_size", 10)
        project_id = request_data.get("project_id")
        dataset = request_data.get("dataset")
        max_concurrent_batches = request_data.get("max_concurrent_batches", 3)
        start_row = request_data.get("start_row", 1)  # Default to 1 if not provided

        # Debug logging for the specific parameter
        logger.info(
            f"DEBUG - max_concurrent_batches parameter: {max_concurrent_batches}"
        )
        logger.info(
            f"DEBUG - max_concurrent_batches type: {type(max_concurrent_batches)}"
        )

        # Ensure max_concurrent_batches is an integer
        try:
            max_concurrent_batches = int(max_concurrent_batches)
            logger.info(
                f"DEBUG - Converted max_concurrent_batches to int: {max_concurrent_batches}"
            )
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Could not convert max_concurrent_batches to int, using default 3. Error: {e}"
            )
            max_concurrent_batches = 3

        # Ensure batch_size is an integer
        try:
            batch_size = int(batch_size)
            logger.info(f"DEBUG - batch_size: {batch_size}")
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not convert batch_size to int. Error: {e}")

        # Ensure start_row is an integer
        try:
            start_row = int(start_row)
            logger.info(f"DEBUG - start_row: {start_row}")
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Could not convert start_row to int, using default 1. Error: {e}"
            )
            start_row = 1

        # APPROACH 1 (DISABLED): Calculate number of batches needed to process all records
        # try:
        #     total_records = int(total_records)
        #     logger.info(f"DEBUG - batch_size: {batch_size}, total_records: {total_records}")
        #     num_batches_needed = (total_records + batch_size - 1) // batch_size
        #     logger.info(f"DEBUG - Total records: {total_records}, batch_size: {batch_size}, batches needed: {num_batches_needed}")
        #     actual_batches_to_create = num_batches_needed
        # except (ValueError, TypeError) as e:
        #     logger.warning(f"Could not convert total_records to int. Error: {e}")

        # APPROACH 2 (CURRENT): Create exactly max_concurrent_batches number of batches
        actual_batches_to_create = max_concurrent_batches
        logger.info(
            f"DEBUG - max_concurrent_batches: {max_concurrent_batches}, actual_batches_to_create: {actual_batches_to_create}"
        )

        # Create batch plan
        pending_batches = []
        logger.info(
            f"DEBUG - Creating {actual_batches_to_create} batches starting from row {start_row}"
        )
        for i in range(actual_batches_to_create):
            batch_start_row = start_row + (i * batch_size)
            batch_end_row = start_row + ((i + 1) * batch_size) - 1
            batch_id = f"batch_{execution_id}_{i+1:04d}"

            logger.info(
                f"DEBUG - Creating batch {i+1}: start_row={batch_start_row}, end_row={batch_end_row}, batch_id={batch_id}"
            )

            pending_batches.append(
                {
                    "batch_id": batch_id,
                    "start_row": batch_start_row,
                    "end_row": batch_end_row,
                    "total_rows": batch_end_row - batch_start_row + 1,
                }
            )

        logger.info(f"Created batch plan with {len(pending_batches)} batches")

        return {
            "execution_id": execution_id,
            "total_batches": len(pending_batches),
            "batch_size": batch_size,
            "max_concurrent_batches": max_concurrent_batches,
            "start_row": start_row,
            "pending_batches": pending_batches,
        }, 200

    except Exception as e:
        logger.error(f"Error creating batch plan: {str(e)}")
        return {"error": str(e)}, 500


@functions_framework.http
def health_check(request):
    """Health check endpoint for Cloud Function."""
    return "OK", 200
