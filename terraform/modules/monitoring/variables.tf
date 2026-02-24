variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "tenant_id" {
  description = "Azure AD tenant ID"
  type        = string
}

variable "log_analytics_name" {
  description = "Name of the Log Analytics workspace"
  type        = string
}

variable "log_analytics_sku" {
  description = "SKU for Log Analytics"
  type        = string
  default     = "PerGB2018"
}

variable "retention_days" {
  description = "Log retention in days"
  type        = number
  default     = 30
}

variable "app_insights_name" {
  description = "Name of Application Insights"
  type        = string
}

variable "application_type" {
  description = "Application type for App Insights"
  type        = string
  default     = "web"
}

variable "key_vault_name" {
  description = "Name of the Key Vault"
  type        = string
}

variable "key_vault_sku" {
  description = "SKU for Key Vault"
  type        = string
  default     = "standard"
}

variable "purge_protection_enabled" {
  description = "Enable purge protection for Key Vault"
  type        = bool
  default     = false
}

variable "soft_delete_retention_days" {
  description = "Soft delete retention days for Key Vault"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
