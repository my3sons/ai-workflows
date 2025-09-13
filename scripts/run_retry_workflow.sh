#!/bin/bash

# Run the retry processor workflow
# Usage: ./run_retry_workflow.sh <project_id> <region> <failed_execution_name> [batch_size] [timeout_seconds]
# Alternative: ./run_retry_workflow.sh <project_id> <region> <failed_execution_name> [batch_size] [timeout_seconds] --manual-output-info <output_info_json>

set -e

PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${2:-us-central1}
FAILED_EXECUTION_NAME=$3
BATCH_SIZE=${4:-50}
TIMEOUT_SECONDS=${5:-1600}

# Check for manual output_info override
MANUAL_OUTPUT_INFO=""
if [[ "$6" == "--manual-output-info" && -n "$7" ]]; then
    MANUAL_OUTPUT_INFO="$7"
fi

if [ -z "$PROJECT_ID" ] || [ -z "$FAILED_EXECUTION_NAME" ]; then
    echo "Error: PROJECT_ID and FAILED_EXECUTION_NAME are required"
    echo "Usage: $0 <project_id> <region> <failed_execution_name> [batch_size] [timeout_seconds]"
    echo "   or: $0 <project_id> <region> <failed_execution_name> [batch_size] [timeout_seconds] --manual-output-info <output_info_json>"
    echo ""
    echo "Example: $0 my-project us-central1 projects/my-project/locations/us-central1/workflows/ta-sub-workflow/executions/abc123"
    echo "Example with manual output_info: $0 my-project us-central1 projects/my-project/locations/us-central1/workflows/ta-sub-workflow/executions/abc123 50 1600 --manual-output-info '{\"gcsOutputDirectory\":\"gs://my-bucket/analyze-batch-output\"}'"
    exit 1
fi

echo "Extracting parameters from failed execution: $FAILED_EXECUTION_NAME"

# Get the execution details
EXECUTION_DETAILS=$(gcloud workflows executions describe $FAILED_EXECUTION_NAME --location=$REGION --project=$PROJECT_ID --format=json)

# Extract the arguments from the failed execution
ARGS=$(echo "$EXECUTION_DETAILS" | jq -r '.result.argument // "{}"')

# Parse the arguments to get the required parameters
PROJECT_ID_FROM_EXEC=$(echo "$ARGS" | jq -r '.project_id // empty')
REGION_FROM_EXEC=$(echo "$ARGS" | jq -r '.region // empty')
DATASET=$(echo "$ARGS" | jq -r '.dataset // empty')
INDEX_TABLE=$(echo "$ARGS" | jq -r '.index_table // empty')
OUTPUT_TABLE=$(echo "$ARGS" | jq -r '.output_table // empty')
EXECUTION_ID=$(echo "$ARGS" | jq -r '.execution_id // empty')
BATCH_ID=$(echo "$ARGS" | jq -r '.batch_id // empty')

# Extract the workflow_id from the execution name
WORKFLOW_ID=$(echo "$FAILED_EXECUTION_NAME" | sed 's/.*executions\///')

echo "Extracted parameters:"
echo "  Project ID: $PROJECT_ID_FROM_EXEC"
echo "  Region: $REGION_FROM_EXEC"
echo "  Dataset: $DATASET"
echo "  Index Table: $INDEX_TABLE"
echo "  Output Table: $OUTPUT_TABLE"
echo "  Execution ID: $EXECUTION_ID"
echo "  Batch ID: $BATCH_ID"
echo "  Workflow ID: $WORKFLOW_ID"

# Determine the output_info
OUTPUT_INFO=""

if [ -n "$MANUAL_OUTPUT_INFO" ]; then
    echo "Using manually provided output_info: $MANUAL_OUTPUT_INFO"
    OUTPUT_INFO="$MANUAL_OUTPUT_INFO"
else
    echo "Attempting to extract or reconstruct output_info..."
    
    # Strategy 1: Try to extract from the execution result if it got to the process_results step
    EXECUTION_RESULT=$(echo "$EXECUTION_DETAILS" | jq -r '.result // empty')
    if [ -n "$EXECUTION_RESULT" ] && [ "$EXECUTION_RESULT" != "null" ]; then
        echo "Found execution result, checking for output_info..."
        # The execution might have failed during the process_results step, 
        # but we can try to extract the batch job info
    fi
    
    # Strategy 2: Try to find the batch job and get its output info
    echo "Looking for batch job information..."
    
    # Get the batch output bucket from the original arguments
    BATCH_OUTPUT_BUCKET=$(echo "$ARGS" | jq -r '.batch_output_bucket // empty')
    if [ -z "$BATCH_OUTPUT_BUCKET" ]; then
        echo "Error: Could not determine batch_output_bucket from failed execution"
        echo ""
        echo "You can provide the output_info manually using:"
        echo "$0 $PROJECT_ID $REGION $FAILED_EXECUTION_NAME $BATCH_SIZE $TIMEOUT_SECONDS --manual-output-info '{\"gcsOutputDirectory\":\"gs://your-bucket/analyze-batch-output\"}'"
        echo ""
        echo "To find the correct output_info:"
        echo "1. Look in the failed workflow execution logs for the batch job name"
        echo "2. Run: gcloud ai custom-jobs describe <job_name> --region=$REGION --project=$PROJECT_ID"
        echo "3. Look for the 'outputInfo' field in the response"
        exit 1
    fi
    
    # Strategy 3: Try to find the batch job by searching for jobs with the workflow_id
    echo "Searching for batch job with workflow_id: $WORKFLOW_ID"
    
    # Search for batch jobs that might match this workflow
    BATCH_JOBS=$(gcloud ai custom-jobs list --region=$REGION --project=$PROJECT_ID --filter="displayName:analyze-batch-job-$WORKFLOW_ID" --format=json 2>/dev/null || echo "[]")
    
    if [ "$BATCH_JOBS" != "[]" ]; then
        echo "Found batch job(s), checking for completed ones..."
        
        # Look for a completed job
        COMPLETED_JOB=$(echo "$BATCH_JOBS" | jq -r '.[] | select(.state == "JOB_STATE_SUCCEEDED") | .name' | head -1)
        
        if [ -n "$COMPLETED_JOB" ]; then
            echo "Found completed batch job: $COMPLETED_JOB"
            JOB_DETAILS=$(gcloud ai custom-jobs describe $COMPLETED_JOB --region=$REGION --project=$PROJECT_ID --format=json)
            EXTRACTED_OUTPUT_INFO=$(echo "$JOB_DETAILS" | jq -r '.outputInfo // empty')
            
            if [ -n "$EXTRACTED_OUTPUT_INFO" ] && [ "$EXTRACTED_OUTPUT_INFO" != "null" ]; then
                echo "Successfully extracted output_info from completed batch job"
                OUTPUT_INFO="$EXTRACTED_OUTPUT_INFO"
            fi
        fi
    fi
    
    # Strategy 4: Fallback to constructing based on standard pattern
    if [ -z "$OUTPUT_INFO" ]; then
        echo "Constructing output_info based on standard pattern..."
        OUTPUT_INFO=$(cat <<EOF
{
  "gcsOutputDirectory": "gs://$BATCH_OUTPUT_BUCKET/analyze-batch-output"
}
EOF
)
        echo "Warning: Using constructed output_info. This may not be accurate if the batch job used a different output location."
        echo "Constructed output_info: $OUTPUT_INFO"
    fi
fi

# Prepare the arguments for the retry workflow
RETRY_ARGS=$(cat <<EOF
{
  "project_id": "$PROJECT_ID_FROM_EXEC",
  "region": "$REGION_FROM_EXEC",
  "dataset": "$DATASET",
  "index_table": "$INDEX_TABLE",
  "output_table": "$OUTPUT_TABLE",
  "output_info": $OUTPUT_INFO,
  "workflow_id": "$WORKFLOW_ID",
  "execution_id": "$EXECUTION_ID",
  "batch_id": "$BATCH_ID",
  "batch_size": $BATCH_SIZE,
  "timeout_seconds": $TIMEOUT_SECONDS,
  "enable_chunked_processing": true,
  "max_retries": 3,
  "chunk_size": 500
}
EOF
)

echo "Starting retry workflow with arguments:"
echo "$RETRY_ARGS" | jq '.'

# Start the retry workflow
EXECUTION_NAME=$(gcloud workflows executions create ta-retry-processor-workflow \
    --location=$REGION \
    --project=$PROJECT_ID \
    --data="$RETRY_ARGS" \
    --format="value(name)")

echo "Started retry workflow execution: $EXECUTION_NAME"
echo "You can monitor it with: gcloud workflows executions describe $EXECUTION_NAME --location=$REGION --project=$PROJECT_ID"
