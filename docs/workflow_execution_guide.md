# Transcription Analytics Workflow Execution Guide

## Overview

This document explains what happens when you run the `trigger_workflows.sh` script in simple, easy-to-understand terms. Think of it as a step-by-step guide to how your transcription analysis system processes data.

## What the Script Does

The `trigger_workflows.sh` script is like a remote control for your data processing system. It tells Google Cloud to start analyzing customer service call transcripts using AI. You can choose different "modes" depending on how much data you want to process and how fast you want it done.

## Available Commands

### 1. Test Run (`./trigger_workflows.sh test`)
- **What it does**: Processes a small sample of data (100 records)
- **Use case**: Testing to make sure everything works before running on real data
- **Speed**: Fast (2 batches running at the same time)

### 2. Production Run (`./trigger_workflows.sh production`)
- **What it does**: Processes the full dataset (10,000 records per batch)
- **Use case**: Regular processing of all your customer service data
- **Speed**: Balanced (5 batches running at the same time)

### 3. Incremental Run (`./trigger_workflows.sh incremental [start] [end] [batch_size] [concurrent]`)
- **What it does**: Processes a specific range of records
- **Use case**: Processing new data that came in since your last run
- **Example**: `./trigger_workflows.sh incremental 1 50000 5000 3` processes records 1-50,000 in batches of 5,000

### 4. Single Batch (`./trigger_workflows.sh single [start] [end] [exec_id] [batch_id]`)
- **What it does**: Processes just one small batch of data
- **Use case**: Debugging or testing a specific range of records

### 5. Custom Run (`./trigger_workflows.sh custom [batch_size] [concurrent] [start_row]`)
- **What it does**: Lets you set your own parameters
- **Use case**: When you need specific settings for your situation

## The Complete Workflow Process

When you run any of these commands, here's exactly what happens behind the scenes:

### Phase 1: Setup and Planning (ta-main-workflow.yaml)

#### Step 1: Initialize Parameters
- **What happens**: The system reads your command and sets up all the configuration
- **In simple terms**: Like setting up a recipe with all the ingredients and instructions
- **Key settings**:
  - How many records to process at once (batch size)
  - How many batches can run simultaneously (concurrency)
  - Which row to start from (start_row)
  - Which database tables to use

#### Step 2: Create Batch Plan
- **What happens**: The system calls a "batch orchestrator" function to figure out how to divide the work
- **In simple terms**: Like a project manager breaking down a big job into smaller, manageable tasks
- **The orchestrator**:
  - Looks at your source data table
  - Calculates how many batches are needed
  - Creates a plan with specific row ranges for each batch
  - Example: Batch 1 processes rows 1-10,000, Batch 2 processes rows 10,001-20,000, etc.

#### Step 3: Check if Work is Needed
- **What happens**: The system checks if there are actually any batches to process
- **In simple terms**: Like checking if there's any work to do before starting
- **If no work**: The workflow ends with "No new records to process"

#### Step 4: Start the Manager
- **What happens**: The system starts a "manager workflow" that will coordinate all the actual processing
- **In simple terms**: Like hiring a supervisor to oversee all the workers

### Phase 2: Batch Management (ta-manager-workflow.yaml)

#### Step 5: Organize Batches into Groups
- **What happens**: The manager takes all the batches and groups them for parallel processing
- **In simple terms**: Like organizing workers into teams that can work at the same time
- **Example**: If you have 10 batches and want 3 running at once, it creates groups of 3, 3, 3, and 1

#### Step 6: Start Worker Workflows in Parallel
- **What happens**: For each group, the manager starts multiple "worker workflows" simultaneously
- **In simple terms**: Like having multiple teams start working on different parts of the project at the same time
- **Each worker gets**:
  - A specific range of records to process
  - A unique batch ID
  - All the configuration it needs

### Phase 3: Individual Batch Processing (ta-sub-workflow.yaml)

Each worker workflow goes through these steps:

#### Step 7: Prepare the Data
- **What happens**: The worker calls a "batch generator" function to create the input file
- **In simple terms**: Like preparing a shopping list with all the items you need to buy
- **The generator**:
  - Queries the database for the specific records assigned to this batch
  - Formats the data for AI processing
  - Saves it to a file in Google Cloud Storage
  - Returns the file location

#### Step 8: Submit to AI Service
- **What happens**: The worker submits the prepared data to Google's AI service (Vertex AI)
- **In simple terms**: Like sending your shopping list to a smart assistant that will analyze each item
- **The AI service**:
  - Uses the Gemini model to analyze each transcript
  - Identifies key themes, sentiment, and insights
  - Processes all records in the batch
  - Saves results to another file

#### Step 9: Wait for AI Processing
- **What happens**: The worker waits for the AI to finish processing (can take 30 minutes to several hours)
- **In simple terms**: Like waiting for the smart assistant to finish analyzing your shopping list
- **The system**:
  - Checks the job status every 30 seconds
  - Can wait up to 12 hours for completion
  - Handles various states (running, succeeded, failed, cancelled)

#### Step 10: Process Results
- **What happens**: Once AI processing is complete, the worker calls a "batch processor" function
- **In simple terms**: Like taking the AI's analysis and organizing it into your final report
- **The processor**:
  - Reads the AI's output file
  - Matches results back to original records
  - Saves everything to your final database table
  - Handles any errors or retries needed

### Phase 4: Completion and Monitoring

#### Step 11: Track Progress
- **What happens**: All workflows log their progress and results
- **In simple terms**: Like having each team report back on what they accomplished
- **You can monitor**:
  - Which batches are running, completed, or failed
  - How many records have been processed
  - Any errors that occurred

#### Step 12: Final Results
- **What happens**: All processed data is saved to your final database table
- **In simple terms**: Like having all your analyzed data organized and ready to use
- **The final table contains**:
  - Original transcript data
  - AI-generated insights and themes
  - Processing metadata (when it was processed, which batch, etc.)

## Monitoring Your Workflow

After running the script, you can check progress using these commands:

```bash
# See recent workflow executions
gcloud workflows executions list --workflow=ta-main-workflow --location=us-central1 --limit=10

# Check specific execution details
gcloud workflows executions describe [EXECUTION_NAME] --location=us-central1

# View function logs
gcloud functions logs read batch-orchestrator --region=us-central1 --limit=50

# Check your results in BigQuery
# (You'll need to run SQL queries in the Google Cloud Console)
```

## What Each Component Does

### Cloud Functions (Serverless Code)
- **batch-orchestrator**: Plans how to divide the work into batches
- **pass1-batch-generator**: Prepares data files for AI processing
- **pass1-batch-processor**: Saves AI results back to your database

### Workflows (Orchestration)
- **ta-main-workflow**: The main coordinator that starts everything
- **ta-manager-workflow**: Manages multiple batches running in parallel
- **ta-sub-workflow**: Processes individual batches

### AI Service
- **Vertex AI Batch Prediction**: Google's AI service that analyzes your transcripts using the Gemini model

### Storage
- **Google Cloud Storage**: Stores temporary files during processing
- **BigQuery**: Your final database where all results are saved

## Typical Timeline

- **Test run (100 records)**: 5-15 minutes
- **Small production run (10,000 records)**: 1-3 hours
- **Large production run (100,000+ records)**: 6-24 hours

The exact time depends on:
- How many records you're processing
- How many batches run in parallel
- Current load on Google's AI services
- Complexity of your transcripts

## Troubleshooting

If something goes wrong:

1. **Check the logs**: Use the monitoring commands above
2. **Look for error messages**: They'll tell you what went wrong
3. **Try a smaller batch**: Use the test command to verify everything works
4. **Check your data**: Make sure your source table has the expected data

## Summary

The `trigger_workflows.sh` script is your gateway to processing customer service transcripts with AI. It automatically:

1. **Plans** how to divide your data into manageable chunks
2. **Coordinates** multiple AI processing jobs running in parallel
3. **Monitors** progress and handles any issues
4. **Delivers** analyzed results to your database

Think of it as having a smart project manager that can handle thousands of AI workers, all analyzing your customer service data to help you understand what your customers are saying and feeling.
