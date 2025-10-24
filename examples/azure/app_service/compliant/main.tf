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
  name     = "rg-web-compliant"
  location = "eastus"
}

resource "azurerm_app_service_plan" "example" {
  name                = "asp-web-compliant"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  sku {
    tier = "Standard"
    size = "S1"
  }
}

resource "azurerm_app_service" "example" {
  name                = "comp-web-app-001"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  app_service_plan_id = azurerm_app_service_plan.example.id

  https_only          = true
  client_affinity_enabled = false

  site_config {
    min_tls_version = "1.2"
    ftps_state      = "Disabled"
    http2_enabled   = true
  }

  auth_settings_v2 {
    auth_enabled           = true
    require_authentication = true
    token_store_enabled    = true
  }
}
