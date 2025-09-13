#!/bin/bash

# Deploy the retry processor workflow
# Usage: ./deploy_retry_workflow.sh <project_id> <region>

set -e

PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${2:-us-central1}

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID is required"
    echo "Usage: $0 <project_id> [region]"
    exit 1
fi

echo "Deploying ta-retry-processor-workflow to project: $PROJECT_ID, region: $REGION"

# Deploy the workflow
gcloud workflows deploy ta-retry-processor-workflow \
    --source=workflow/ta-retry-processor-workflow.yaml \
    --location=$REGION \
    --project=$PROJECT_ID

echo "Successfully deployed ta-retry-processor-workflow"
echo "You can now run it with: ./scripts/run_retry_workflow.sh"
