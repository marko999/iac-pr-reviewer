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
  name     = "rg-sql-compliant"
  location = "southcentralus"
}

resource "azurerm_mssql_server" "example" {
  name                         = "compliant-sql-server"
  resource_group_name          = azurerm_resource_group.example.name
  location                     = azurerm_resource_group.example.location
  administrator_login          = "sqladminuser"
  administrator_login_password = "P@ssword1234!"
  minimum_tls_version          = "1.2"
  public_network_access_enabled = false

  identity {
    type = "SystemAssigned"
  }
}
