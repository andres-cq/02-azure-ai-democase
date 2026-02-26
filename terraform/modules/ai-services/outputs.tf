# AI Services outputs
output "ai_services_id" {
  description = "ID of the Azure AI Services account"
  value       = azurerm_cognitive_account.ai_services.id
}

output "ai_services_name" {
  description = "Name of the Azure AI Services account"
  value       = azurerm_cognitive_account.ai_services.name
}

output "endpoint" {
  description = "Endpoint URL for Azure AI Services"
  value       = azurerm_cognitive_account.ai_services.endpoint
}

output "primary_access_key" {
  description = "Primary access key for Azure AI Services"
  value       = azurerm_cognitive_account.ai_services.primary_access_key
  sensitive   = true
}

# Model deployment outputs
output "gpt4_deployment_name" {
  description = "Name of the GPT-4 deployment"
  value       = var.deploy_gpt4 ? azurerm_cognitive_deployment.gpt4[0].name : null
}

output "embedding_deployment_name" {
  description = "Name of the embedding deployment"
  value       = var.deploy_embedding ? azurerm_cognitive_deployment.embedding[0].name : null
}
