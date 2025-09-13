# Deployment Guide

This guide provides step-by-step instructions for deploying the Transcription Analytics Workflows system to Google Cloud Platform.

## Prerequisites

### 1. Google Cloud Platform Setup

- **Project**: Create or select a GCP project with billing enabled
- **APIs**: Enable the following APIs:
  ```bash
  gcloud services enable workflows.googleapis.com
  gcloud services enable cloudfunctions.googleapis.com
  gcloud services enable aiplatform.googleapis.com
  gcloud services enable bigquery.googleapis.com
  gcloud services enable storage.googleapis.com
  gcloud services enable cloudscheduler.googleapis.com
  ```

### 2. Authentication

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID
```

### 3. Required Tools

- `gcloud` CLI (latest version)
- `bq` CLI (BigQuery command-line tool)
- Python 3.11+ (for testing scripts)

## Step 1: Environment Configuration

### 1.1 Set Environment Variables

```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export DATASET="ORDER_ANALYSIS"
export INDEX_TABLE="transcription_pass_2"
export OUTPUT_TABLE="transcription_analyzed_transcripts"
export BATCH_BUCKET="your-batch-input-bucket"
export BATCH_OUTPUT_BUCKET="your-batch-output-bucket"
export MODEL="gemini-2.5-flash-lite"
```

### 1.2 Create Cloud Storage Buckets

```bash
# Create input bucket for batch files
gsutil mb gs://$BATCH_BUCKET

# Create output bucket for AI results
gsutil mb gs://$BATCH_OUTPUT_BUCKET
```

### 1.3 Set Up BigQuery Dataset and Tables

```bash
# Create dataset
bq mk --dataset $PROJECT_ID:$DATASET

# Create source table (adjust schema as needed)
bq mk --table $PROJECT_ID:$DATASET.$INDEX_TABLE \
  phone_number_token:STRING,referenceId:STRING,interactionId:STRING,transcript:TEXT,event_timestamp:TIMESTAMP

# Create output table
bq mk --table $PROJECT_ID:$DATASET.$OUTPUT_TABLE \
  phone_number_token:STRING,referenceId:STRING,interactionId:STRING,event_timestamp:TIMESTAMP,summary:STRING,call_sentiment_incoming:STRING,call_sentiment_outgoing:STRING,call_sentiment_summary:STRING,call_tone:STRING,language_code:STRING,reason_for_call_summary:STRING,reason_for_call_intent:STRING,reason_for_call_product:STRING,agent_response_resolved:STRING,agent_response_summary:STRING,agent_response_action:STRING,products:STRING,processed_at:FLOAT64,created_at:TIMESTAMP
```

## Step 2: Deploy Cloud Functions

### 2.1 Deploy Batch Orchestrator Function

```bash
cd cloud-functions/batch_orchestrator_function

# Deploy the function
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
  --egress-settings=all

cd ../..
```

### 2.2 Deploy Batch Generator Function

```bash
cd cloud-functions/pass1_batch_generator_function

# Deploy the function
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
  --egress-settings=all

cd ../..
```

### 2.3 Deploy Batch Processor Function

```bash
cd cloud-functions/pass1_batch_processor_function

# Deploy the function
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
  --egress-settings=all

cd ../..
```

## Step 3: Deploy Workflows

### 3.1 Deploy Main Workflow

```bash
gcloud workflows deploy ta-main-workflow \
  --source=workflows/ta-main-workflow.yaml \
  --location=$REGION \
  --project=$PROJECT_ID
```

### 3.2 Deploy Manager Workflow

```bash
gcloud workflows deploy ta-manager-workflow \
  --source=workflows/ta-manager-workflow.yaml \
  --location=$REGION \
  --project=$PROJECT_ID
```

### 3.3 Deploy Sub-Workflow

```bash
gcloud workflows deploy ta-sub-workflow \
  --source=workflows/ta-sub-workflow.yaml \
  --location=$REGION \
  --project=$PROJECT_ID
```

### 3.4 Deploy Retry Workflow

```bash
gcloud workflows deploy ta-retry-processor-workflow \
  --source=workflows/ta-retry-processor-workflow.yaml \
  --location=$REGION \
  --project=$PROJECT_ID
```

## Step 4: Configure IAM Permissions

### 4.1 Create Service Account

```bash
# Create service account for workflows
gcloud iam service-accounts create workflow-service-account \
  --display-name="Workflow Service Account" \
  --description="Service account for transcription analytics workflows"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

### 4.2 Update Cloud Functions

```bash
# Update functions to use the service account
gcloud functions deploy batch-orchestrator \
  --service-account=workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com \
  --region=$REGION

gcloud functions deploy pass1-batch-generator \
  --service-account=workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com \
  --region=$REGION

gcloud functions deploy pass1-batch-processor \
  --service-account=workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com \
  --region=$REGION
```

## Step 5: Testing and Validation

### 5.1 Run Comprehensive Tests

```bash
# Run the full test suite
./scripts/deploy_and_test.sh

# Or run specific tests
python scripts/test_orchestrator.py --config test-configs/test_small_batch.json
```

### 5.2 Test Individual Components

```bash
# Test batch orchestrator function
curl -X POST https://$REGION-$PROJECT_ID.cloudfunctions.net/batch-orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "action": "get_total_records",
    "project_id": "'$PROJECT_ID'",
    "dataset": "'$DATASET'",
    "index_table": "'$INDEX_TABLE'"
  }'

# Test workflow execution
./scripts/trigger_workflows.sh test
```

## Step 6: Production Configuration

### 6.1 Update Configuration Files

Update the configuration in `scripts/trigger_workflows.sh`:

```bash
# Edit the script to use your project settings
PROJECT_ID="your-project-id"
REGION="us-central1"
DATASET="your-dataset"
```

### 6.2 Set Up Monitoring

```bash
# Create monitoring dashboard (optional)
# Use Google Cloud Monitoring to create custom dashboards
# Monitor: workflow executions, function invocations, BigQuery jobs
```

### 6.3 Set Up Automated Scheduling

```bash
# Set up daily processing
./scripts/setup_cloud_scheduler.sh create-daily daily-processing 2 30

# Set up weekly processing
./scripts/setup_cloud_scheduler.sh create-weekly weekly-processing 1 3 0
```

## Step 7: Production Deployment

### 7.1 Deploy with Production Settings

```bash
# Update test configurations for production
cp test-configs/test_small_batch.json test-configs/production_batch.json

# Edit production_batch.json with your production settings
# - batch_size: 10000 (or appropriate for your data)
# - max_concurrent_workflows: 5 (or based on your quota)
# - output_table: your production table name
```

### 7.2 Run Production Test

```bash
# Test with production configuration
python scripts/test_orchestrator.py --config test-configs/production_batch.json

# If tests pass, run production workflow
./scripts/trigger_workflows.sh production
```

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**
   ```bash
   # Check IAM permissions
   gcloud projects get-iam-policy $PROJECT_ID
   
   # Verify service account has required roles
   gcloud iam service-accounts get-iam-policy workflow-service-account@$PROJECT_ID.iam.gserviceaccount.com
   ```

2. **Function Deployment Failures**
   ```bash
   # Check function logs
   gcloud functions logs read batch-orchestrator --region=$REGION --limit=50
   
   # Verify source code
   gcloud functions describe batch-orchestrator --region=$REGION
   ```

3. **Workflow Execution Failures**
   ```bash
   # Check workflow execution details
   gcloud workflows executions describe [EXECUTION_NAME] --location=$REGION
   
   # Check workflow definition
   gcloud workflows describe ta-main-workflow --location=$REGION
   ```

4. **BigQuery Issues**
   ```bash
   # Check table schema
   bq show $PROJECT_ID:$DATASET.$INDEX_TABLE
   
   # Check job status
   bq ls -j --max_results=10
   ```

### Logs and Monitoring

```bash
# View all logs
gcloud logging read "resource.type=cloud_function" --limit=50
gcloud logging read "resource.type=workflow" --limit=50

# Monitor specific resources
gcloud monitoring metrics list --filter="resource.type=cloud_function"
```

## Security Considerations

1. **Network Security**
   - Functions use `internal-only` ingress for security
   - VPC connector can be added for additional network isolation

2. **Data Security**
   - All data is encrypted in transit and at rest
   - Service accounts follow principle of least privilege

3. **Access Control**
   - Use IAM roles and policies for access control
   - Regularly audit permissions and access logs

## Maintenance

### Regular Tasks

1. **Monitor Performance**
   - Check function execution times
   - Monitor BigQuery job performance
   - Review workflow execution logs

2. **Update Dependencies**
   - Regularly update Cloud Function dependencies
   - Monitor for security updates

3. **Backup and Recovery**
   - Regular backups of BigQuery data
   - Test disaster recovery procedures

### Scaling Considerations

1. **Function Scaling**
   - Adjust `max-instances` based on load
   - Monitor memory usage and adjust allocation

2. **Workflow Scaling**
   - Adjust `max_concurrent_workflows` based on quota
   - Monitor workflow execution times

3. **Data Scaling**
   - Consider partitioning large tables
   - Implement data retention policies

## Support and Resources

- **Documentation**: See `docs/` directory for detailed documentation
- **Google Cloud Console**: Monitor resources and logs
- **Community**: Google Cloud Community forums
- **Support**: Google Cloud Support (if you have a support plan)
