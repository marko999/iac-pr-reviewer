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
  name     = "rg-multi-noncompliant"
  location = "centralus"
}

resource "azurerm_storage_account" "shared" {
  name                     = "noncompliantstor01"
  resource_group_name      = azurerm_resource_group.core.name
  location                 = azurerm_resource_group.core.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_0"
}

resource "azurerm_key_vault" "shared" {
  name                        = "noncomp-multi-kv01"
  location                    = azurerm_resource_group.core.location
  resource_group_name         = azurerm_resource_group.core.name
  tenant_id                   = "00000000-0000-0000-0000-000000000000"
  sku_name                    = "standard"
  enable_rbac_authorization   = false
  purge_protection_enabled    = false
  soft_delete_retention_days  = 7
  public_network_access_enabled = true

  network_acls {
    bypass         = ["AzureServices"]
    default_action = "Allow"
  }
}

resource "azurerm_app_service_plan" "shared" {
  name                = "asp-multi-noncompliant"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name

  sku {
    tier = "Basic"
    size = "B1"
  }
}

resource "azurerm_app_service" "shared" {
  name                = "noncomp-multi-web-01"
  location            = azurerm_resource_group.core.location
  resource_group_name = azurerm_resource_group.core.name
  app_service_plan_id = azurerm_app_service_plan.shared.id

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

resource "azurerm_mssql_server" "shared" {
  name                         = "noncomp-multi-sqlsrv"
  resource_group_name          = azurerm_resource_group.core.name
  location                     = azurerm_resource_group.core.location
  version                      = "12.0"
  administrator_login          = "sqladminuser"
  administrator_login_password = "WeakPass1"
  minimum_tls_version          = "1.0"
  public_network_access_enabled = true

  identity {
    type = "None"
  }
}
