variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

# AI Services account
variable "ai_services_name" {
  description = "Name of the Azure AI Services account"
  type        = string
}

variable "sku_name" {
  description = "SKU for Azure AI Services"
  type        = string
  default     = "S0"
}

# GPT-4 deployment variables
variable "deploy_gpt4" {
  description = "Deploy GPT-4 model"
  type        = bool
  default     = true
}

variable "gpt4_deployment_name" {
  description = "Name of the GPT-4 deployment"
  type        = string
  default     = "gpt-4"
}

variable "gpt4_model_name" {
  description = "GPT-4 model name"
  type        = string
  default     = "gpt-4.1"
}

variable "gpt4_model_version" {
  description = "GPT-4 model version"
  type        = string
  default     = "nano-2025-04-14"
}

variable "gpt4_capacity" {
  description = "GPT-4 capacity (tokens per minute / 1000)"
  type        = number
  default     = 10
}

# Embedding deployment variables
variable "deploy_embedding" {
  description = "Deploy text-embedding model"
  type        = bool
  default     = true
}

variable "embedding_deployment_name" {
  description = "Name of the embedding deployment"
  type        = string
  default     = "text-embedding-ada-002"
}

variable "embedding_model_name" {
  description = "Embedding model name"
  type        = string
  default     = "text-embedding-ada-002"
}

variable "embedding_model_version" {
  description = "Embedding model version"
  type        = string
  default     = "2"
}

variable "embedding_capacity" {
  description = "Embedding capacity (tokens per minute / 1000)"
  type        = number
  default     = 10
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
