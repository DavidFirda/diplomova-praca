# vsetky nastavenia (krysanova/verdikt, s RAG a bez) pre zvolene modely a seedy
# napr. .\spusti_porovnanie.ps1 -Models gpt-oss:20b -Seeds 1 -Zadanie
param(
    [string[]]$Models = @("gpt-oss:20b", "qwen3.8:27b"),
    [int[]]$Seeds = @(1, 2, 3),
    [int]$N = 3,
    [switch]$Zadanie
)
# bez [string[]] sa --zadanie rozseka na znaky
[string[]]$extra = if ($Zadanie) { @("--zadanie") } else { @() }
$configs = @(@(), @("--rag"), @("--prompt", "verdikt"), @("--prompt", "verdikt", "--rag"))
foreach ($model in $Models) {
    # qwen bez thinking, pri gpt-oss sa vypnut neda
    [string[]]$think = if ($model -like "gpt-oss*") { @() } else { @("--think", "false") }
    foreach ($seed in $Seeds) {
        foreach ($cfg in $configs) {
            Write-Host "`n##### $model | seed $seed | $($cfg -join ' ')" -ForegroundColor Cyan
            python hw_eval.py --models $model --n $N --seed $seed @think @cfg @extra
        }
    }
}
python hw_grafy.py
