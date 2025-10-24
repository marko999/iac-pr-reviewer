#!/usr/bin/env pwsh
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$arguments = @($args)

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
                $options[$key] = $value
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

Import-Module -Name PSRule -ErrorAction Stop
Import-Module -Name PSRule.Rules.Azure -ErrorAction SilentlyContinue

$invokeParams = @{ InputPath = $inputPath; OutputFormat = 'Json' }

if ($inputType) {
    $invokeParams['InputType'] = $inputType
}

if ($modules.Count -gt 0) {
    $invokeParams['Module'] = $modules
}

if ($sources.Count -gt 0) {
    $invokeParams['Source'] = $sources
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
