# Transcription Analytics Workflow Flow Diagram

This Mermaid diagram shows the high-level flow through all workflows when you run `trigger_workflows.sh custom`.

```mermaid
graph TD
    A[User runs trigger_workflows.sh custom] --> B[ta-main-workflow starts]
    
    B --> C[Initialize Parameters<br/>- batch_size<br/>- max_concurrent<br/>- start_row<br/>- execution_id]
    
    C --> D[Create Batch Plan<br/>Call batch-orchestrator function]
    
    D --> E{Any batches<br/>to process?}
    
    E -->|No| F[End: No new records]
    E -->|Yes| G[Start ta-manager-workflow]
    
    G --> H[Organize batches into chunks<br/>based on max_concurrent]
    
    H --> I[Start multiple ta-sub-workflow<br/>instances in parallel]
    
    I --> J1[Worker 1:<br/>ta-sub-workflow]
    I --> J2[Worker 2:<br/>ta-sub-workflow]
    I --> J3[Worker N:<br/>ta-sub-workflow]
    
    J1 --> K1[Generate batch file<br/>Call pass1-batch-generator]
    J2 --> K2[Generate batch file<br/>Call pass1-batch-generator]
    J3 --> K3[Generate batch file<br/>Call pass1-batch-generator]
    
    K1 --> L1[Submit to Vertex AI<br/>Batch Prediction Job]
    K2 --> L2[Submit to Vertex AI<br/>Batch Prediction Job]
    K3 --> L3[Submit to Vertex AI<br/>Batch Prediction Job]
    
    L1 --> M1[Wait for AI Processing<br/>Poll every 30 seconds]
    L2 --> M2[Wait for AI Processing<br/>Poll every 30 seconds]
    L3 --> M3[Wait for AI Processing<br/>Poll every 30 seconds]
    
    M1 --> N1{Job Status}
    M2 --> N2{Job Status}
    M3 --> N3{Job Status}
    
    N1 -->|Success| O1[Process Results<br/>Call pass1-batch-processor]
    N1 -->|Failed| P1[Log Error & End]
    
    N2 -->|Success| O2[Process Results<br/>Call pass1-batch-processor]
    N2 -->|Failed| P2[Log Error & End]
    
    N3 -->|Success| O3[Process Results<br/>Call pass1-batch-processor]
    N3 -->|Failed| P3[Log Error & End]
    
    O1 --> Q1[Save to BigQuery<br/>transcription_analyzed_transcripts]
    O2 --> Q2[Save to BigQuery<br/>transcription_analyzed_transcripts]
    O3 --> Q3[Save to BigQuery<br/>transcription_analyzed_transcripts]
    
    Q1 --> R[All Workers Complete]
    Q2 --> R
    Q3 --> R
    
    R --> S[Workflow Execution Complete<br/>Results available in BigQuery]
    
    %% Styling
    classDef userAction fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef workflow fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef function fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef ai fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef storage fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef decision fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef endState fill:#ffebee,stroke:#c62828,stroke-width:2px
    
    class A userAction
    class B,G,J1,J2,J3 workflow
    class D,K1,K2,K3,O1,O2,O3 function
    class L1,L2,L3,M1,M2,M3 ai
    class Q1,Q2,Q3 storage
    class E,N1,N2,N3 decision
    class F,P1,P2,P3,R,S endState
```

## Key Components Explained

### 🎯 **User Action** (Blue)
- **trigger_workflows.sh custom**: The entry point where you specify batch size, concurrency, and start row

### 🔄 **Workflows** (Purple)
- **ta-main-workflow**: Master coordinator that sets up parameters and starts the manager
- **ta-manager-workflow**: Organizes batches and starts multiple workers in parallel
- **ta-sub-workflow**: Individual worker that processes one batch of data

### ⚙️ **Cloud Functions** (Green)
- **batch-orchestrator**: Creates the batch plan with row ranges
- **pass1-batch-generator**: Prepares data files for AI processing
- **pass1-batch-processor**: Saves AI results back to database

### 🤖 **AI Processing** (Orange)
- **Vertex AI Batch Prediction**: Google's AI service that analyzes transcripts using Gemini model
- **Polling**: Waits for AI to complete (can take 30 minutes to several hours)

### 💾 **Storage** (Pink)
- **BigQuery**: Final destination where all analyzed results are stored

### ❓ **Decision Points** (Yellow)
- **Any batches to process?**: Checks if there's work to do
- **Job Status**: Monitors AI processing success/failure

### 🏁 **End States** (Red)
- **No new records**: When there's nothing to process
- **Errors**: When something goes wrong
- **Complete**: When all processing is finished

## Parallel Processing Flow

The diagram shows how multiple workers (J1, J2, J3, etc.) run simultaneously, each processing different batches of data. This parallel approach significantly speeds up the overall processing time.

## Custom Run Specifics

When you use `trigger_workflows.sh custom [batch_size] [concurrent] [start_row]`:
- You control exactly how many records per batch
- You control how many batches run at the same time
- You can start from any row number (useful for resuming interrupted processing)

The flow remains the same, but your parameters determine:
- How many workers are created
- How much data each worker processes
- Where processing begins
