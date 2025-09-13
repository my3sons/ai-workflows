#!/bin/bash

# Testing script for the batch orchestration system
# This script tests the deployed components with a small batch

set -e  # Exit on any error

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

echo -e "${BLUE}🧪 Batch Orchestration System - Testing${NC}"
echo "=========================================="

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if gcloud is authenticated
check_auth() {
    print_info "Checking authentication..."
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_error "Not authenticated with gcloud. Please run 'gcloud auth login' first."
        exit 1
    fi
    print_status "Authentication verified"
}

# Verify deployed resources
verify_deployment() {
    print_info "Verifying deployed resources..."
    
    # Check if batch orchestrator function exists
    if gcloud functions describe batch-orchestrator --region=$REGION --project=$PROJECT_ID >/dev/null 2>&1; then
        print_status "Batch orchestrator function verified"
    else
        print_error "Batch orchestrator function not found. Please deploy it first."
        exit 1
    fi
    
    # Check if master workflow exists
    if gcloud workflows describe ta-main-workflow --location=$REGION --project=$PROJECT_ID >/dev/null 2>&1; then
        print_status "Master workflow verified"
    else
        print_error "Master workflow not found. Please deploy it first."
        exit 1
    fi
    
    print_status "All required resources are deployed and ready"
}

# Install Python dependencies for testing
# install_test_dependencies() {
#     print_info "Installing test dependencies..."
    
#     pip install google-cloud-bigquery google-cloud-workflows google-auth requests
    
#     print_status "Test dependencies installed"
# }

# Run the small batch test
run_small_batch_test() {
    print_info "Running small batch test..."
    
    python scripts/test_orchestrator.py --config test_configs/test_small_batch.json --cleanup
    
    if [ $? -eq 0 ]; then
        print_status "Small batch test passed"
        return 0
    else
        print_error "Small batch test failed"
        return 1
    fi
}

# Run a manual test with the master orchestrator
test_master_orchestrator() {
    print_info "Testing master orchestrator with small dataset..."
    
    # Execute the master workflow with test configuration
    gcloud workflows execute ta-main-workflow \
        --location=$REGION \
        --project=$PROJECT_ID \
        --data='{
            "project_id": "'$PROJECT_ID'",
            "region": "'$REGION'",
            "dataset": "'$DATASET'",
            "index_table": "transcription_pass_2",
            "output_table": "transcription_analyzed_transcripts_test",
            "batch_bucket": "puca-vertex-ai-batches-d01",
            "batch_output_bucket": "puca-vertex-ai-batch-output-d01",
            "model": "gemini-2.5-flash-lite",
            "batch_size": 25,
            "max_concurrent_workflows": 2
        }'
    
    print_status "Master orchestrator test initiated"
    print_info "Check the workflow execution in the Google Cloud Console"
}

# Show monitoring commands
show_monitoring_commands() {
    echo ""
    echo -e "${BLUE}📊 Monitoring Commands${NC}"
    echo "=========================="
    echo ""
    echo "1. Check workflow executions:"
    echo "   gcloud workflows executions list --workflow=ta-main-workflow --location=$REGION"
    echo ""
    echo "2. Check batch orchestrator function logs:"
    echo "   gcloud functions logs read batch-orchestrator --region=$REGION --limit=50"
    echo ""
    echo "3. Check BigQuery tracking table:"
    
    echo ""
    echo "4. Monitor specific workflow execution:"
    echo "   gcloud workflows executions describe [EXECUTION_NAME] --location=$REGION"
    echo ""
}

# Main execution
main() {
    echo "Starting testing process..."
    echo ""
    
    # Check authentication
    check_auth
    
    # Verify deployment
    verify_deployment
    
    # Install dependencies
    # install_test_dependencies
    
    # Run small batch test
    if run_small_batch_test; then
        print_status "Small batch test passed! The system is working correctly."
        echo ""
        
        # Ask if user wants to test the master orchestrator
        read -p "Do you want to test the master orchestrator with a small dataset? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            test_master_orchestrator
        fi
        
        show_monitoring_commands
        
        echo ""
        echo -e "${GREEN}🎉 Testing completed successfully!${NC}"
        echo ""
        echo "Next steps:"
        echo "1. Review the test results above"
        echo "2. Monitor the system using the commands provided"
        echo "3. Scale up gradually by increasing batch_size and max_concurrent_workflows"
        echo "4. For production, use the full dataset with appropriate batch sizes"
        
    else
        print_error "Testing failed. Please review the errors above and fix issues before proceeding."
        exit 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    "test-only")
        run_small_batch_test
        ;;
    "master-test")
        check_auth
        verify_deployment
        test_master_orchestrator
        ;;
    "monitor")
        show_monitoring_commands
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [test-only|master-test|monitor]"
        echo ""
        echo "Commands:"
        echo "  test-only    - Run small batch test only"
        echo "  master-test  - Test master orchestrator workflow directly"
        echo "  monitor      - Show monitoring commands"
        echo "  (no args)    - Run full testing process (verify deployment + test)"
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
