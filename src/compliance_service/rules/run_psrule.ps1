#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]
    $Arguments = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$arguments = @($Arguments)

if ($arguments.Count -gt 0 -and $arguments[0].ToLowerInvariant() -eq 'run') {
    if ($arguments.Count -gt 1) {
        $arguments = $arguments[1..($arguments.Count - 1)]
    }
    else {
        $arguments = @()
    }
}

$inputPath = $null
$inputType = $null
$outputFormat = $null
$modules = @()
$sources = @()
$options = @{}

function Convert-OptionValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $trimmed = $Value.Trim()

    switch -Regex ($trimmed) {
        '^(?i:true|false)$' {
            return [bool]::Parse($trimmed)
        }
        '^-?\d+$' {
            return [int]$trimmed
        }
        '^-?\d+\.\d+$' {
            return [double]$trimmed
        }
    }

    if ($trimmed -eq 'null') {
        return $null
    }

    if (($trimmed.StartsWith('{') -and $trimmed.EndsWith('}')) -or (
            $trimmed.StartsWith('[') -and $trimmed.EndsWith(']')
        )) {
        try {
            return $trimmed | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            # Fall back to returning the raw string when JSON parsing fails.
        }
    }

    return $Value
}

function Set-OptionValue {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Target,

        [Parameter(Mandatory = $true)]
        [string]$Key,

        [Parameter(Mandatory = $true)]
        $Value
    )

    if ($Target.ContainsKey($Key)) {
        $existing = $Target[$Key]
        if ($existing -is [System.Collections.IList]) {
            $existing.Add($Value) | Out-Null
        }
        else {
            $Target[$Key] = @($existing, $Value)
        }
    }
    else {
        $Target[$Key] = $Value
    }
}

for ($i = 0; $i -lt $arguments.Count; $i++) {
    $current = $arguments[$i]
    switch ($current) {
        '--input-path' {
            $i++
            if ($i -lt $arguments.Count) {
                $inputPath = $arguments[$i]
            }
        }
        '--input-type' {
            $i++
            if ($i -lt $arguments.Count) {
                $inputType = $arguments[$i]
            }
        }
        '--module' {
            $i++
            if ($i -lt $arguments.Count) {
                $modules += $arguments[$i]
            }
        }
        '--source' {
            $i++
            if ($i -lt $arguments.Count) {
                $sources += $arguments[$i]
            }
        }
        '--option' {
            $i++
            if ($i -lt $arguments.Count) {
                $optionValue = $arguments[$i]
                $separatorIndex = $optionValue.IndexOf('=')
                if ($separatorIndex -ge 0) {
                    $key = $optionValue.Substring(0, $separatorIndex)
                    $value = $optionValue.Substring($separatorIndex + 1)
                }
                else {
                    $key = $optionValue
                    $value = $true
                }
                $convertedValue = Convert-OptionValue -Value $value
                Set-OptionValue -Target $options -Key $key -Value $convertedValue
            }
        }
        '--output-format' {
            $i++
            if ($i -lt $arguments.Count) {
                $outputFormat = $arguments[$i]
            }
        }
        default { }
    }
}

if (-not $inputPath) {
    throw 'Missing required --input-path argument.'
}

try {
    Import-Module -Name PSRule -ErrorAction Stop | Out-Null
}
catch {
    throw 'Unable to load the PSRule module. Please ensure PSRule is installed.'
}

Import-Module -Name PSRule.Rules.Azure -ErrorAction SilentlyContinue | Out-Null

$invokeParams = @{ InputPath = $inputPath; OutputFormat = 'Json' }

if ($inputType) {
    $invokeParams['InputType'] = $inputType
}

if ($modules.Count -gt 0) {
    $invokeParams['Module'] = $modules
}

if ($sources.Count -gt 0) {
    $resolvedSources = @()
    foreach ($sourcePath in $sources) {
        try {
            $resolvedSources += (Resolve-Path -Path $sourcePath -ErrorAction Stop).ProviderPath
        }
        catch {
            $resolvedSources += $sourcePath
        }
    }

    $invokeParams['Source'] = $resolvedSources
}

if ($options.Count -gt 0) {
    $invokeParams['Option'] = $options
}

$output = Invoke-PSRule @invokeParams

if ($null -ne $output) {
    if ($output -is [string]) {
        [Console]::Out.Write($output)
    }
    else {
        foreach ($line in $output) {
            [Console]::Out.WriteLine($line)
        }
    }
}

$exitCode = 0
try {
    $psruleState = Get-Variable -Name PSRule -ValueOnly -ErrorAction Stop
    if ($null -ne $psruleState -and $psruleState.PSObject.Properties['LastExitCode']) {
        $exitCode = [int]$psruleState.LastExitCode
    }
}
catch {
    # Ignore lookup failures; default to success when PSRule does not publish a code.
}

exit $exitCode
