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

resource "azurerm_resource_group" "core" {
  name     = "rg-multi-compliant"
  location = "eastus2"
}

resource "azurerm_storage_account" "shared" {
  name                     = "compliantstoracct01"
  resource_group_name      = azurerm_resource_group.core.name
  location                 = azurerm_resource_group.core.location
  account_tier             = "Standard"
  account_replication_type = "GRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    delete_retention_policy {
      days = 30
    }
  }
}

resource "azurerm_key_vault" "shared" {
  name                        = "comp-multi-kv01"
  location                    = azurerm_resource_group.core.location
  resource_group_name         = azurerm_resource_group.core.name
  tenant_id                   = "00000000-0000-0000-0000-000000000000"
  sku_name                    = "standard"
  enable_rbac_authorization   = true
  purge_protection_enabled    = true
  soft_delete_retention_days  = 90
  public_network_access_enabled = false

  network_acls {
    bypass         = ["AzureServices"]
    default_action = "Deny"
    ip_rules       = ["10.10.0.0/24"]
  }
}

resource "azurerm_app_service_plan" "shared" {
  name                = "asp-multi-compliant"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name

  sku {
    tier = "PremiumV2"
    size = "P1v2"
  }
}

resource "azurerm_app_service" "shared" {
  name                = "comp-multi-web-01"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name
  app_service_plan_id = azurerm_app_service_plan.shared.id

  https_only              = true
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

resource "azurerm_mssql_server" "shared" {
  name                         = "comp-multi-sqlsrv"
  resource_group_name          = azurerm_resource_group.core.name
  location                     = azurerm_resource_group.core.location
  version                      = "12.0"
  administrator_login          = "sqladminuser"
  administrator_login_password = "Sup3rStrongPass!"
  minimum_tls_version          = "1.2"
  public_network_access_enabled = false

  identity {
    type = "SystemAssigned"
  }
}
