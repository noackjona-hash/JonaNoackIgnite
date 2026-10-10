for ($i=1; $i -le 21; $i++) {
    $out = "eval_detail_$i.json"
    $img = "..\test-data\bild ($i).jpeg"
    & .\ignite-core.exe -mode=cli -input="$img" -output="$out" | Out-Null
    if (Test-Path $out) {
        $raw = Get-Content $out -Raw
        $data = ConvertFrom-Json $raw
        Write-Host "=== BILD $i (Total: $($data.hotspots.Count), HighestRisk: $($data.highest_risk)) ==="
        foreach ($h in $data.hotspots) {
            $r = $h.region
            $a = $h.assessment
            Write-Host "  Spot: Center=($($r.center_x),$($r.center_y)) Box=[$($r.bounding_box[0]),$($r.bounding_box[1]) to $($r.bounding_box[2]),$($r.bounding_box[3])] Max=$($r.max_val) ContraDelta=$($r.contra_delta) Area=$($r.area) Label=$($a.finding_type) Risk=$($a.risk_level) EdgeGrad=$($r.edge_gradient)"
        }
        Remove-Item $out -Force
    }
}
