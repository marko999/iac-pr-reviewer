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
  name     = "rg-web-noncompliant"
  location = "centralus"
}

resource "azurerm_app_service_plan" "example" {
  name                = "asp-web-noncompliant"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  sku {
    tier = "Standard"
    size = "S1"
  }
}

resource "azurerm_app_service" "example" {
  name                = "noncomp-web-app-001"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  app_service_plan_id = azurerm_app_service_plan.example.id

  https_only              = false
  client_affinity_enabled = true

  site_config {
    min_tls_version = "1.0"
    ftps_state      = "AllAllowed"
    http2_enabled   = false
  }

  auth_settings_v2 {
    auth_enabled           = false
    require_authentication = false
    token_store_enabled    = false
  }
}
