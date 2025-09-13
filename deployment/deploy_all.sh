#!/bin/bash

# Complete Deployment Script for Transcription Analytics Workflows
# This script deploys all components of the system in the correct order

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - Update these values for your environment
PROJECT_ID=${PROJECT_ID:-"your-project-id"}
REGION=${REGION:-"us-central1"}
DATASET=${DATASET:-"ORDER_ANALYSIS"}
INDEX_TABLE=${INDEX_TABLE:-"transcription_pass_2"}
OUTPUT_TABLE=${OUTPUT_TABLE:-"transcription_analyzed_transcripts"}
BATCH_BUCKET=${BATCH_BUCKET:-"your-batch-input-bucket"}
BATCH_OUTPUT_BUCKET=${BATCH_OUTPUT_BUCKET:-"your-batch-output-bucket"}
MODEL=${MODEL:-"gemini-2.5-flash-lite"}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check if gcloud is installed and authenticated
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_error "Not authenticated with gcloud. Please run 'gcloud auth login' first."
        exit 1
    fi
    
    # Check if project is set
    if [ "$PROJECT_ID" = "your-project-id" ]; then
        print_error "Please set PROJECT_ID environment variable or update the script configuration."
        exit 1
    fi
    
    # Set the project
    gcloud config set project $PROJECT_ID
    
    print_status "Prerequisites check passed"
}

# Function to enable required APIs
enable_apis() {
    print_info "Enabling required Google Cloud APIs..."
    
    apis=(
        "workflows.googleapis.com"
        "cloudfunctions.googleapis.com"
        "aiplatform.googleapis.com"
        "bigquery.googleapis.com"
        "storage.googleapis.com"
        "cloudscheduler.googleapis.com"
    )
    
    for api in "${apis[@]}"; do
        print_info "Enabling $api..."
        gcloud services enable $api --project=$PROJECT_ID
    done
    
    print_status "All required APIs enabled"
}

# Function to create Cloud Storage buckets
create_buckets() {
    print_info "Creating Cloud Storage buckets..."
    
    # Create input bucket
    if ! gsutil ls gs://$BATCH_BUCKET &> /dev/null; then
        print_info "Creating input bucket: $BATCH_BUCKET"
        gsutil mb gs://$BATCH_BUCKET
    else
        print_warning "Input bucket $BATCH_BUCKET already exists"
    fi
    
    # Create output bucket
    if ! gsutil ls gs://$BATCH_OUTPUT_BUCKET &> /dev/null; then
        print_info "Creating output bucket: $BATCH_OUTPUT_BUCKET"
        gsutil mb gs://$BATCH_OUTPUT_BUCKET
    else
        print_warning "Output bucket $BATCH_OUTPUT_BUCKET already exists"
    fi
    
    print_status "Cloud Storage buckets ready"
}

# Function to create BigQuery dataset and tables
create_bigquery_resources() {
    print_info "Creating BigQuery dataset and tables..."
    
    # Create dataset
    if ! bq ls -d $PROJECT_ID:$DATASET &> /dev/null; then
        print_info "Creating dataset: $DATASET"
        bq mk --dataset $PROJECT_ID:$DATASET
    else
        print_warning "Dataset $DATASET already exists"
    fi
    
    # Create source table (if it doesn't exist)
    if ! bq ls -t $PROJECT_ID:$DATASET.$INDEX_TABLE &> /dev/null; then
        print_info "Creating source table: $INDEX_TABLE"
        bq mk --table $PROJECT_ID:$DATASET.$INDEX_TABLE \
          phone_number_token:STRING,referenceId:STRING,interactionId:STRING,transcript:TEXT,event_timestamp:TIMESTAMP
    else
        print_warning "Source table $INDEX_TABLE already exists"
    fi
    
    # Create output table (if it doesn't exist)
    if ! bq ls -t $PROJECT_ID:$DATASET.$OUTPUT_TABLE &> /dev/null; then
        print_info "Creating output table: $OUTPUT_TABLE"
        bq mk --table $PROJECT_ID:$DATASET.$OUTPUT_TABLE \
          phone_number_token:STRING,referenceId:STRING,interactionId:STRING,event_timestamp:TIMESTAMP,summary:STRING,call_sentiment_incoming:STRING,call_sentiment_outgoing:STRING,call_sentiment_summary:STRING,call_tone:STRING,language_code:STRING,reason_for_call_summary:STRING,reason_for_call_intent:STRING,reason_for_call_product:STRING,agent_response_resolved:STRING,agent_response_summary:STRING,agent_response_action:STRING,products:STRING,processed_at:FLOAT64,created_at:TIMESTAMP
    else
        print_warning "Output table $OUTPUT_TABLE already exists"
    fi
    
    print_status "BigQuery resources ready"
}

# Function to create service account
create_service_account() {
    print_info "Creating service account..."
    
    SERVICE_ACCOUNT_NAME="workflow-service-account"
    SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"
    
    # Create service account if it doesn't exist
    if ! gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL &> /dev/null; then
        print_info "Creating service account: $SERVICE_ACCOUNT_NAME"
        gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
          --display-name="Workflow Service Account" \
          --description="Service account for transcription analytics workflows"
    else
        print_warning "Service account $SERVICE_ACCOUNT_NAME already exists"
    fi
    
    # Grant necessary permissions
    print_info "Granting permissions to service account..."
    
    roles=(
        "roles/bigquery.dataEditor"
        "roles/bigquery.jobUser"
        "roles/storage.objectAdmin"
        "roles/aiplatform.user"
        "roles/workflows.invoker"
    )
    
    for role in "${roles[@]}"; do
        print_info "Granting role: $role"
        gcloud projects add-iam-policy-binding $PROJECT_ID \
          --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
          --role="$role" \
          --quiet
    done
    
    print_status "Service account created and configured"
}

# Function to deploy Cloud Functions
deploy_cloud_functions() {
    print_info "Deploying Cloud Functions..."
    
    # Deploy batch orchestrator
    print_info "Deploying batch orchestrator function..."
    cd cloud-functions/batch_orchestrator_function
    gcloud functions deploy batch-orchestrator \
      --gen2 \
      --runtime=python312 \
      --source=. \
      --entry-point=batch_orchestrator \
      --trigger-http \
      --region=$REGION \
      --memory=512MB \
      --timeout=540s \
      --max-instances=4 \
      --ingress-settings=internal-only \
      --egress-settings=all \
      --service-account=workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com \
      --project=$PROJECT_ID
    cd ../..
    
    # Deploy batch generator
    print_info "Deploying batch generator function..."
    cd cloud-functions/pass1_batch_generator_function
    gcloud functions deploy pass1-batch-generator \
      --gen2 \
      --runtime=python312 \
      --source=. \
      --entry-point=pass1_batch_generator \
      --trigger-http \
      --region=$REGION \
      --memory=2GB \
      --timeout=1800s \
      --max-instances=4 \
      --ingress-settings=internal-only \
      --egress-settings=all \
      --service-account=workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com \
      --project=$PROJECT_ID
    cd ../..
    
    # Deploy batch processor
    print_info "Deploying batch processor function..."
    cd cloud-functions/pass1_batch_processor_function
    gcloud functions deploy pass1-batch-processor \
      --gen2 \
      --runtime=python312 \
      --source=. \
      --entry-point=pass1_batch_processor \
      --trigger-http \
      --region=$REGION \
      --memory=4GB \
      --timeout=1800s \
      --max-instances=4 \
      --ingress-settings=internal-only \
      --egress-settings=all \
      --service-account=workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com \
      --project=$PROJECT_ID
    cd ../..
    
    print_status "All Cloud Functions deployed"
}

# Function to deploy workflows
deploy_workflows() {
    print_info "Deploying Google Cloud Workflows..."
    
    # Deploy main workflow
    print_info "Deploying main workflow..."
    gcloud workflows deploy ta-main-workflow \
      --source=workflows/ta-main-workflow.yaml \
      --location=$REGION \
      --project=$PROJECT_ID
    
    # Deploy manager workflow
    print_info "Deploying manager workflow..."
    gcloud workflows deploy ta-manager-workflow \
      --source=workflows/ta-manager-workflow.yaml \
      --location=$REGION \
      --project=$PROJECT_ID
    
    # Deploy sub-workflow
    print_info "Deploying sub-workflow..."
    gcloud workflows deploy ta-sub-workflow \
      --source=workflows/ta-sub-workflow.yaml \
      --location=$REGION \
      --project=$PROJECT_ID
    
    # Deploy retry workflow
    print_info "Deploying retry workflow..."
    gcloud workflows deploy ta-retry-processor-workflow \
      --source=workflows/ta-retry-processor-workflow.yaml \
      --location=$REGION \
      --project=$PROJECT_ID
    
    print_status "All workflows deployed"
}

# Function to run tests
run_tests() {
    print_info "Running system tests..."
    
    # Update test configuration with current project settings
    cat > test-configs/deployment_test.json << EOF
{
  "project_id": "$PROJECT_ID",
  "region": "$REGION",
  "dataset": "$DATASET",
  "index_table": "$INDEX_TABLE",
  "output_table": "${OUTPUT_TABLE}_test",
  "batch_bucket": "$BATCH_BUCKET",
  "batch_output_bucket": "$BATCH_OUTPUT_BUCKET",
  "model": "$MODEL",
  "batch_size": 10,
  "max_concurrent_workflows": 2,
  "start_row": 1,
  "test_mode": true,
  "description": "Deployment test configuration"
}
EOF
    
    # Run tests
    if python scripts/test_orchestrator.py --config test-configs/deployment_test.json; then
        print_status "System tests passed"
    else
        print_warning "System tests failed - check logs for details"
    fi
}

# Function to show deployment summary
show_summary() {
    echo ""
    echo -e "${GREEN}🎉 Deployment Complete!${NC}"
    echo "=========================="
    echo ""
    echo "Deployed Components:"
    echo "  ✓ Cloud Functions: batch-orchestrator, pass1-batch-generator, pass1-batch-processor"
    echo "  ✓ Workflows: ta-main-workflow, ta-manager-workflow, ta-sub-workflow, ta-retry-processor-workflow"
    echo "  ✓ BigQuery: Dataset $DATASET with tables $INDEX_TABLE and $OUTPUT_TABLE"
    echo "  ✓ Cloud Storage: Buckets $BATCH_BUCKET and $BATCH_OUTPUT_BUCKET"
    echo "  ✓ Service Account: workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com"
    echo ""
    echo "Next Steps:"
    echo "  1. Test the system: ./scripts/trigger_workflows.sh test"
    echo "  2. Run production: ./scripts/trigger_workflows.sh production"
    echo "  3. Set up scheduling: ./scripts/setup_cloud_scheduler.sh create-daily"
    echo "  4. Monitor: https://console.cloud.google.com/workflows/executions?project=$PROJECT_ID"
    echo ""
    echo "Configuration:"
    echo "  Project ID: $PROJECT_ID"
    echo "  Region: $REGION"
    echo "  Dataset: $DATASET"
    echo "  Model: $MODEL"
    echo ""
}

# Main execution
main() {
    echo -e "${BLUE}🚀 Transcription Analytics Workflows Deployment${NC}"
    echo "=================================================="
    echo ""
    
    check_prerequisites
    enable_apis
    create_buckets
    create_bigquery_resources
    create_service_account
    deploy_cloud_functions
    deploy_workflows
    run_tests
    show_summary
}

# Handle command line arguments
case "${1:-}" in
    "functions-only")
        check_prerequisites
        deploy_cloud_functions
        ;;
    "workflows-only")
        check_prerequisites
        deploy_workflows
        ;;
    "test-only")
        check_prerequisites
        run_tests
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  (no args)        - Full deployment (default)"
        echo "  functions-only   - Deploy only Cloud Functions"
        echo "  workflows-only   - Deploy only Workflows"
        echo "  test-only        - Run tests only"
        echo "  help             - Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  PROJECT_ID              - Google Cloud Project ID"
        echo "  REGION                  - GCP Region (default: us-central1)"
        echo "  DATASET                 - BigQuery Dataset (default: ORDER_ANALYSIS)"
        echo "  INDEX_TABLE             - Source table name"
        echo "  OUTPUT_TABLE            - Output table name"
        echo "  BATCH_BUCKET            - Input bucket name"
        echo "  BATCH_OUTPUT_BUCKET     - Output bucket name"
        echo "  MODEL                   - Vertex AI model (default: gemini-2.5-flash-lite)"
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information."
        exit 1
        ;;
esac
