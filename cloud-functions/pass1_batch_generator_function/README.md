gcloud auth application-default login
gcloud auth login

https://console.cloud.google.com/vertex-ai/batch-predictions?inv=1&invt=Ab2Oug&project=bbyus-ana-puca-d01

Here are the correct ways to run your code:

Option 1: From the project root (recommended)
```bash
cd /Users/a660709/git/services-transcription-analytics/pass1_batch_generator
source .venv/bin/activate
python src/main.py
```

Option 2: From the src directory
```bash
cd /Users/a660709/git/services-transcription-analytics/pass1_batch_generator/src
source ../.venv/bin/activate
python main.py
```

Option 3: Using uv run (easiest)
```bash
cd /Users/a660709/git/services-transcription-analytics/pass1_batch_generator
uv run python src/main.py
```
```bash
gcloud auth application-default login

```

https://code.bestbuy.com/wiki/display/EDPUG/GCP+Service+Catalog

uv init mcp-server-demo
cd mcp-server-demo
c .
uv venv --python 3.12
source .venv/bin/activate
uv add fastapi "mcp[cli]" python-dotenv tavily-python

# to run basic web_search mcp server:
uv run server.py

# to run FastAPI app exposing math and echo servers:
uv run fastapi_example/server.py

# to run mcp inspector
uv run mcp dev server.py

**Delete Function**
from the services-transcription-analytics folder, run this command:
```bash
gcloud functions delete pass1-batch-generator --region=us-central1 --quiet
```
NOTE: it does bring up back to git folder, so you will need to cd back into folder

{
  "batch_bucket": "puca-vertex-ai-batches-d01",
  "batch_output_bucket": "puca-vertex-ai-batch-output-d01",
  "dataset": "ORDER_ANALYSIS",
  "index_table": "transcription_pass_2",
  "model": "gemini-2.5-flash-lite",
  "output_table": "transcription_analyzed_transcripts",
  "project_id": "bbyus-ana-puca-d01",
  "region": "us-central1",
  "where_clause": "WHERE row_num between 1 and 6"
}