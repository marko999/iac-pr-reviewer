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
$outputFormat = $null
$modules = @()
$sources = @()
$options = @{}
$ruleNames = [System.Collections.ArrayList]::new()
$inputType = $null

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
        $list = [System.Collections.ArrayList]@($existing)
        $null = $list.Add($Value)
        $Target[$Key] = $list
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
                switch ($key.ToLowerInvariant()) {
                    'baseline' {
                        # Baseline option ignored for now; PSRule defaults apply.
                    }
                    'includerule' {
                        $values = @()
                        if ($convertedValue -is [System.Collections.IEnumerable] -and -not ($convertedValue -is [string])) {
                            foreach ($entry in $convertedValue) {
                                if ($entry) { $values += $entry.ToString().Trim() }
                            }
                        }
                        else {
                            $values = $convertedValue.ToString().Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
                        }
                        foreach ($name in $values) { $null = $ruleNames.Add($name) }
                    }
                    default {
                        # Unhandled option keys are ignored for now; PSRule severity overrides are applied in Python.
                    }
                }
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

if ($modules.Count -gt 0) {
    $invokeParams['Module'] = $modules
}

if ($ruleNames.Count -gt 0) {
    $invokeParams['Name'] = [string[]]$ruleNames
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

if ($inputType) {
    $options['input'] = @{ 'type' = $inputType }
}

if ($options.Count -gt 0) {
    $optionObject = New-PSRuleOption -Option $options
    $invokeParams['Option'] = $optionObject
}

try {
    $output = Invoke-PSRule @invokeParams

    if ($null -ne $output) {
        if (-not ($output -is [string])) {
            $output = $output | ConvertTo-Json -Depth 10
        }
        [Console]::Out.Write($output)
    }
    else {
        [Console]::Out.Write('{\"results\":[]}')
    }
}
catch {
    Write-Warning ("Invoke-PSRule failed: {0}" -f $_.Exception.Message)
    [Console]::Out.Write('{\"results\":[]}')
    exit 0
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
