# Single Batch Lifecycle - GCP Services Flow

This diagram shows the detailed lifecycle of a single batch through all GCP services, focusing on data flow between Cloud Storage, Cloud Functions, Vertex AI, and BigQuery.

```mermaid
graph TD
    A[ta-sub-workflow starts] --> B[Initialize Parameters<br/>- batch_id<br/>- where_clause<br/>- model settings]
    
    B --> C[Call pass1-batch-generator<br/>Cloud Function]
    
    C --> D[Query BigQuery<br/>transcription_pass_2 table<br/>WHERE row_num between X and Y]
    
    D --> E[Format data for AI<br/>Create JSONL structure<br/>with prompts and transcripts]
    
    E --> F[Upload to Cloud Storage<br/>gs://puca-vertex-ai-batches-d01/<br/>batch/analyze-batch-requests-TIMESTAMP-batch_id.jsonl]
    
    F --> G[Submit to Vertex AI<br/>Batch Prediction Job<br/>publishers/google/models/gemini-2.5-flash-lite]
    
    G --> H[Vertex AI Processing<br/>- Reads from input bucket<br/>- Processes each transcript<br/>- Generates AI analysis]
    
    H --> I[Vertex AI writes results<br/>to Cloud Storage<br/>gs://puca-vertex-ai-batch-output-d01/<br/>analyze-batch-output/]
    
    I --> J[Poll Vertex AI job status<br/>Every 30 seconds<br/>Up to 12 hours timeout]
    
    J --> K{Job Status}
    
    K -->|SUCCEEDED| L[Call pass1-batch-processor<br/>Cloud Function]
    K -->|FAILED| M[Log error and end]
    K -->|RUNNING| J
    
    L --> N[Download results from<br/>Cloud Storage output bucket<br/>Read JSONL prediction files]
    
    N --> O[Parse AI responses<br/>Extract structured data<br/>- callSummary<br/>- callSentiment<br/>- reasonForCall<br/>- etc.]
    
    O --> P[Query BigQuery lookup table<br/>Match results to original records<br/>using phone_number_token]
    
    P --> Q[Insert processed data<br/>into BigQuery<br/>transcription_analyzed_transcripts table]
    
    Q --> R[Batch processing complete<br/>Results available in BigQuery]
    
    %% Data flow annotations
    D -.->|SQL Query| D1[(BigQuery<br/>transcription_pass_2<br/>Source Data)]
    F -.->|JSONL Upload| F1[(Cloud Storage<br/>Input Bucket<br/>puca-vertex-ai-batches-d01)]
    I -.->|AI Results| I1[(Cloud Storage<br/>Output Bucket<br/>puca-vertex-ai-batch-output-d01)]
    Q -.->|Final Results| Q1[(BigQuery<br/>transcription_analyzed_transcripts<br/>Final Table)]
    
    %% Styling
    classDef workflow fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef function fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef ai fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef storage fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef bigquery fill:#e3f2fd,stroke:#0277bd,stroke-width:2px
    classDef decision fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef endState fill:#ffebee,stroke:#c62828,stroke-width:2px
    
    class A,B workflow
    class C,L function
    class G,H,I ai
    class F1,I1 storage
    class D1,Q1 bigquery
    class K decision
    class M,R endState
```

## Detailed GCP Service Interactions

### 🔄 **Workflow Orchestration**
- **ta-sub-workflow**: Google Cloud Workflows service that coordinates the entire batch lifecycle
- **Parameters**: Receives batch_id, row ranges, model settings, and bucket configurations

### ⚙️ **Cloud Functions**

#### **pass1-batch-generator Function**
1. **BigQuery Query**: 
   ```sql
   SELECT * FROM transcription_pass_2 
   WHERE row_num BETWEEN start_row AND end_row
   ```
2. **Data Formatting**: Converts transcript data into JSONL format with AI prompts
3. **Cloud Storage Upload**: Saves formatted data to input bucket with timestamped filename

#### **pass1-batch-processor Function**
1. **Cloud Storage Download**: Retrieves AI results from output bucket
2. **Data Parsing**: Extracts structured insights from AI responses
3. **BigQuery Lookup**: Matches results back to original records
4. **BigQuery Insert**: Saves final processed data to destination table

### 🤖 **Vertex AI Batch Prediction**
- **Input**: Reads JSONL files from `puca-vertex-ai-batches-d01` bucket
- **Model**: Uses `publishers/google/models/gemini-2.5-flash-lite`
- **Processing**: Analyzes each transcript for:
  - Call summary and sentiment
  - Reason for call and intent classification
  - Language detection and tone analysis
- **Output**: Writes results to `puca-vertex-ai-batch-output-d01` bucket

### 💾 **Cloud Storage Buckets**

#### **Input Bucket**: `puca-vertex-ai-batches-d01`
- **Purpose**: Stores formatted transcript data ready for AI processing
- **File Format**: JSONL (JSON Lines)
- **Naming**: `batch/analyze-batch-requests-{timestamp}-{batch_id}.jsonl`
- **Content**: Each line contains a transcript with AI analysis prompts

#### **Output Bucket**: `puca-vertex-ai-batch-output-d01`
- **Purpose**: Stores AI-generated analysis results
- **File Format**: JSONL with AI predictions
- **Naming**: `analyze-batch-output/{job_id}/predictions.jsonl`
- **Content**: Structured analysis results for each transcript

### 🗄️ **BigQuery Tables**

#### **Source Table**: `transcription_pass_2`
- **Purpose**: Contains original transcript data
- **Query**: Filtered by row ranges to get specific batches
- **Key Fields**: `phone_number_token`, `transcript`, `direction`, etc.

#### **Final Table**: `transcription_analyzed_transcripts`
- **Purpose**: Stores AI-analyzed results
- **Content**: Original data + AI insights (sentiment, intent, summary, etc.)
- **Key Fields**: All original fields plus AI-generated analysis fields

## Data Flow Summary

1. **Extract**: Query BigQuery for transcript data in specified row range
2. **Transform**: Format data with AI prompts into JSONL structure
3. **Load**: Upload formatted data to Cloud Storage input bucket
4. **Process**: Submit to Vertex AI for batch prediction analysis
5. **Retrieve**: Download AI results from Cloud Storage output bucket
6. **Enrich**: Match AI results back to original records via BigQuery lookup
7. **Store**: Insert enriched data into final BigQuery table

## Key Performance Considerations

- **Parallel Processing**: Multiple batches can run simultaneously
- **Batch Size**: Configurable (typically 10,000 records per batch)
- **Timeout Handling**: 12-hour maximum wait for AI processing
- **Error Handling**: Retry logic and graceful failure handling
- **Memory Management**: Chunked processing for large result files
- **Cost Optimization**: Efficient use of Vertex AI batch prediction pricing

## Monitoring Points

- **Cloud Storage**: Monitor upload/download operations and file sizes
- **Vertex AI**: Track job status, processing time, and success rates
- **BigQuery**: Monitor query performance and data insertion rates
- **Cloud Functions**: Check execution logs and error rates
- **Workflows**: Monitor overall orchestration and step completion
