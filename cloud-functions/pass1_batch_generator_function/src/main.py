import functions_framework
import json
import base64
import os
from google.auth import default
import google.auth.transport.requests
from google import genai
from gcp_clients import get_bq_client, get_storage_client


def get_summary_prompt(transcript: str, direction: str) -> str:
    """Get the summary prompt template."""
    return f"""
    You are an AI assistant tasked with analyzing Best Buy customer call center transcripts. Your goal is to extract specific information based on a careful, holistic review of the entire interaction.
    
    **Input Details:**
    * transcript: This is a transcribed version of one of the following three modes of interaction customers can have with Best Buy's support center. For each of these modes, the transcript should clearly indicate who is speaking, so you can infer from that 
     what type of interaction the given transcript is.
        * IVR:  This is a transcript of a customer interacting with Best Buy's IVR system. The content may not always be complete but do your best to extract as much information as possible.
        * ChatBot: This is a transcript of a customer interacting with Best Buy's SMS ChatBot.
        * Human Agent: This is a transcript of a customer interacting with a human agent.

     * direction: There should only be 2 values for this (INBOUND or OUTBOUND), however, for IVR and ChatBot, the direction will typically not be provided so you can just assume the customer initiated those interactions. 
     For voice calls, if the call is initiated by the customer, then the value should be INBOUND. If the call is initiated by the agent, then the value should be OUTBOUND. Therefore, 
    please take this value into account when analyzing the transcript. For example, if the direction is OUTBOUND and the transcript clearly indicates that it was the Agent who
    called the customer, then your summaries should not indicate that the customer initiated the call. That being said, do not assume that the direction is always correct, you must also use you best judgement based on the contents of the transcript.
    If it is unclear then simply assume it was the customer who initiated the call.
    
    **Perform the following actions for each transcript:**

    1.  **callSummary:**
        *   Write a 3-4 sentence summarizing the core reason(s) for the call, key points and topics being discussed during the call, and any clear customer emotions (e.g., frustration). Stick strictly to facts from the transcript.
        *   Do not include any customer identifying information such as first or last name. (e.g., say "The customer is..." not "The customer, Mary is...").
    2.  **callSentiment:**
        *   Determine the customer's emotional sentiment at two key points: the beginning of the call and the end of the call.
        *   **`incoming`**: The customer's sentiment at the *start* of the interaction, reflecting their feelings about the issue that prompted the call.
        *   **`outgoing`**: The customer's sentiment at the *end* of the interaction, after the resolution or agent's response.
        *   For both `incoming` and `outgoing`, choose **ONLY ONE** from: "happy", "angry", "worried", "frustrated", "neutral".
    3.  **callSentimentSummary:**
        *   Provide a brief summary that justifies why you chose the `incoming` and `outgoing` callSentiment values. The summary should reference specific moments or statements from both the beginning and the end of the transcript to support your assessment of the customer's emotional journey. 
    4.  **callTone:**
        *   Determine the customer's overall tone during the call.
        *   Choose **ONLY ONE** from: "polite", "rude", "neutral".
    5.  **languageCode:**
        *   Identify the primary language spoken using the ISO 639-1 code (e.g., "en", "es").
        *   If multiple languages are present, prioritize the non-English one if it's significantly used.
    6.  **reasonForCall:**
        *   Determine the **single, primary reason** the customer initiated the call or SMS. Focus on why they *originally dialed the number* or *sent the SMS*, before the conversation may have shifted or evolved.
        If the direction of the call is clearly OUTBOUND, then the reasonForCall should reflect the reason why the agent called the customer.
        *   Ignore any discussions, solutions, or new topics that come up after the customer's initial statement of their reason for contacting support; focus only on the original reason the customer reached out.
        *   You need to extract and classify the following fields that will comprise the reasonForCall:
            *   **`summary`**: State the customer's single **primary intent** for calling in 1-2 sentences. Capture precisely *why* the customer initiated the call and any relevant details that can add insightful context as to the reason why the customer called.
                If the discussion pivots to another subject, your focus must remain on the customer's original intent. Do not include any content that indicates what the agent did for the customer, focus only on the customer's intent for calling.
            *   **`intent`**: The value you choose for intent must align with the reason why the customer called. The value you choose for intent is critically important so please take your time and be extremely thoughtful as to which value you choose. 
                Below is a list of the most common intents that customers have when calling Best Buy, please try to limit your choice for intent from the list below.  
                If none of the intents match to the customer's intent, then using 2-3 words (in-store and in-home count as one word), distill down the customer's primary intent for calling. Keep the intent as general as possible, but still specific enough to be meaningful.
                *   `account inquiry`
                *   `appointment inquiry`: Use this intent only if the customer is calling with a general appointment related inquiry Do not use this if the customer is calling to get either the in-home delivery status or in-store pickup status of their appointment. 
                *   `cancel autotech appointment`
                *   `cancel in-home appointment`
                *   `cancel in-store appointment`
                *   `cancel membership`
                *   `cancel protection plan`
                *   `cancel purchase order`
                *   `change purchase order`
                *   `compensation inquiry`
                *   `contact store`
                *   `credit card inquiry`
                *   `file complaint`
                *   `general inquiry`
                *   `gift card inquiry`
                *   `in-home delivery status`
                *   `in-store pickup status`
                *   `job application inquiry`
                *   `language assistance`
                *   `lost and found inquiry`
                *   `membership inquiry`
                *   `purchase order refund status`
                *   `purchase order status inquiry`: Do not use this intent if the customer is calling to check the delivery status or other status related to an in-home or in-store appointment. Instead use the `in-home delivery status`, `in-store pickup status`, or `appointment inquiry` intents accordingly.
                *   `place order`
                *   `price match inquiry`
                *   `product availability inquiry`
                *   `product exchange inquiry`
                *   `product inquiry`
                *   `product installation help`
                *   `product parts inquiry`
                *   `product pre-order inquiry`
                *   `product price inquiry`
                *   `product repair inquiry`
                *   `product replacement inquiry`
                *   `product troubleshooting`: Only assign this if the customer truly wants to **fix/resolve** a product issue on the call. DO NOT assign if the customer is calling to schedule a repair/service appointment to address the product issue, is calling to see if their product issue would be covered under their protection plan/warranty, or if they are calling to see if their defective product can be exchanged, canceled, or returned/refunded.
                *   `protection plan inquiry`
                *   `receipt inquiry`
                *   `recycling inquiry`
                *   `repair status inquiry`
                *   `reschedule autotech appointment`
                *   `reschedule in-home appointment`
                *   `reschedule in-store appointment`
                *   `return purchase order`
                *   `scam inquiry`
                *   `schedule autotech appointment`
                *   `schedule in-home delivery appointment`
                *   `schedule in-home installation/setup appointment`
                *   `schedule in-home service/repair appointment`
                *   `schedule in-store appointment`
                *   `trade-in inquiry`
                *   `warranty inquiry`
                *   `website issue`
            *   **`inquiryQuestion`**: If the `intent` you chose is an inquiry (e.g., ends in "inquiry" or "status"), capture the **specific question** the customer asked, preserving its literal intent. Do not over-generalize. If the customer also provides a direct reason for asking, incorporate that reason into a single, concise and cohesive summary of the inquiry.
                *   **Crucial Point on Specificity**: If the customer asks "What time is my delivery?", your response must be about the *time* (e.g., "The customer is asking for the specific time of their delivery."), not a general status. The goal is to capture exactly what the customer wants to know.
                *   **Example with Reason**: If the customer asks, "What time is my delivery?" and adds, "I never got a text," your output should be a summary like: "The customer is asking for their delivery time because they did not receive a text notification with the time window."
                *   **Example without Reason**: If the customer just asks, "What time is my delivery?", your output should be: "The customer is asking for the specific time of their delivery."
                *   You may clean up grammar to make the question asked more coherent. 
                *   If the intent is not an inquiry, this field must be `null`.
            *   **`product`**: If the customer is calling about a specific product, extract what you can for the product (name/brand/type) but based only on the information provided in the transcript (see below for formatting instructions). 
                   You can only extract one product for this field, so if the customer happens to mention multiple products, choose the one that is most critical to the reason why the customer is calling. If the customer is not calling about a specific product, leave this field blank.
                *   **Formatting Instructions:**
                *   Use `PascalCase` for general product types (e.g., `Washing Machine`, `Laptop`, `Headphones`).
                *   Use `ALL CAPS` for specific brands or acronyms that are commonly capitalized (e.g., `LG TV`, `HP Laptop`, `GE Refrigerator`, `SONOS Speaker`).
                *   If a brand and type are mentioned, include both in the product field value.
            *   **`productCategory`**: Based on the `product` identified, assign a high-level product category. If no product is identified for the call reason, this field should be null.
                *   Please use one of the following categories if the product fits:
                    *   **`Appliances`**: Use for products like dishwashers, washers, dryers, stoves, microwaves, ranges, refrigerators, etc.
                    *   **`Home Theater`**: Use for products like Large TVs, soundbars, projectors, AV receivers, etc.
                    *   **`Computing`**: Use for products like computers, laptops, printers, monitors, networking gear, etc.
                    *   **`Gaming`**: Use for gaming consoles, video games, or related accessories (e.g., `Sony Playstation 5`, `Nintendo Switch`).
                    *   **`Fitness`**: Use for fitness equipment like treadmills, ellipticals, etc.
                    *   **`Furniture`**: Use for indoor or outdoor furniture.
                *   If the product does not align with any of these categories, assign a different general category that you deem appropriate. The category must be one or two words at most (e.g., `Mobile Phone`, `Cameras`).

    7.  **agentResponse:**
        *   This field is certainly applicable for all human agent interactions. For IVR if you can determine where the customer was routed then use that in both the summary and action. For Chatbot interactions use your best judgement as to whether or not there is enogh information
        to warrant an agent response.
        *   This requires three pieces of information within a nested object:
            *   **`resolved`**: Determine if the agent's actions and responses effectively addressed the customer's **primary intent** (identified in `reasonForCall`) *within this specific interaction*. Output "yes", "partially", or "no" based *strictly* on the following criteria:      

                *   **Output "yes" if EITHER of these is true:**
                    1.  **Intent Fully Achieved:** The agent directly resolved the customer's primary intent, providing the specific information or completing the action sought by the customer, thereby *fulfilling their stated goal for that intent during this interaction* (e.g., product confirmed in stock and available for purchase, order successfully cancelled, issue fully fixed via troubleshooting on the call).
                    2.  **Agent Action Complete & Definitive (Even if Outcome Not Ideal):** The agent provided a complete, procedurally correct, and definitive response or took all appropriate final actions *within their scope for this interaction*, even if the ultimate outcome wasn't what the customer desired or requires further non-agent steps. The agent has done *everything they are expected to do for this query*, and no further direct action from *this agent* regarding the primary intent is pending or possible.
                        *   Examples:
                            *   Correctly informing the customer a product is definitively out of stock (providing available restock info if per procedure).
                            *   Correctly explaining a policy that prevents the customer's specific request.
                            *   Successfully troubleshooting but the issue requires an in-home repair, and the agent correctly scheduled that appointment or provided clear, complete instructions for the customer to do so if self-service is the process.
                            *   The query was fully investigated, and the agent provided the complete and final answer available to them.

                *   **Output "partially" if:**
                    *   The agent made progress on the customer's primary intent, but the resolution is *incomplete from the perspective of this interaction*, and further steps are required *by another agent/department or at a later time by anyone*. The agent's actions were a step in the process but not the concluding one for the intent.
                        *   Examples:
                            *   **Handoff Required:** The agent addressed the intent to the best of their ability but then had to transfer the customer to another department, agent, or supervisor for completion.
                            *   **Information Provided, but Incomplete for Resolution:** The agent provided some relevant information, but it was not sufficient to fully resolve the intent, and more information *could have been provided by this agent or was clearly still needed* for the customer to consider the *specific inquiry* resolved (e.g., answered only one part of a multi-part question related to the primary intent; provided vague information when specifics were expected and likely available to the agent).
                            *   **Action Initiated, Not Completed:** The agent started a process (e.g., began an order, started a diagnostic) but couldn't complete it in this interaction due to a *non-agent/non-system failure* that necessitates follow-up (e.g., customer needs to find information and call back).

                *   **Output "no" if:**
                    *   The agent fundamentally failed to address or progress the customer's primary intent due to their own actions, inactions, or limitations, or due to system/process failures impacting their ability to act.
                        *   Examples:
                            *   Agent lacked necessary information, skills, or tools they were expected to have.
                            *   Agent clearly misunderstood or failed to grasp the customer's primary intent.
                            *   Agent provided demonstrably incorrect or misleading information directly related to the primary intent.
                            *   Technical difficulties (on the agent's/company's side) prevented them from addressing the intent.
                            *   Organizational roadblocks (e.g., policy confusion, inability to find correct procedure, improper escalation) stopped them from substantively addressing the intent.
                            *   The call was prematurely disconnected before the agent could substantively address the intent (and it wasn't customer-initiated abandonment early on).

            *   **`summary`**: Provide a brief, 1-2 sentence summary describing the agent's key actions or information provided in response to the customer's primary intent.

            *   **`action`**: Describe the single, final, and most definitive action the agent performed during this interaction to address the customer's primary intent. This action should represent the last step the agent took.

                **Crucial Guideline:** Focus strictly on what is observable *in the transcript*. **Do not infer or predict outcomes that happen after the call ends or after a transfer.** Your goal is to capture what *this agent* did, not what the final resolution for the customer might eventually be.

                *   **Example Scenario:** If an agent transfers the customer to Geek Squad so they can schedule a repair, the correct `action` is `transferred to another department`, NOT `scheduled in-home service/repair appointment`. The scheduling did not occur with the agent in this transcript; the transfer was their final, observable action.

                Use 2-5 words (in-store and in-home count as one word). Below are examples to use as a guide. This is not an exhaustive list.
                *   `transferred to another department`
                *   `escalated to supervisor`
                *   `scheduled in-store appointment`: Only use if the agent *completed* the scheduling on the call.
                *   `scheduled in-home appointment`: Only use if the agent *completed* the scheduling on the call.
                *   `scheduled autotech appointment`: Only use if the agent *completed* the scheduling on the call.
                *   `rescheduled in-store appointment`: Only use if the agent *completed* the scheduling on the call.
                *   `rescheduled in-home appointment`: Only use if the agent *completed* the scheduling on the call.
                *   `canceled in-store appointment`: Only use if the agent *completed* the cancellation on the call.
                *   `canceled in-home appointment`: Only use if the agent *completed* the cancellation on the call.
                *   `scheduled technician followup`: Only use if the agent *completed* the scheduling on the call.
                *   `fixed/resolved product issue`: Applies to product troubleshooting, product setup, product help, or product installation that was successfully resolved on the call.
                *   `canceled order`
                *   `canceled membership`
                *   `canceled protection plan`
                *   `submitted order`
                *   `processed refund`
                *   `answered customer's appointment related inquiry`: Applies to any appointment related inquiry (e.g. appointment status, delivery status, repair status, date/time confirmation, general inquiries, etc.) that does not fall under the other categories.
                *   `answered customer's product related inquiry`: Applies to any product related inquiry (e.g availability, price, features, etc.) that does not fall under the other categories.
                *   `answered customer's order related inquiry`: Applies to any purchase order related inquiry (e.g. order status, in-store pickup status, order return, etc.) that does not fall under the other categories.
                *   `attempted troubleshooting`: Applies when troubleshooting was unsuccessful and did not lead to another conclusive action by the agent (like a transfer or scheduling).

    8.  **products:**
        *   **Critical Note:** In this context, products are tangible items sold by Best Buy, they do not include services, appointments, or any other non-product items.
        *   Create an array of all products mentioned during the call. It is important that you indicate in the context summary who specifically (e.g. customer or agent) mentioned the product. If no products are mentioned, return an empty array.
        *   For each product mentioned, extract the following:
            *   **`name`**: The name of the product. Use the same formatting rules as described for `reasonForCall.product`.
            *   **`context`**: A 1-2 sentence summary describing the context in which the customer mentioned this specific product. For example, were they comparing it to another product, asking about its warranty, or mentioning it as a past purchase?


    **Response Format:**

    Respond **ONLY** with a valid, parseable JSON object matching the structure below. Do **not** include any explanations, comments, apologies, or text outside the JSON structure itself.

    ```json
    {{
        "callSummary": "string",
        "callSentiment": {{
            "incoming": "string",
            "outgoing": "string"
        }},
        "callSentimentSummary": "string",
        "callTone": "string",
        "languageCode": "string",
        "reasonForCall": {{
            "summary": "string",
            "intent": "string",
            "inquiryQuestion": "string or null",
            "product": "string or null",
            "productCategory": "string or null"
        }},
        "agentResponse": {{
            "resolved": "yes" or "partially" or "no",
            "summary": "string",
            "action": "string"
        }},
        "products": [
          {{
            "name": "string",
            "context": "string"
          }}
        ]
    }}
    ```

    **Call Transcript to Analyze:**
    "{transcript}"
    
    "Call Direction": "{direction}"


    """


@functions_framework.http
def pass1_batch_generator(request):
    """HTTP endpoint for generating batch requests for Vertex AI."""
    try:
        print("=== STARTING HTTP pass1 batch generator ===")

        # Get request data
        print("Getting request JSON...")
        request_json = request.get_json()
        print(f"Request JSON received: {request_json is not None}")

        if not request_json:
            print("ERROR: No JSON data in request")
            return (
                "Error: No JSON data in request",
                400,
                {"Content-Type": "application/json"},
            )

        print("Extracting data from request...")
        data = request_json.get("data", {})
        print(f"Data extracted: {data}")

        project_id = data.get("project_id")
        region = data.get("region")
        model = data.get("model")
        dataset = data.get("dataset")
        index_table = data.get("index_table")
        where_clause = data.get("where_clause")
        batch_bucket = data.get("batch_bucket")
        batch_input_blob = data.get(
            "batch_input_blob", "batch/analyze-batch-requests.jsonl"
        )

        # Add friendly timestamp to the blob name for better readability
        from datetime import datetime

        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        batch_id = data.get("batch_id", "unknown")

        # If the blob name doesn't end with .jsonl, add it
        if not batch_input_blob.endswith(".jsonl"):
            batch_input_blob = batch_input_blob + ".jsonl"

        # Create the final blob name with timestamp
        final_blob_name = (
            f"{batch_input_blob.replace('.jsonl', '')}-{timestamp}-{batch_id}.jsonl"
        )

        print(f"Parameters extracted:")
        print(f"  project_id: {project_id}")
        print(f"  region: {region}")
        print(f"  model: {model}")
        print(f"  dataset: {dataset}")
        print(f"  index_table: {index_table}")
        print(f"  where_clause: {where_clause}")
        print(f"  batch_bucket: {batch_bucket}")
        print(f"  original_batch_input_blob: {batch_input_blob}")
        print(f"  final_blob_name: {final_blob_name}")

        # Validate required parameters
        if not all(
            [
                project_id,
                region,
                model,
                dataset,
                index_table,
                where_clause,
                batch_bucket,
            ]
        ):
            missing = [
                param
                for param, value in {
                    "project_id": project_id,
                    "region": region,
                    "model": model,
                    "dataset": dataset,
                    "index_table": index_table,
                    "where_clause": where_clause,
                    "batch_bucket": batch_bucket,
                }.items()
                if not value
            ]
            print(f"ERROR: Missing required parameters: {missing}")
            return (
                json.dumps({"error": f"Missing required parameters: {missing}"}),
                400,
                {"Content-Type": "application/json"},
            )

        print("Initializing BigQuery client...")
        try:
            # client = bigquery.Client(project=project_id)
            client = get_bq_client(project_id)
            print("BigQuery client initialized successfully")
        except Exception as e:
            print(f"ERROR initializing BigQuery client: {str(e)}")
            return (
                json.dumps({"error": f"Error initializing BigQuery client: {str(e)}"}),
                500,
                {"Content-Type": "application/json"},
            )

        # Construct and execute the BigQuery query with deduplication
        query = f"""
        SELECT 
            t.phone_number_token, 
            t.referenceId, 
            t.interactionId, 
            t.transcript, 
            t.direction, 
            t.provider, 
            t.event_timestamp,
            t.batch_row_num
        FROM ( 
            SELECT *, ROW_NUMBER() OVER(ORDER BY phone_number_token, referenceId, interactionId) as batch_row_num 
            FROM `{project_id}.{dataset}.{index_table}` 
        ) t
         LEFT JOIN (
            SELECT phone_number_token, interaction_id 
            FROM `{project_id}.{dataset}.transcription_processed_records`
        ) p
            ON t.phone_number_token = p.phone_number_token 
            AND t.interactionId = p.interaction_id
        WHERE p.phone_number_token IS NULL  -- Only process records that haven't been processed
        AND {where_clause.replace('WHERE ', '').replace('row_num', 't.batch_row_num')}
        ORDER BY t.batch_row_num
        """

        print(f"Constructed BigQuery query: {query}")

        try:
            print("Executing BigQuery query...")
            query_job = client.query(query)
            print("Query job created, waiting for results...")
            results = query_job.result()
            print("Query completed successfully")
        except Exception as e:
            print(f"ERROR executing BigQuery query: {str(e)}")
            return (
                json.dumps({"error": f"Error executing BigQuery query: {str(e)}"}),
                500,
                {"Content-Type": "application/json"},
            )

        # Convert results to list for processing
        print("Converting results to list...")
        try:
            rows = list(results)
            print(f"Retrieved {len(rows)} records from BigQuery")
        except Exception as e:
            print(f"ERROR converting results to list: {str(e)}")
            return (
                json.dumps({"error": f"Error converting results to list: {str(e)}"}),
                500,
                {"Content-Type": "application/json"},
            )

        if len(rows) == 0:
            print("WARNING: No rows returned from BigQuery query")
            return (
                json.dumps(
                    {
                        "message": "No data found for the given criteria",
                        "rows_processed": 0,
                    }
                ),
                200,
                {"Content-Type": "application/json"},
            )

        # Generate JSONL content
        print("Starting JSONL generation...")
        jsonl_lines = []

        for i, row in enumerate(rows):
            try:
                print(f"Processing row {i+1}/{len(rows)}")

                # Extract row data directly from BigQuery result
                phone_token = row.phone_number_token
                interaction_id = row.interactionId
                transcript = row.transcript
                direction = row.direction

                print(
                    f"  Row data - phone_token: {phone_token}, interaction_id: {interaction_id}"
                )
                print(
                    f"  Direction: {direction}, transcript length: {len(transcript) if transcript else 0}"
                )

                # Base64 encode the phone_token as bytes, then decode to str
                phone_token_b64 = base64.b64encode(
                    str(phone_token).encode("utf-8")
                ).decode("utf-8")
                print(f"  Encoded phone_token: {phone_token_b64}")

                # Get the get prompt
                print("  Getting summary prompt...")
                prompt = get_summary_prompt(transcript, direction)
                print(f"  Prompt generated, length: {len(prompt)}")

                # Concatenate the base64 encoded phone token with interaction ID
                composite_key = phone_token_b64 + "|" + str(interaction_id)
                print(f"  Composite key: {composite_key}")

                # Create the entry
                entry = {
                    "key": composite_key,
                    "request": {
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generation_config": {
                            "temperature": 0.1,
                            "thinkingConfig": {"thinkingBudget": 0},
                        },
                    },
                }

                jsonl_lines.append(json.dumps(entry))
                print(f"  Entry created and added to list")

            except Exception as e:
                print(f"ERROR processing row {i+1}: {str(e)}")
                return (
                    json.dumps({"error": f"Error processing row {i+1}: {str(e)}"}),
                    500,
                    {"Content-Type": "application/json"},
                )

        print("Joining JSONL lines...")
        try:
            # Join all lines with newlines
            jsonl_content = "\n".join(jsonl_lines)
            print(
                f"Successfully generated JSONL content with {len(jsonl_lines)} entries"
            )
            print(f"Total content length: {len(jsonl_content)} characters")
        except Exception as e:
            print(f"ERROR joining JSONL lines: {str(e)}")
            return (
                json.dumps({"error": f"Error joining JSONL lines: {str(e)}"}),
                500,
                {"Content-Type": "application/json"},
            )

        # Upload directly to GCS
        print("Initializing GCS client...")
        try:
            # storage_client = storage.Client(project=project_id)
            storage_client = get_storage_client(project_id)
            bucket = storage_client.bucket(batch_bucket)
            blob = bucket.blob(final_blob_name)
            print(
                f"GCS client initialized, uploading to gs://{batch_bucket}/{final_blob_name}"
            )
            print(
                f"BATCH GENERATOR DEBUG - Uploading to: gs://{batch_bucket}/{final_blob_name}"
            )
            print(
                f"BATCH GENERATOR DEBUG - File size will be: {len(jsonl_content)} characters"
            )
        except Exception as e:
            print(f"ERROR initializing GCS client: {str(e)}")
            return (
                json.dumps({"error": f"Error initializing GCS client: {str(e)}"}),
                500,
                {"Content-Type": "application/json"},
            )

        try:
            print("Uploading JSONL content to GCS...")
            blob.upload_from_string(jsonl_content, content_type="text/plain")
            print("Upload completed successfully")
            print(
                f"BATCH GENERATOR DEBUG - Successfully uploaded to: gs://{batch_bucket}/{final_blob_name}"
            )

            # Verify the file exists
            try:
                blob.reload()
                print(
                    f"BATCH GENERATOR DEBUG - File verification: {blob.name} exists, size: {blob.size} bytes"
                )
            except Exception as verify_error:
                print(
                    f"BATCH GENERATOR DEBUG - File verification failed: {verify_error}"
                )
        except Exception as e:
            print(f"ERROR uploading to GCS: {str(e)}")
            return (
                json.dumps({"error": f"Error uploading to GCS: {str(e)}"}),
                500,
                {"Content-Type": "application/json"},
            )

        print("=== FUNCTION COMPLETED SUCCESSFULLY ===")

        # Return success response with metadata
        response = {
            "success": True,
            "message": "JSONL file generated and uploaded successfully",
            "rows_processed": len(rows),
            "gcs_path": f"gs://{batch_bucket}/{final_blob_name}",
            "blob_name": final_blob_name,
            "entries_generated": len(jsonl_lines),
        }

        return json.dumps(response), 200, {"Content-Type": "application/json"}

    except Exception as e:
        print(f"=== UNEXPECTED ERROR: {str(e)} ===")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return (
            json.dumps({"error": f"Unexpected error: {str(e)}"}),
            500,
            {"Content-Type": "application/json"},
        )


@functions_framework.http
def health_check(request):
    """Health check endpoint for Cloud Function."""
    return "OK", 200
