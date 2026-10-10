for ($i = 1; $i -le 21; $i++) {
    $img = "..\test-data\bild ($i).jpeg"
    $out = "test_eval_$i.json"
    if (Test-Path $img) {
        $p = Start-Process -FilePath ".\ignite-core.exe" -ArgumentList "-mode=cli", "-input=`"$img`"", "-output=`"$out`"" -NoNewWindow -Wait -PassThru
        if (Test-Path $out) {
            $raw = Get-Content $out -Raw
            $json = ConvertFrom-Json $raw
            $hotspots = $json.hotspots
            $critCount = 0
            if ($hotspots) {
                foreach ($h in $hotspots) {
                    if ($h.assessment.risk_level -eq "CRITICAL") { $critCount++ }
                }
            }
            $cnt = if ($hotspots) { $hotspots.Count } else { 0 }
            Write-Host "Bild $i : Stages=$($json.total_stages) | Hotspots=$cnt | Critical=$critCount | Risk=$($json.highest_risk) | TotalMs=$($json.timing.total_ms)"
            Remove-Item $out -Force
        } else {
            Write-Host "Bild $i : Output not created"
        }
    }
}
