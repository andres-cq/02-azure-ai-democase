# Monitoring Module
# Provides Log Analytics, Application Insights, and Key Vault

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "law" {
  name                = var.log_analytics_name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.log_analytics_sku
  retention_in_days   = var.retention_days

  tags = var.tags
}

# Application Insights
resource "azurerm_application_insights" "appinsights" {
  name                = var.app_insights_name
  resource_group_name = var.resource_group_name
  location            = var.location
  application_type    = var.application_type
  workspace_id        = azurerm_log_analytics_workspace.law.id

  tags = var.tags
}


