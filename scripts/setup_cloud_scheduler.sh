#!/bin/bash

# Cloud Scheduler Setup Script
# This script sets up automated workflow triggering using Cloud Scheduler

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="bbyus-ana-puca-d01"
REGION="us-central1"
DATASET="ORDER_ANALYSIS"

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

# Function to create Cloud Scheduler job
create_scheduler_job() {
    local job_name=$1
    local schedule=$2
    local description=$3
    local data=$4
    
    print_info "Creating Cloud Scheduler job: $job_name"
    print_info "Schedule: $schedule"
    print_info "Description: $description"
    
    # Create the job
    gcloud scheduler jobs create http $job_name \
        --schedule="$schedule" \
        --uri="https://workflowexecutions.googleapis.com/v1/projects/$PROJECT_ID/locations/$REGION/workflows/ta-main-workflow/executions" \
        --http-method=POST \
        --headers="Content-Type=application/json" \
        --message-body="$data" \
        --oauth-service-account-email="$PROJECT_ID@appspot.gserviceaccount.com" \
        --description="$description" \
        --location=$REGION \
        --project=$PROJECT_ID
    
    print_status "Cloud Scheduler job '$job_name' created successfully"
}

# Function to list existing jobs
list_scheduler_jobs() {
    print_info "Listing existing Cloud Scheduler jobs..."
    gcloud scheduler jobs list --location=$REGION --project=$PROJECT_ID
}

# Function to delete a job
delete_scheduler_job() {
    local job_name=$1
    print_info "Deleting Cloud Scheduler job: $job_name"
    gcloud scheduler jobs delete $job_name --location=$REGION --project=$PROJECT_ID --quiet
    print_status "Job '$job_name' deleted successfully"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  create-daily [job_name] [hour] [minute] - Create daily job"
    echo "  create-weekly [job_name] [day] [hour] [minute] - Create weekly job"
    echo "  create-custom [job_name] [cron_expression] [description] - Create custom job"
    echo "  list                                    - List existing jobs"
    echo "  delete [job_name]                       - Delete a job"
    echo "  help                                    - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 create-daily daily-processing 2 30    # Daily at 2:30 AM"
    echo "  $0 create-weekly weekly-processing 1 3 0 # Weekly on Monday at 3:00 AM"
    echo "  $0 create-custom custom-job '0 4 * * 1-5' 'Weekdays at 4 AM'"
    echo "  $0 list                                  # List all jobs"
    echo "  $0 delete daily-processing               # Delete job"
    echo ""
    echo "Cron Expression Format:"
    echo "  minute hour day month day-of-week"
    echo "  Examples:"
    echo "    '0 2 * * *'     - Daily at 2:00 AM"
    echo "    '0 3 * * 1'     - Weekly on Monday at 3:00 AM"
    echo "    '0 4 * * 1-5'   - Weekdays at 4:00 AM"
    echo "    '0 1 1 * *'     - Monthly on 1st at 1:00 AM"
    echo ""
}

# Function to create daily job
create_daily_job() {
    local job_name=${1:-"daily-transcription-processing"}
    local hour=${2:-2}
    local minute=${3:-0}
    local schedule="$minute $hour * * *"
    local description="Daily transcription processing job - runs at $hour:$minute AM"
    
    local data='{
        "project_id": "'$PROJECT_ID'",
        "region": "'$REGION'",
        "dataset": "'$DATASET'",
        "index_table": "transcription_pass_2",
        "output_table": "transcription_analyzed_transcripts",
        "batch_bucket": "puca-vertex-ai-batches-d01",
        "batch_output_bucket": "puca-vertex-ai-batch-output-d01",
        "model": "gemini-2.5-flash-lite",
        "batch_size": 10000,
        "max_concurrent_workflows": 5
    }'
    
    create_scheduler_job "$job_name" "$schedule" "$description" "$data"
}

# Function to create weekly job
create_weekly_job() {
    local job_name=${1:-"weekly-transcription-processing"}
    local day=${2:-1}  # 1=Monday, 7=Sunday
    local hour=${3:-3}
    local minute=${4:-0}
    local schedule="$minute $hour * * $day"
    local day_name=""
    
    case $day in
        1) day_name="Monday" ;;
        2) day_name="Tuesday" ;;
        3) day_name="Wednesday" ;;
        4) day_name="Thursday" ;;
        5) day_name="Friday" ;;
        6) day_name="Saturday" ;;
        7) day_name="Sunday" ;;
        *) day_name="Day $day" ;;
    esac
    
    local description="Weekly transcription processing job - runs on $day_name at $hour:$minute AM"
    
    local data='{
        "project_id": "'$PROJECT_ID'",
        "region": "'$REGION'",
        "dataset": "'$DATASET'",
        "index_table": "transcription_pass_2",
        "output_table": "transcription_analyzed_transcripts",
        "batch_bucket": "puca-vertex-ai-batches-d01",
        "batch_output_bucket": "puca-vertex-ai-batch-output-d01",
        "model": "gemini-2.5-flash-lite",
        "batch_size": 10000,
        "max_concurrent_workflows": 5
    }'
    
    create_scheduler_job "$job_name" "$schedule" "$description" "$data"
}

# Function to create custom job
create_custom_job() {
    local job_name=${1:-"custom-transcription-processing"}
    local cron_expression=${2:-"0 2 * * *"}
    local description=${3:-"Custom transcription processing job"}
    
    local data='{
        "project_id": "'$PROJECT_ID'",
        "region": "'$REGION'",
        "dataset": "'$DATASET'",
        "index_table": "transcription_pass_2",
        "output_table": "transcription_analyzed_transcripts",
        "batch_bucket": "puca-vertex-ai-batches-d01",
        "batch_output_bucket": "puca-vertex-ai-batch-output-d01",
        "model": "gemini-2.5-flash-lite",
        "batch_size": 10000,
        "max_concurrent_workflows": 5
    }'
    
    create_scheduler_job "$job_name" "$cron_expression" "$description" "$data"
}

# Main execution
case "${1:-}" in
    "create-daily")
        job_name=${2:-"daily-transcription-processing"}
        hour=${3:-2}
        minute=${4:-0}
        create_daily_job "$job_name" "$hour" "$minute"
        ;;
    "create-weekly")
        job_name=${2:-"weekly-transcription-processing"}
        day=${3:-1}
        hour=${4:-3}
        minute=${5:-0}
        create_weekly_job "$job_name" "$day" "$hour" "$minute"
        ;;
    "create-custom")
        job_name=${2:-"custom-transcription-processing"}
        cron_expression=${3:-"0 2 * * *"}
        description=${4:-"Custom transcription processing job"}
        create_custom_job "$job_name" "$cron_expression" "$description"
        ;;
    "list")
        list_scheduler_jobs
        ;;
    "delete")
        job_name=$2
        if [ -z "$job_name" ]; then
            print_error "Job name is required"
            exit 1
        fi
        delete_scheduler_job "$job_name"
        ;;
    "help"|"-h"|"--help")
        show_usage
        ;;
    "")
        echo "No command specified. Use '$0 help' for usage information."
        exit 1
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information."
        exit 1
        ;;
esac
