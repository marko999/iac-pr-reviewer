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
  name     = "rg-kv-noncompliant"
  location = "westus"
}

resource "azurerm_key_vault" "example" {
  name                        = "noncomp-kv-001"
  location                    = azurerm_resource_group.example.location
  resource_group_name         = azurerm_resource_group.example.name
  tenant_id                   = "00000000-0000-0000-0000-000000000000"
  sku_name                    = "standard"
  purge_protection_enabled    = false
  soft_delete_retention_days  = 7
  enable_rbac_authorization   = false
  public_network_access_enabled = true

  network_acls {
    bypass         = ["AzureServices", "AzureKeyVault"]
    default_action = "Allow"
    ip_rules       = []
  }
}
