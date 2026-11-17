# qa_eval a gen_eval na troch nastaveniach: gpt-oss, qwen bez uvazovania a qwen s uvazovanim
# napr. .\spusti_3_modely.ps1                  (oba testy, seed 2)
#       .\spusti_3_modely.ps1 -Seed 3 -Test gen -LenProfil
param(
    [int]$Seed = 2,
    [ValidateSet("qa", "gen")][string[]]$Test = @("qa", "gen"),
    [switch]$LenProfil
)
[string[]]$konfig = @("gpt-oss:20b", "qwen3.8:27b@false", "qwen3.8:27b@true")
$start = Get-Date
if ($Test -contains "qa") {
    Write-Host "`n##### qa_eval | seed $Seed" -ForegroundColor Cyan
    python qa_eval.py --konfig @konfig --seed $Seed
}
if ($Test -contains "gen") {
    [string[]]$rezimy = if ($LenProfil) { @("--rezimy", "s_profilom") } else { @() }
    Write-Host "`n##### gen_eval | seed $Seed" -ForegroundColor Cyan
    python gen_eval.py --konfig @konfig --seed $Seed @rezimy
}
Write-Host "`nHotovo za $([int]((Get-Date) - $start).TotalMinutes) min" -ForegroundColor Green
Write-Host "Vysledky na hodnotenie: data\eval\qa\*_review.csv a data\eval\gen\*_review.csv"
