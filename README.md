# Transcription Analytics Workflows

A comprehensive Google Cloud Platform (GCP) workflow system for processing customer service call transcripts using AI-powered analysis. This system orchestrates batch processing of large datasets through Google Cloud Workflows, Cloud Functions, and Vertex AI.

## 🏗️ Architecture Overview

This system consists of four main components working together:

1. **Google Cloud Workflows** - Orchestrates the entire process
2. **Cloud Functions** - Handles data processing and batch management
3. **Vertex AI** - Performs AI-powered transcript analysis
4. **BigQuery** - Stores source data and processed results

### System Flow

```
User Trigger → Main Workflow → Batch Orchestrator → Manager Workflow → Sub-Workflows → AI Processing → Results Storage
```

## 📁 Repository Structure

```
transcription-analytics-workflows/
├── workflows/                    # Google Cloud Workflow definitions
│   ├── ta-main-workflow.yaml     # Master orchestrator
│   ├── ta-manager-workflow.yaml  # Batch manager
│   ├── ta-sub-workflow.yaml      # Individual batch processor
│   ├── ta-retry-processor-workflow.yaml  # Retry handler
│   └── old_workflow.yaml         # Legacy workflow (reference)
├── cloud-functions/              # Cloud Function source code
│   ├── batch_orchestrator_function/     # Batch planning and tracking
│   ├── pass1_batch_generator_function/  # Data preparation for AI
│   └── pass1_batch_processor_function/  # Result processing and storage
├── scripts/                      # Automation and trigger scripts
│   ├── trigger_workflows.sh      # Main workflow trigger script
│   ├── deploy_and_test.sh        # Testing and deployment
│   ├── deploy_retry_workflow.sh  # Retry workflow deployment
│   ├── run_retry_workflow.sh     # Retry workflow execution
│   ├── setup_cloud_scheduler.sh  # Automated scheduling
│   ├── test_orchestrator.py      # Comprehensive testing
│   └── start_row_test_script.py  # Start row functionality testing
├── docs/                         # Documentation
│   ├── workflow_flow_diagram.md  # Workflow flow documentation
│   ├── workflow_execution_guide.md  # Execution guide
│   ├── high_level_architecture_diagram.md  # Architecture overview
│   ├── complete_flow_diagram.md  # Complete system flow
│   ├── batch_lifecycle_gcp_services.md  # GCP services lifecycle
│   └── ENTERPRISE_DEPLOYMENT.md  # Enterprise deployment guide
├── test-configs/                 # Test configurations
│   ├── test_small_batch.json     # Small batch test config
│   └── test_tiny_batch.json      # Tiny batch test config
├── deployment/                   # Deployment automation
└── README.md                     # This file
```

## 🚀 Quick Start

### Prerequisites

- Google Cloud Platform project with billing enabled
- `gcloud` CLI installed and authenticated
- Required APIs enabled:
  - Cloud Workflows API
  - Cloud Functions API
  - Vertex AI API
  - BigQuery API
  - Cloud Storage API

### 1. Deploy Cloud Functions

```bash
# Deploy batch orchestrator
cd cloud-functions/batch_orchestrator_function
gcloud functions deploy batch-orchestrator \
  --gen2 \
  --runtime=python312 \
  --source=. \
  --entry-point=batch_orchestrator \
  --trigger-http \
  --region=us-central1 \
  --memory=512MB \
  --timeout=540s

# Deploy batch generator
cd ../pass1_batch_generator_function
gcloud functions deploy pass1-batch-generator \
  --gen2 \
  --runtime=python312 \
  --source=. \
  --entry-point=pass1_batch_generator \
  --trigger-http \
  --region=us-central1 \
  --memory=2GB \
  --timeout=1800s

# Deploy batch processor
cd ../pass1_batch_processor_function
gcloud functions deploy pass1-batch-processor \
  --gen2 \
  --runtime=python312 \
  --source=. \
  --entry-point=pass1_batch_processor \
  --trigger-http \
  --region=us-central1 \
  --memory=4GB \
  --timeout=1800s
```

### 2. Deploy Workflows

```bash
# Deploy main workflow
gcloud workflows deploy ta-main-workflow \
  --source=workflows/ta-main-workflow.yaml \
  --location=us-central1

# Deploy manager workflow
gcloud workflows deploy ta-manager-workflow \
  --source=workflows/ta-manager-workflow.yaml \
  --location=us-central1

# Deploy sub-workflow
gcloud workflows deploy ta-sub-workflow \
  --source=workflows/ta-sub-workflow.yaml \
  --location=us-central1

# Deploy retry workflow
gcloud workflows deploy ta-retry-processor-workflow \
  --source=workflows/ta-retry-processor-workflow.yaml \
  --location=us-central1
```

### 3. Run Tests

```bash
# Run comprehensive tests
./scripts/deploy_and_test.sh

# Or run specific tests
python scripts/test_orchestrator.py --config test-configs/test_small_batch.json
```

### 4. Trigger Workflows

```bash
# Test run (small dataset)
./scripts/trigger_workflows.sh test

# Production run (full dataset)
./scripts/trigger_workflows.sh production

# Custom run with specific parameters
./scripts/trigger_workflows.sh custom 5000 3 1001
```

## 🎯 Usage Examples

### Basic Workflow Triggering

```bash
# Test run - processes 100 records with 2 concurrent workflows
./scripts/trigger_workflows.sh test

# Production run - processes full dataset with 10K batch size
./scripts/trigger_workflows.sh production

# Incremental run - processes specific row range
./scripts/trigger_workflows.sh incremental 1 50000 5000 3

# Single batch - processes one small batch
./scripts/trigger_workflows.sh single 1 10000 my_exec_123 batch_001

# Custom run - full control over parameters
./scripts/trigger_workflows.sh custom 5000 3 1001
```

### Monitoring and Management

```bash
# List recent workflow executions
gcloud workflows executions list --workflow=ta-main-workflow --location=us-central1 --limit=10

# Check specific execution status
gcloud workflows executions describe [EXECUTION_NAME] --location=us-central1

# Check function logs
gcloud functions logs read batch-orchestrator --region=us-central1 --limit=50

# Monitor in Google Cloud Console
# https://console.cloud.google.com/workflows/executions?project=YOUR_PROJECT_ID
```

### Automated Scheduling

```bash
# Set up daily processing at 2:30 AM
./scripts/setup_cloud_scheduler.sh create-daily daily-processing 2 30

# Set up weekly processing on Mondays at 3:00 AM
./scripts/setup_cloud_scheduler.sh create-weekly weekly-processing 1 3 0

# List existing scheduled jobs
./scripts/setup_cloud_scheduler.sh list
```

## 🔧 Configuration

### Environment Variables

The system uses the following configuration parameters:

- `PROJECT_ID`: Your GCP project ID
- `REGION`: GCP region (default: us-central1)
- `DATASET`: BigQuery dataset name
- `INDEX_TABLE`: Source table for transcript data
- `OUTPUT_TABLE`: Destination table for processed results
- `BATCH_BUCKET`: Cloud Storage bucket for batch input files
- `BATCH_OUTPUT_BUCKET`: Cloud Storage bucket for batch output files
- `MODEL`: Vertex AI model name (default: gemini-2.5-flash-lite)

### Test Configurations

Use the provided test configurations for different scenarios:

- `test-configs/test_tiny_batch.json`: 10 records, 2 concurrent workflows
- `test-configs/test_small_batch.json`: 50 records, 3 concurrent workflows

## 📊 Monitoring and Troubleshooting

### Key Metrics to Monitor

1. **Workflow Execution Status**: Check for failed or stuck executions
2. **Cloud Function Performance**: Monitor memory usage and execution time
3. **BigQuery Job Status**: Ensure data processing completes successfully
4. **Vertex AI Batch Jobs**: Monitor AI processing progress

### Common Issues and Solutions

1. **Workflow Timeout**: Increase timeout values in workflow definitions
2. **Memory Issues**: Increase Cloud Function memory allocation
3. **Permission Errors**: Verify IAM roles and service account permissions
4. **Data Quality Issues**: Check source data format and completeness

### Logs and Debugging

```bash
# View workflow logs
gcloud workflows executions describe [EXECUTION_NAME] --location=us-central1

# View function logs
gcloud functions logs read [FUNCTION_NAME] --region=us-central1 --limit=100

# View BigQuery job logs
bq ls -j --max_results=10
```

## 🔄 Retry and Recovery

### Manual Retry

```bash
# Retry a failed workflow execution
./scripts/run_retry_workflow.sh PROJECT_ID REGION FAILED_EXECUTION_NAME

# Retry with custom parameters
./scripts/run_retry_workflow.sh PROJECT_ID REGION FAILED_EXECUTION_NAME 50 1600
```

### Automated Recovery

The system includes built-in retry mechanisms:
- Workflow-level retries for transient failures
- Function-level retries with exponential backoff
- Batch job retries for AI processing failures

## 🏢 Enterprise Deployment

For enterprise environments with restricted deployment access, see:
- `docs/ENTERPRISE_DEPLOYMENT.md` - Detailed enterprise deployment guide
- `docs/batch_lifecycle_gcp_services.md` - GCP services lifecycle management

## 📚 Documentation

- `docs/workflow_flow_diagram.md` - Detailed workflow flow diagrams
- `docs/workflow_execution_guide.md` - Step-by-step execution guide
- `docs/high_level_architecture_diagram.md` - System architecture overview
- `docs/complete_flow_diagram.md` - Complete system flow documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly using the provided test scripts
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the documentation in the `docs/` directory
2. Review the troubleshooting section above
3. Check Google Cloud Console logs
4. Create an issue in the repository

## 🔄 Version History

- **v1.0.0** - Initial release with complete workflow system
- **v1.1.0** - Added retry mechanisms and improved error handling
- **v1.2.0** - Added automated scheduling and monitoring tools
