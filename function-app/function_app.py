"""
Azure Function App — Insurance Claims Pipeline + T&C RAG Chatbot

Flow 1 (blob-triggered, chained):
  insurance-claims/       → process_insurance_claim  (Document Intelligence extraction)
  processed-data/         → analyze_with_gpt5        (GPT verdict)
  model-analysis-results/ ← final verdict JSON

Flow 2 (HTTP):
  POST /api/messages → messages (Bot Framework T&C chatbot)
"""

import json
import logging
import os
import threading
import traceback

import azure.functions as func
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI

app = func.FunctionApp()


# ── Shared: Azure OpenAI (used by both flows) ─────────────────────────────────
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")


def get_service_credential():
    """Managed identity for OpenAI and Search; DefaultAzureCredential handles local dev automatically."""
    return DefaultAzureCredential()


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 1 — Insurance Claims Pipeline
# PDF → Document Intelligence → processed-data → GPT verdict → model-analysis-results
# ══════════════════════════════════════════════════════════════════════════════

DOC_INTEL_ENDPOINT = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
DATA_STORAGE_ACCOUNT_URL = os.getenv("DATA_STORAGE_ACCOUNT_URL", "")
OUTPUT_CONTAINER = os.getenv("OUTPUT_CONTAINER_NAME", "processed-data")
MODEL_ANALYSIS_CONTAINER = os.getenv("MODEL_ANALYSIS_CONTAINER_NAME", "model-analysis-results")

with open(os.path.join(os.path.dirname(__file__), "fraud_rules.json")) as _f:
    _FRAUD_RULES = json.load(_f)


@app.blob_trigger(
    arg_name="blob",
    path="insurance-claims/{name}",
    connection="DataStorageConnection"
)
def process_insurance_claim(blob: func.InputStream):
    """Step 1: Extract structured data from a claim PDF using Document Intelligence.
    Output written to processed-data/, which triggers analyze_with_gpt5."""
    logging.info(f"Processing blob: {blob.name}, Size: {blob.length} bytes")

    try:
        doc_client = DocumentAnalysisClient(
            endpoint=DOC_INTEL_ENDPOINT,
            credential=get_service_credential()
        )

        pdf_bytes = blob.read()

        # prebuilt-document extracts text, key-value pairs, and tables
        # Switch to "prebuilt-invoice" if claims are always invoice-format PDFs
        poller = doc_client.begin_analyze_document(
            model_id="prebuilt-document",
            document=pdf_bytes
        )
        result = poller.result()

        extracted_data = {
            "source_file": blob.name,
            "pages": len(result.pages),
            "content": result.content,
            "key_value_pairs": {},
            "tables": [],
            "fraud_indicators": []
        }

        # Key-value pairs (e.g. claimant name, dates, amounts)
        if result.key_value_pairs:
            for kv_pair in result.key_value_pairs:
                if kv_pair.key and kv_pair.value:
                    key_text = kv_pair.key.content if kv_pair.key.content else ""
                    value_text = kv_pair.value.content if kv_pair.value.content else ""
                    extracted_data["key_value_pairs"][key_text] = value_text

        # Raw table cells (preserved for audit; GPT analysis uses key_value_pairs instead)
        if result.tables:
            for table_idx, table in enumerate(result.tables):
                table_data = {
                    "table_id": table_idx,
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "cells": []
                }
                for cell in table.cells:
                    table_data["cells"].append({
                        "row_index": cell.row_index,
                        "column_index": cell.column_index,
                        "content": cell.content
                    })
                extracted_data["tables"].append(table_data)

        # Heuristic fraud checks loaded from fraud_rules.json — GPT incorporates these in step 2
        content_lower = result.content.lower()
        kv = extracted_data["key_value_pairs"]

        for check in _FRAUD_RULES.get("keyword_checks", []):
            if any(kw in content_lower for kw in check["keywords"]):
                extracted_data["fraud_indicators"].append(check["indicator"])

        for check in _FRAUD_RULES.get("date_comparison_checks", []):
            ef, lf = check["earlier_field"], check["later_field"]
            if ef in kv and lf in kv and kv[ef] < kv[lf]:
                extracted_data["fraud_indicators"].append(check["indicator"])

        # Write to processed-data/ — this triggers analyze_with_gpt5
        blob_service_client = BlobServiceClient(account_url=DATA_STORAGE_ACCOUNT_URL, credential=get_service_credential())
        output_blob_name = f"{os.path.splitext(blob.name)[0]}_analyzed.json"
        output_blob_client = blob_service_client.get_blob_client(
            container=OUTPUT_CONTAINER,
            blob=output_blob_name
        )
        output_blob_client.upload_blob(
            json.dumps(extracted_data, indent=2),
            overwrite=True
        )

        logging.info(f"Extraction complete: {output_blob_name} ({len(extracted_data['fraud_indicators'])} heuristic indicators)")

    except Exception as e:
        logging.error(f"Error processing blob {blob.name}: {str(e)}")
        raise


@app.blob_trigger(
    arg_name="blob",
    path="processed-data/{name}",
    connection="DataStorageConnection"
)
def analyze_with_gpt5(blob: func.InputStream):
    """Step 2: Produce a GPT verdict from the Document Intelligence extraction.
    Output written to model-analysis-results/ as a clean JSON verdict."""
    logging.info(f"Analyzing blob: {blob.name}")

    try:
        if not blob.name.endswith('.json'):
            logging.info(f"Skipping non-JSON file: {blob.name}")
            return

        document_data = json.loads(blob.read().decode('utf-8'))

        credential = get_service_credential()
        client = AzureOpenAI(
            azure_ad_token_provider=lambda: credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            ).token,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )

        # Send only the fields the model needs — raw table cells are excluded
        prompt_data = {
            "key_value_pairs": document_data.get("key_value_pairs", {}),
            "content": document_data.get("content", ""),
            "existing_fraud_indicators": document_data.get("fraud_indicators", [])
        }

        prompt = f"""Analyze the following insurance claim data and return a JSON object with exactly these fields:

{{
  "summary": "<2-3 sentence summary of the claim>",
  "risk_level": "<Low | Medium | High>",
  "fraud_indicators": ["<indicator 1>", "..."],
  "recommended_next_steps": ["<step 1>", "..."]
}}

Note: existing_fraud_indicators have already been flagged by automated checks — incorporate them into your analysis.

Claim data:
{json.dumps(prompt_data, indent=2)}"""

        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert insurance claims analyst with deep knowledge of fraud detection and risk assessment."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=6000
        )

        gpt_analysis = response.choices[0].message.content

        logging.info(f"Response finish_reason: {response.choices[0].finish_reason}")
        if not gpt_analysis:
            raise ValueError(f"Empty response from GPT. Full response: {response.model_dump_json()}")

        verdict = json.loads(gpt_analysis)

        analysis_result = {
            "source_document": blob.name,
            "analysis_timestamp": response.created,
            "model_used": AZURE_OPENAI_DEPLOYMENT,
            "verdict": verdict
        }

        blob_service_client = BlobServiceClient(account_url=DATA_STORAGE_ACCOUNT_URL, credential=get_service_credential())
        output_blob_name = f"{os.path.splitext(blob.name)[0]}_gpt5_analysis.json"
        output_blob_client = blob_service_client.get_blob_client(
            container=MODEL_ANALYSIS_CONTAINER,
            blob=output_blob_name
        )
        output_blob_client.upload_blob(
            json.dumps(analysis_result, indent=2),
            overwrite=True
        )

        logging.info(f"Verdict saved: {output_blob_name} (tokens used: {response.usage.total_tokens})")

    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in blob {blob.name}: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error analyzing blob {blob.name} with GPT: {str(e)}")
        raise


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 2 — T&C RAG Chatbot
# POST /api/messages → search T&C index → GPT response → Bot Framework reply
# ══════════════════════════════════════════════════════════════════════════════

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "terms-and-conditions-index")
BOT_APP_ID = os.getenv("MicrosoftAppId", "")

SYSTEM_PROMPT = """You are an insurance terms and conditions assistant. Your role is to help insurance agents find and understand information from insurance policy terms and conditions documents.

Rules:
- ONLY answer questions using the provided context from T&C documents.
- If the context does not contain enough information to answer, say so clearly.
- Cite specific sections or clauses when possible (e.g., "According to Section 3.2...").
- Never invent, assume, or fabricate information not present in the context.
- Decline questions that are not related to insurance terms and conditions politely.
- Be concise and professional in your responses.
"""


def get_bot_credential():
    """User-assigned managed identity for Bot Framework auth; falls back to DefaultAzureCredential locally."""
    if BOT_APP_ID:
        return ManagedIdentityCredential(client_id=BOT_APP_ID)
    return DefaultAzureCredential()


def search_terms_and_conditions(query: str) -> str:
    """Hybrid search (text + vector) with semantic ranking. Returns top 5 T&C chunks as context."""
    credential = get_service_credential()
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=credential,
    )

    vector_query = VectorizableTextQuery(
        text=query,
        k_nearest_neighbors=5,
        fields="text_vector",
    )

    results = search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        query_type="semantic",
        semantic_configuration_name="tc-semantic-config",
        top=5,
        select=["chunk", "title"],
    )

    context_parts = []
    for i, result in enumerate(results, 1):
        title = result.get("title", "Unknown")
        chunk = result.get("chunk", "")
        context_parts.append(f"[Source {i}: {title}]\n{chunk}")

    return "\n\n---\n\n".join(context_parts) if context_parts else ""


def get_rag_response(user_message: str) -> str:
    """Search T&C index → build prompt → call GPT → return answer."""
    context = search_terms_and_conditions(user_message)

    if not context:
        return (
            "I couldn't find any relevant information in the terms and conditions documents. "
            "Please make sure the T&C documents have been indexed, or try rephrasing your question."
        )

    credential = get_service_credential()
    openai_client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=lambda: credential.get_token(
            "https://cognitiveservices.azure.com/.default"
        ).token,
        api_version=AZURE_OPENAI_API_VERSION,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context from T&C documents:\n\n{context}\n\n---\n\nQuestion: {user_message}",
        },
    ]

    response = openai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=messages,
        max_completion_tokens=1024,
    )

    return response.choices[0].message.content


def _send_bot_reply(service_url, conversation_id, reply):
    """Send a reply activity to the Bot Framework connector."""
    import requests

    reply_url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/activities"
    try:
        credential = get_bot_credential()
        token = credential.get_token("https://api.botframework.com/.default").token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(reply_url, json=reply, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to send reply via Bot service: {e}")


def _process_and_reply(body, user_text):
    """Run the RAG pipeline and send the reply; executes in a background thread."""
    try:
        answer = get_rag_response(user_text)
    except Exception:
        logging.error(f"RAG pipeline error: {traceback.format_exc()}")
        answer = "I'm sorry, I encountered an error processing your question. Please try again."

    reply = {
        "type": "message",
        "from": body.get("recipient", {}),
        "recipient": body.get("from", {}),
        "conversation": body.get("conversation", {}),
        "text": answer,
        "replyToId": body.get("id"),
    }

    service_url = body.get("serviceUrl", "")
    conversation_id = body.get("conversation", {}).get("id", "")
    if service_url and conversation_id:
        _send_bot_reply(service_url, conversation_id, reply)


@app.route(route="messages", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
async def messages(req: func.HttpRequest) -> func.HttpResponse:
    """Bot Framework /api/messages endpoint.
    Returns 200 immediately; RAG processing runs in a background thread to stay within the 15s webhook timeout."""
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON", status_code=400)

    activity_type = body.get("type", "")

    if activity_type == "message":
        user_text = body.get("text", "").strip()
        if not user_text:
            return func.HttpResponse(status_code=200)

        logging.info(f"Received message: {user_text[:100]}")

        thread = threading.Thread(target=_process_and_reply, args=(body, user_text))
        thread.start()

        return func.HttpResponse(status_code=200)

    elif activity_type == "conversationUpdate":
        # Send welcome message to any new member (excluding the bot itself)
        members_added = body.get("membersAdded", [])
        bot_id = body.get("recipient", {}).get("id", "")
        service_url = body.get("serviceUrl", "")
        conversation_id = body.get("conversation", {}).get("id", "")
        for member in members_added:
            if member.get("id") != bot_id:
                welcome = {
                    "type": "message",
                    "from": body.get("recipient", {}),
                    "recipient": member,
                    "conversation": body.get("conversation", {}),
                    "text": (
                        "Hello! I'm the Terms & Conditions Assistant. "
                        "Ask me any question about your insurance policy terms and conditions."
                    ),
                }
                if service_url and conversation_id:
                    _send_bot_reply(service_url, conversation_id, welcome)

        return func.HttpResponse(status_code=200)

    return func.HttpResponse(status_code=200)
