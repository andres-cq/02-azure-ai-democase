resource "azurerm_cognitive_account" "ai_services" {
  name                  = var.name
  resource_group_name   = var.resource_group_name
  location              = var.location
  kind                  = "AIServices"
  sku_name              = var.sku_name
  custom_subdomain_name = var.name

  tags = var.tags
}
