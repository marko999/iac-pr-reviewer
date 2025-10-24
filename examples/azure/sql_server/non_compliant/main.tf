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
  name     = "rg-sql-noncompliant"
  location = "westus2"
}

resource "azurerm_mssql_server" "example" {
  name                         = "noncomp-sql-server"
  resource_group_name          = azurerm_resource_group.example.name
  location                     = azurerm_resource_group.example.location
  administrator_login          = "sqladminuser"
  administrator_login_password = "WeakPass1"
  minimum_tls_version          = "1.0"
  public_network_access_enabled = true

  identity {
    type = "None"
  }
}
