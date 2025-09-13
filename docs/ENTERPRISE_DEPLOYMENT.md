# Enterprise Deployment Guide for Batch Orchestrator Function

This guide explains how to deploy the batch orchestrator function in an enterprise environment where automated deployment is restricted.

## Overview

The `batch_orchestrator` function is a **required component** for the batch processing system. It handles:
- Progress tracking and monitoring
- Batch plan creation and management
- Status updates and reporting
- Concurrency management

## Function Requirements

### **Function Name**
- **Name**: `batch-orchestrator`
- **URL**: `https://{region}-{project_id}.cloudfunctions.net/batch-orchestrator`

### **Runtime Configuration**
- **Runtime**: Python 3.11
- **Trigger**: HTTP
- **Entry Point**: `batch_orchestrator`
- **Memory**: 512MB
- **Timeout**: 540 seconds (9 minutes)
- **Authentication**: Allow unauthenticated (or configure your preferred auth method)

### **Dependencies**
```txt
functions-framework==3.*
google-cloud-bigquery==3.*
google-auth==2.*
requests==2.*
```

## Deployment Steps

### **Step 1: Prepare Function Code**

1. **Copy the function code** from `batch_orchestrator_function/src/main.py`
2. **Create requirements.txt** with the dependencies listed above
3. **Ensure the function has the correct entry point**: `batch_orchestrator`

### **Step 2: Deploy Using Your Enterprise Process**

Use your standard enterprise deployment process. The function should:

1. **Be deployed to the correct region**: `us-central1`
2. **Be deployed to the correct project**: `bbyus-ana-puca-d01`
3. **Have the correct name**: `batch-orchestrator`
4. **Be accessible via HTTP trigger**

### **Step 3: Verify Deployment**

After deployment, verify the function is accessible:

```bash
# Check if function exists
gcloud functions describe batch-orchestrator --region=us-central1 --project=bbyus-ana-puca-d01

# Test the function endpoint
curl -X POST https://us-central1-bbyus-ana-puca-d01.cloudfunctions.net/batch-orchestrator \
  -H "Content-Type: application/json" \
  -d '{"action": "get_total_records", "project_id": "bbyus-ana-puca-d01", "dataset": "ORDER_ANALYSIS", "index_table": "transcription_pass_2"}'
```

## Function Endpoints

The function supports the following actions:

### **1. get_total_records**
```json
{
  "action": "get_total_records",
  "project_id": "bbyus-ana-puca-d01",
  "dataset": "ORDER_ANALYSIS",
  "index_table": "transcription_pass_2"
}
```

### **2. create_batch_plan**
```json
{
  "action": "create_batch_plan",
  "execution_id": "exec_20240115_123456",
  "total_records": 1000,
  "batch_size": 100,
  "project_id": "bbyus-ana-puca-d01",
  "dataset": "ORDER_ANALYSIS",
  "start_row": 1,
  "record_limit": 500,
  "max_batches": 1000
}
```

**Parameters:**
- `execution_id` (required): Unique identifier for this execution
- `total_records` (required): Total number of records to process
- `batch_size` (optional, default: 10): Number of records per batch
- `project_id` (required): Google Cloud project ID
- `dataset` (required): BigQuery dataset name
- `start_row` (optional, default: 1): Starting row number for batch processing
- `record_limit` (optional): Maximum number of records to plan for in this call. Useful for small test runs.
- `max_batches` (optional, default: 1000): Hard cap on the number of batches returned to prevent large memory usage.



## Required Permissions

The function needs the following IAM permissions:

### **BigQuery Permissions**
- `bigquery.jobs.create`
- `bigquery.tables.get`
- `bigquery.tables.updateData`
- `bigquery.tables.create`

### **Service Account**
The function should run with a service account that has:
- BigQuery Data Editor role on the dataset
- BigQuery Job User role

## Testing the Function

After deployment, you can test the function manually:

```bash
# Test 1: Get total records
curl -X POST https://us-central1-bbyus-ana-puca-d01.cloudfunctions.net/batch-orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "action": "get_total_records",
    "project_id": "bbyus-ana-puca-d01",
    "dataset": "ORDER_ANALYSIS",
    "index_table": "transcription_pass_2"
  }'

# Test 2: Create batch plan
curl -X POST https://us-central1-bbyus-ana-puca-d01.cloudfunctions.net/batch-orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "action": "create_batch_plan",
    "execution_id": "test_exec_123",
    "total_records": 100,
    "batch_size": 25,
    "project_id": "bbyus-ana-puca-d01",
    "dataset": "ORDER_ANALYSIS",
    "start_row": 1,
    "record_limit": 50
  }'

# Test 3: Create batch plan with custom start row
curl -X POST https://us-central1-bbyus-ana-puca-d01.cloudfunctions.net/batch-orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "action": "create_batch_plan",
    "execution_id": "test_exec_124",
    "total_records": 100,
    "batch_size": 25,
    "project_id": "bbyus-ana-puca-d01",
    "dataset": "ORDER_ANALYSIS",
    "start_row": 1001,
    "record_limit": 50
  }'
```

## Troubleshooting

### **Common Issues**

1. **Function not found**
   - Verify the function name is exactly `batch-orchestrator`
   - Check the region and project ID

2. **Permission denied**
   - Ensure the function has BigQuery permissions
   - Check the service account configuration

3. **Timeout errors**
   - Increase the function timeout to 540 seconds
   - Check BigQuery query performance

4. **Import errors**
   - Verify all dependencies are installed
   - Check the requirements.txt file

### **Logs and Monitoring**

```bash
# View function logs
gcloud functions logs read batch-orchestrator --region=us-central1 --limit=50

# Monitor function metrics
gcloud functions describe batch-orchestrator --region=us-central1
```

## Integration with Testing Script

Once deployed, the testing script will:

1. **Check if the function exists** before running tests
2. **Skip deployment** if the function is already available
3. **Verify the function is accessible** before proceeding
4. **Use the function** for all orchestration tasks during testing

## Next Steps

After deploying the function:

1. **Run the testing script**: `./scripts/deploy_and_test.sh`
2. **Verify all tests pass**
3. **Proceed with production deployment**
4. **Monitor function performance** during large-scale processing

## Support

If you encounter issues with the function deployment:

1. **Check the logs** for specific error messages
2. **Verify permissions** and service account configuration
3. **Test individual endpoints** using curl commands
4. **Contact your enterprise DevOps team** for deployment assistance
