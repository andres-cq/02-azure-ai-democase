# Azure AI Services Module
# Simplified - just AI Services account with model deployments
# No AI Foundry Hub overhead (storage, KV, App Insights)

# Azure AI Services - Multi-service account
resource "azurerm_cognitive_account" "ai_services" {
  name                = var.ai_services_name
  resource_group_name = var.resource_group_name
  location            = var.location
  kind                = "AIServices"  # Multi-service account
  sku_name            = var.sku_name
  project_management_enabled = true

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# GPT-4 Model Deployment
resource "azurerm_cognitive_deployment" "gpt4" {
  count                = var.deploy_gpt4 ? 1 : 0
  name                 = var.gpt4_deployment_name
  cognitive_account_id = azurerm_cognitive_account.ai_services.id
  rai_policy_name            = "Microsoft.DefaultV2"
  
  model {
    format  = "OpenAI"
    name    = var.gpt4_model_name
    version = var.gpt4_model_version
  }

  sku {
    name     = "Standard"
    capacity = var.gpt4_capacity
  }
}

# Text Embedding Deployment
resource "azurerm_cognitive_deployment" "embedding" {
  count                = var.deploy_embedding ? 1 : 0
  name                 = var.embedding_deployment_name
  cognitive_account_id = azurerm_cognitive_account.ai_services.id

  model {
    format  = "OpenAI"
    name    = var.embedding_model_name
    version = var.embedding_model_version
  }

  sku {
    name     = "Standard"
    capacity = var.embedding_capacity
  }
}
