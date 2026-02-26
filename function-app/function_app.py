"""
Azure Function App - Document Intelligence Processor
Automatically processes PDF documents when uploaded to blob storage
"""

import azure.functions as func
import logging
import os
import json
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI

app = func.FunctionApp()

# Environment variables - Document Intelligence
DOC_INTEL_ENDPOINT = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
DOC_INTEL_KEY = os.getenv("DOCUMENT_INTELLIGENCE_KEY")
DATA_STORAGE_CONN = os.getenv("DataStorageConnection")
OUTPUT_CONTAINER = os.getenv("OUTPUT_CONTAINER_NAME", "processed-data")

# Environment variables - Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
MODEL_ANALYSIS_CONTAINER = os.getenv("MODEL_ANALYSIS_CONTAINER_NAME", "model-analysis-results")


@app.blob_trigger(
    arg_name="blob",
    path="insurance-claims/{name}",
    connection="DataStorageConnection"
)
def process_insurance_claim(blob: func.InputStream):
    """
    Triggered when a PDF is uploaded to the 'insurance-claims' container.
    Analyzes the document using Document Intelligence and stores results.
    """
    logging.info(f"Processing blob: {blob.name}, Size: {blob.length} bytes")

    try:
        # Initialize Document Intelligence client
        doc_client = DocumentAnalysisClient(
            endpoint=DOC_INTEL_ENDPOINT,
            credential=AzureKeyCredential(DOC_INTEL_KEY)
        )

        # Read blob content
        pdf_bytes = blob.read()
        logging.info(f"Read {len(pdf_bytes)} bytes from blob {blob.name}")

        # Analyze document using prebuilt-document model
        # For invoices, you can use "prebuilt-invoice" model
        poller = doc_client.begin_analyze_document(
            model_id="prebuilt-document",  # or "prebuilt-invoice" for invoices
            document=pdf_bytes
        )
        result = poller.result()

        # Extract structured data
        extracted_data = {
            "source_file": blob.name,
            "pages": len(result.pages),
            "content": result.content,
            "key_value_pairs": {},
            "tables": [],
            "fraud_indicators": []
        }

        # Extract key-value pairs
        if result.key_value_pairs:
            for kv_pair in result.key_value_pairs:
                if kv_pair.key and kv_pair.value:
                    key_text = kv_pair.key.content if kv_pair.key.content else ""
                    value_text = kv_pair.value.content if kv_pair.value.content else ""
                    extracted_data["key_value_pairs"][key_text] = value_text

        # Extract tables
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

        # Simple fraud detection logic (example)
        content_lower = result.content.lower()
        if "urgent" in content_lower or "immediate payment" in content_lower:
            extracted_data["fraud_indicators"].append("Urgent language detected")

        # Check for date inconsistencies (basic example)
        if "invoice date" in extracted_data["key_value_pairs"] and "incident date" in extracted_data["key_value_pairs"]:
            invoice_date = extracted_data["key_value_pairs"]["invoice date"]
            incident_date = extracted_data["key_value_pairs"]["incident date"]
            if invoice_date < incident_date:
                extracted_data["fraud_indicators"].append("Invoice date before incident date")

        # Store results in output container
        blob_service_client = BlobServiceClient.from_connection_string(DATA_STORAGE_CONN)
        output_blob_name = f"{os.path.splitext(blob.name)[0]}_analyzed.json"
        output_blob_client = blob_service_client.get_blob_client(
            container=OUTPUT_CONTAINER,
            blob=output_blob_name
        )

        # Upload analyzed data as JSON
        output_blob_client.upload_blob(
            json.dumps(extracted_data, indent=2),
            overwrite=True
        )

        logging.info(f"Successfully processed {blob.name}, results saved to {output_blob_name}")
        logging.info(f"Fraud indicators found: {len(extracted_data['fraud_indicators'])}")

    except Exception as e:
        logging.error(f"Error processing blob {blob.name}: {str(e)}")
        raise


@app.blob_trigger(
    arg_name="blob",
    path="processed-data/{name}",
    connection="DataStorageConnection"
)
def analyze_with_gpt4(blob: func.InputStream):
    """
    Triggered when a JSON document is uploaded to the 'processed-data' container.
    Sends the JSON to GPT-4o-mini for analysis and stores the response.
    """
    logging.info(f"GPT-4 Analysis - Processing blob: {blob.name}, Size: {blob.length} bytes")

    try:
        # Only process JSON files
        if not blob.name.endswith('.json'):
            logging.info(f"Skipping non-JSON file: {blob.name}")
            return

        # Read blob content
        json_content = blob.read().decode('utf-8')
        document_data = json.loads(json_content)

        logging.info(f"Read JSON document: {blob.name}")

        # Initialize Azure OpenAI client
        client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )

        # Construct prompt for GPT-4
        prompt = f"""You are an insurance claims analyst. Analyze the following document data and provide:
1. A summary of the claim
2. Any potential fraud indicators
3. Recommended next steps for claim processing
4. Risk assessment (Low/Medium/High)

Document Data:
{json.dumps(document_data, indent=2)}

Provide your analysis in a structured format."""

        # Call GPT-4o-mini
        logging.info(f"Calling Azure OpenAI deployment: {AZURE_OPENAI_DEPLOYMENT}")
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
            temperature=1,  # Lower temperature for more consistent analysis
            max_completion_tokens=1500
        )

        # Extract analysis from response
        gpt_analysis = response.choices[0].message.content

        # Build result object
        analysis_result = {
            "source_document": blob.name,
            "analysis_timestamp": response.created,
            "model_used": AZURE_OPENAI_DEPLOYMENT,
            "original_data": document_data,
            "gpt4_analysis": gpt_analysis,
            "token_usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }

        # Store results in model-analysis-results container
        blob_service_client = BlobServiceClient.from_connection_string(DATA_STORAGE_CONN)
        output_blob_name = f"{os.path.splitext(blob.name)[0]}_gpt4_analysis.json"
        output_blob_client = blob_service_client.get_blob_client(
            container=MODEL_ANALYSIS_CONTAINER,
            blob=output_blob_name
        )

        # Upload analysis result as JSON
        output_blob_client.upload_blob(
            json.dumps(analysis_result, indent=2),
            overwrite=True
        )

        logging.info(f"Successfully analyzed {blob.name} with GPT-4")
        logging.info(f"Results saved to {output_blob_name}")
        logging.info(f"Tokens used: {response.usage.total_tokens}")

    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in blob {blob.name}: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error analyzing blob {blob.name} with GPT-4: {str(e)}")
        raise
