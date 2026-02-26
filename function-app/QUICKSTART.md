# Quick Start Guide

## Prerequisites

1. **Azure CLI** installed and configured
   ```bash
   az --version
   az login
   ```

2. **Azure Functions Core Tools v4** installed
   ```bash
   func --version  # Should show 4.x
   ```

3. **Python 3.11** installed
   ```bash
   python3 --version  # Should be 3.11.x
   ```

4. **Terraform** installed
   ```bash
   terraform --version
   ```

## Step-by-Step Deployment

### Step 1: Deploy Infrastructure (REQUIRED FIRST!)

❗ **You MUST deploy infrastructure before publishing the function code.**

```bash
# Navigate to terraform directory
cd ../terraform

# Initialize Terraform (if not already done)
terraform init -backend-config=backend.tfvars

# Plan deployment
terraform plan

# Deploy infrastructure
terraform apply
```

This creates:
- Storage Account with `claims` and `processed` containers
- Document Intelligence service
- Function App (empty, ready for code deployment)
- Application Insights
- All necessary RBAC permissions

**Wait for terraform to complete successfully before proceeding!**

### Step 2: Deploy Function Code

```bash
# Navigate to function-app directory
cd ../function-app

# Use the deployment script (recommended)
./deploy.sh

# OR manually:
func azure functionapp publish func-frauddetect --python
```

### Step 3: Test the Function

```bash
# Upload a test PDF
az storage blob upload \
  --account-name stfrauddetect \
  --container-name claims \
  --name test-claim.pdf \
  --file ../sample-data/claims/legitimate-claim.pdf \
  --auth-mode login

# Wait ~10-30 seconds for processing

# Download the result
az storage blob download \
  --account-name stfrauddetect \
  --container-name processed \
  --name test-claim_analyzed.json \
  --file output.json \
  --auth-mode login

# View results
cat output.json | jq .
```

### Step 4: Monitor Function

```bash
# Stream live logs
func azure functionapp logstream func-frauddetect

# Or view in Azure Portal:
# Navigate to Function App → Functions → process_insurance_claim → Monitor
```

## Common Mistakes

### ❌ Publishing Before Terraform Apply

**Error**: `Sequence contains no elements`

**Reason**: Function App doesn't exist in Azure yet.

**Solution**: Run `terraform apply` FIRST, then publish function code.

### ❌ Wrong Directory

**Error**: Various errors about missing files

**Reason**: Not in the `function-app` directory.

**Solution**:
```bash
cd /Users/dominik/dev/github/02-azure-ai-democase/function-app
./deploy.sh
```

### ❌ Wrong Function App Name

**Error**: Function app not found

**Reason**: Using wrong project name.

**Solution**: Check actual function app name:
```bash
terraform output  # Run from terraform directory
# Or
az functionapp list --resource-group rg-frauddetect --query "[].name" -o table
```

## Verification Checklist

Before publishing function code, verify:

```bash
# ✅ Check infrastructure exists
az functionapp show --name func-frauddetect --resource-group rg-frauddetect

# ✅ Check storage account exists
az storage account show --name stfrauddetect --resource-group rg-frauddetect

# ✅ Check Document Intelligence exists
az cognitiveservices account show --name doc-intel-frauddetect --resource-group rg-frauddetect

# ✅ Check you're in the right directory
pwd  # Should end with: /function-app

# ✅ Check function file exists
ls -la function_app.py
```

All checks should succeed before running `./deploy.sh`.

## Architecture Flow

```
1. terraform apply
   ↓
   Creates: Function App (empty) + Storage + Doc Intelligence

2. ./deploy.sh
   ↓
   Uploads: Python code to Function App

3. Upload PDF to 'claims' container
   ↓
   Triggers: Function automatically
   ↓
   Calls: Document Intelligence API
   ↓
   Saves: Results to 'processed' container
```

## Need Help?

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed error resolution.
