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
  name     = "rg-storage-compliant"
  location = "eastus"
}

resource "azurerm_storage_account" "example" {
  name                     = "compstoracct001"
  resource_group_name      = azurerm_resource_group.example.name
  location                 = azurerm_resource_group.example.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  allow_blob_public_access      = false
  enable_https_traffic_only     = true
  min_tls_version               = "TLS1_2"
  infrastructure_encryption_enabled = true
  public_network_access_enabled = false

  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }
}
