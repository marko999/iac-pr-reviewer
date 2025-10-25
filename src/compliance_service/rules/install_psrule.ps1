#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string[]]
    $Modules
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-Modules {
    param(
        [Parameter(Mandatory = $false)]
        [string[]]$ExplicitModules
    )

    if ($ExplicitModules -and $ExplicitModules.Count -gt 0) {
        return $ExplicitModules
    }

    if ($env:PSRULE_MODULES) {
        return @(
            $env:PSRULE_MODULES.Split(',') |
                ForEach-Object { $_.Trim() } |
                Where-Object { $_ }
        )
    }

    return @()
}

function Ensure-NuGetProvider {
    if (Get-PackageProvider -Name NuGet -ErrorAction SilentlyContinue) {
        return
    }

    Install-PackageProvider -Name NuGet -Scope CurrentUser -Force -Confirm:$false | Out-Null
}

function Trust-PSGallery {
    if (-not (Get-Command Set-PSRepository -ErrorAction SilentlyContinue)) {
        return
    }

    try {
        Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -ErrorAction Stop
    }
    catch {
        Write-Verbose "Failed to update PSGallery trust policy: $($_.Exception.Message)"
    }
}

function Install-ModuleIfMissing {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ModuleName
    )

    $moduleRoot = Join-Path -Path $env:HOME -ChildPath ".local/share/powershell/Modules/$ModuleName"
    if (Test-Path -Path $moduleRoot) {
        Write-Verbose "Module already present: $ModuleName"
        return
    }

    Install-Module -Name $ModuleName -Scope CurrentUser -Force -Confirm:$false
}

$moduleList = Resolve-Modules -ExplicitModules $Modules
if ($moduleList.Count -eq 0) {
    Write-Verbose "No PSRule modules requested for installation."
    return
}

Ensure-NuGetProvider
Trust-PSGallery

$uniqueModules = @($moduleList | Sort-Object -Unique)
foreach ($module in $uniqueModules) {
    Install-ModuleIfMissing -ModuleName $module
}
