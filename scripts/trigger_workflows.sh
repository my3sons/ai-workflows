#!/bin/bash

# Workflow Triggering Script
# This script provides different ways to trigger workflows manually

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

# Function to trigger master orchestrator
trigger_master_orchestrator() {
    local batch_size=${1:-10000}
    local max_concurrent=${2:-5}
    local start_row=${3:-1}
    local execution_id="manual_exec_$(date +%Y%m%d_%H%M%S)"
    
    print_info "Triggering master orchestrator..."
    print_info "Execution ID: $execution_id"
    print_info "Batch size: $batch_size"
    print_info "Max concurrent: $max_concurrent"
    print_info "Start row: $start_row"
    
    gcloud workflows execute ta-main-workflow \
        --location=$REGION \
        --project=$PROJECT_ID \
        --data="{
            \"project_id\": \"$PROJECT_ID\",
            \"region\": \"$REGION\",
            \"dataset\": \"$DATASET\",
            \"index_table\": \"precinct_appointment_index\",
            \"output_table\": \"transcription_analyzed_transcripts\",
            \"batch_bucket\": \"puca-vertex-ai-batches-d01\",
            \"batch_output_bucket\": \"puca-vertex-ai-batch-output-d01\",
            \"model\": \"gemini-2.5-flash-lite\",
            \"batch_size\": $batch_size,
            \"max_concurrent_workflows\": $max_concurrent,
            \"start_row\": $start_row
        }"
    
    print_status "Master orchestrator triggered successfully"
}

# Function to trigger individual batch workflow
trigger_single_batch() {
    local start_row=${1:-1}
    local end_row=${2:-10000}
    local execution_id=${3:-"manual_batch_$(date +%Y%m%d_%H%M%S)"}
    local batch_id=${4:-"manual_batch_001"}
    
    print_info "Triggering single batch workflow..."
    print_info "Execution ID: $execution_id"
    print_info "Batch ID: $batch_id"
    print_info "Row range: $start_row to $end_row"
    
    gcloud workflows execute ta-sub-workflow \
        --location=$REGION \
        --project=$PROJECT_ID \
        --data="{
            \"batch_bucket\": \"puca-vertex-ai-batches-d01\",
            \"batch_output_bucket\": \"puca-vertex-ai-batch-output-d01\",
            \"dataset\": \"$DATASET\",
            \"index_table\": \"transcription_pass_2\",
            \"model\": \"gemini-2.5-flash-lite\",
            \"output_table\": \"transcription_analyzed_transcripts\",
            \"project_id\": \"$PROJECT_ID\",
            \"region\": \"$REGION\",
            \"where_clause\": \"WHERE row_num between $start_row and $end_row\",
            \"execution_id\": \"$execution_id\",
            \"batch_id\": \"$batch_id\"
        }"
    
    print_status "Single batch workflow triggered successfully"
}

# Function to trigger test run
trigger_test_run() {
    print_info "Triggering test run (small dataset)..."
    trigger_master_orchestrator 100 2 1
}

# Function to trigger production run
trigger_production_run() {
    print_info "Triggering production run (full dataset)..."
    trigger_master_orchestrator 10000 5 1
}

# Function to trigger incremental run
trigger_incremental_run() {
    local start_row=${1:-1}
    local end_row=${2:-50000}
    local batch_size=${3:-5000}
    local max_concurrent=${4:-3}
    
    print_info "Triggering incremental run..."
    print_info "Row range: $start_row to $end_row"
    print_info "Batch size: $batch_size"
    print_info "Max concurrent: $max_concurrent"
    
    # Calculate number of batches needed
    local total_records=$((end_row - start_row + 1))
    local num_batches=$((total_records / batch_size))
    if [ $((total_records % batch_size)) -ne 0 ]; then
        num_batches=$((num_batches + 1))
    fi
    
    print_info "Will create $num_batches batches starting from row $start_row"
    
    # Trigger master orchestrator with start_row parameter
    trigger_master_orchestrator $batch_size $max_concurrent $start_row
    
    print_status "Incremental run triggered successfully"
}

# Function to show monitoring commands
show_monitoring() {
    echo ""
    echo -e "${BLUE}📊 Monitoring Commands${NC}"
    echo "=========================="
    echo ""
    echo "1. List recent workflow executions:"
    echo "   gcloud workflows executions list --workflow=ta-main-workflow --location=$REGION --limit=10"
    echo ""
    echo "2. Check specific execution status:"
    echo "   gcloud workflows executions describe [EXECUTION_NAME] --location=$REGION"
    echo ""
    echo "3. Check batch orchestrator function logs:"
    echo "   gcloud functions logs read batch-orchestrator --region=$REGION --limit=50"
    echo ""
    echo "4. Check BigQuery tracking table:"
    
    echo ""
    echo "5. Monitor in Google Cloud Console:"
    echo "   https://console.cloud.google.com/workflows/executions?project=$PROJECT_ID"
    echo ""
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  test                    - Trigger test run (100 records, 2 concurrent, start_row=1)"
    echo "  production              - Trigger production run (10K batch size, 5 concurrent, start_row=1)"
    echo "  incremental [start] [end] [batch_size] [concurrent] - Trigger incremental run"
    echo "  single [start] [end] [exec_id] [batch_id] - Trigger single batch workflow"
    echo "  custom [batch_size] [concurrent] [start_row] - Trigger with custom parameters"
    echo "  monitor                 - Show monitoring commands"
    echo "  help                    - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 test                                    # Test run"
    echo "  $0 production                              # Full production run"
    echo "  $0 incremental 1 50000 5000 3             # Process rows 1-50K in 5K batches"
    echo "  $0 single 1 10000 my_exec_123 batch_001   # Single batch"
    echo "  $0 custom 5000 3                          # Custom batch size and concurrency"
    echo "  $0 custom 5000 3 1001                     # Custom with start_row=1001"
    echo ""
}

# Main execution
case "${1:-}" in
    "test")
        trigger_test_run
        show_monitoring
        ;;
    "production")
        trigger_production_run
        show_monitoring
        ;;
    "incremental")
        start_row=${2:-1}
        end_row=${3:-50000}
        batch_size=${4:-5000}
        max_concurrent=${5:-3}
        trigger_incremental_run $start_row $end_row $batch_size $max_concurrent
        show_monitoring
        ;;
    "single")
        start_row=${2:-1}
        end_row=${3:-10000}
        execution_id=${4:-"manual_batch_$(date +%Y%m%d_%H%M%S)"}
        batch_id=${5:-"manual_batch_001"}
        trigger_single_batch $start_row $end_row $execution_id $batch_id
        show_monitoring
        ;;
    "custom")
        batch_size=${2:-10000}
        max_concurrent=${3:-5}
        start_row=${4:-1}
        trigger_master_orchestrator $batch_size $max_concurrent $start_row
        show_monitoring
        ;;
    "monitor")
        show_monitoring
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
