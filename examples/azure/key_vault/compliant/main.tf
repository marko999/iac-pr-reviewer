terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.70.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "example" {
  name     = "rg-kv-compliant"
  location = "eastus2"
}

resource "azurerm_key_vault" "example" {
  name                        = "comp-kv-001"
  location                    = azurerm_resource_group.example.location
  resource_group_name         = azurerm_resource_group.example.name
  tenant_id                   = "00000000-0000-0000-0000-000000000000"
  sku_name                    = "standard"
  purge_protection_enabled    = true
  soft_delete_retention_days  = 90
  enable_rbac_authorization   = true
  public_network_access_enabled = false

  network_acls {
    bypass         = ["AzureServices"]
    default_action = "Deny"
    ip_rules       = ["10.10.0.0/24"]
  }
}
