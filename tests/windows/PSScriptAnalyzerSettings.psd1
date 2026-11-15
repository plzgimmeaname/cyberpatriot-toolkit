# PSScriptAnalyzer settings for scripts/windows/Harden.ps1
#
#   pwsh -c "Invoke-ScriptAnalyzer -Path scripts/windows/Harden.ps1 -Settings tests/windows/PSScriptAnalyzerSettings.psd1"
#
# Every default rule runs except four style rules that do not fit a single-file script
# written to be read by beginners. Each exclusion is a deliberate choice, not a silenced bug:
#
#  PSAvoidUsingPositionalParameters    The script's own helpers (Set-Reg, Remove-RegValue, Add-Result...)
#                                      read better positionally. Set-Reg $path 'Name' 1 'DWord' 'why'
#                                      is one readable line; naming all five parameters would double the
#                                      length of hundreds of lines without changing what they do.
#  PSAvoidUsingWriteHost               This is an interactive console program. Colour, progress and prompts
#                                      are the point, and nothing needs to travel down a pipeline.
#  PSUseSingularNouns                  Invoke-Users, Invoke-Updates and Invoke-Services are named after the
#                                      checklist sections they implement, so a student can match script to docs.
#  PSUseShouldProcessForStateChangingFunctions
#                                      The script has its own audit/apply switch: nothing changes unless the
#                                      run is Apply mode and Invoke-Fix wraps the call. A second -WhatIf
#                                      switch would conflict with it.
@{
    IncludeDefaultRules = $true
    ExcludeRules        = @(
        'PSAvoidUsingPositionalParameters'
        'PSAvoidUsingWriteHost'
        'PSUseSingularNouns'
        'PSUseShouldProcessForStateChangingFunctions'
    )
}
