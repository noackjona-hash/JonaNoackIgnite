-- perfusion_eval.lua
-- IGNITE Medical Imaging Suite v5.0.0
-- Beurteilung des longitudinalen Temperaturgradienten zur Erkennung von pAVK.

function evaluate_perfusion_drop(max_drop, hypo_area_percent)
    if max_drop > 4.5 or hypo_area_percent > 30.0 then
        return {
            risk_level = "CRITICAL",
            recommendation = "Kritische distale Ischaemie. Dringende angiologische/gefaesschirurgische Abklaerung indiziert.",
            score = 10.0
        }
    elseif max_drop > 2.0 or hypo_area_percent > 10.0 then
        return {
            risk_level = "MODERATE",
            recommendation = "Beginnende periphere Minderperfusion. Doppler-Verschlussdruckmessung (ABI) empfohlen.",
            score = 5.0
        }
    else
        return {
            risk_level = "BENIGN",
            recommendation = "Homogene Gewebeperfusion ohne signifikanten Gefaessverschluss.",
            score = 1.0
        }
    end
end
