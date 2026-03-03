#!/bin/bash
set -e

echo "=================================================="
echo "Azure AI Fraud Detection - Infrastructure Deployment"
echo "=================================================="
echo ""

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform not found. Please install: https://www.terraform.io/downloads"
    exit 1
fi

echo "✅ Azure CLI found: $(az version --query '\"azure-cli\"' -o tsv)"
echo "✅ Terraform found: $(terraform version -json | grep -o '"terraform_version":"[^"]*' | cut -d'"' -f4)"
echo ""

# Check Azure login
echo "🔐 Checking Azure authentication..."
if ! az account show &> /dev/null; then
    echo "❌ Not logged in to Azure. Running 'az login'..."
    az login
fi

SUBSCRIPTION=$(az account show --query name -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "✅ Logged in to Azure"
echo "   Subscription: $SUBSCRIPTION"
echo "   ID: $SUBSCRIPTION_ID"
echo ""

# Create terraform.tfvars if it doesn't exist
if [ ! -f "terraform.tfvars" ]; then
    echo "📝 Creating terraform.tfvars from example..."
    cp terraform.tfvars.example terraform.tfvars
    echo "✅ Created terraform.tfvars - please review and customize if needed"
    echo ""
fi

# Initialize Terraform
echo "🔧 Initializing Terraform..."
terraform init
echo ""

# Validate configuration
echo "✅ Validating Terraform configuration..."
terraform validate
echo ""

# Plan deployment
echo "📋 Planning deployment..."
terraform plan -out=tfplan
echo ""

# Confirm deployment
read -p "🚀 Ready to deploy? This will create Azure resources. Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Deployment cancelled"
    rm -f tfplan
    exit 0
fi

# Apply deployment
echo ""
echo "🚀 Deploying infrastructure..."
terraform apply tfplan
rm -f tfplan
echo ""

echo "=================================================="
echo "✅ Deployment Complete!"
echo "=================================================="
echo ""

# Display summary
echo "📊 Deployment Summary:"
terraform output deployment_summary
echo ""

echo "🔑 Service Endpoints:"
echo "   Storage Account:      $(terraform output -raw storage_account_name)"
echo "   Document Intelligence: $(terraform output -raw doc_intelligence_endpoint)"
echo "   AI Search:            $(terraform output -raw search_endpoint)"
echo "   OpenAI:               $(terraform output -raw openai_endpoint)"
echo ""

echo "📁 Upload sample claims:"
echo "   cd .."
echo "   STORAGE_ACCOUNT=\$(cd terraform && terraform output -raw storage_account_name)"
echo "   az storage blob upload --account-name \$STORAGE_ACCOUNT --container-name insurance-claims \\"
echo "     --name legitimate-claim.pdf --file sample-data/claims/legitimate-claim.pdf --auth-mode login"
echo ""

echo "💡 Next steps:"
echo "   1. Upload sample PDFs to blob storage"
echo "   2. Configure Document Intelligence"
echo "   3. Set up AI Search index"
echo "   4. Test fraud detection in AI Foundry"
echo ""

echo "🧹 To cleanup and remove all resources:"
echo "   terraform destroy"
echo ""
