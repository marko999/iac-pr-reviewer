terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.70.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "example" {
  name     = "rg-storage-noncompliant"
  location = "eastus2"
}

resource "azurerm_storage_account" "example" {
  name                     = "noncomplstor001"
  resource_group_name      = azurerm_resource_group.example.name
  location                 = azurerm_resource_group.example.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  allow_blob_public_access      = true
  enable_https_traffic_only     = false
  min_tls_version               = "TLS1_0"
  infrastructure_encryption_enabled = false
  public_network_access_enabled = true
}
