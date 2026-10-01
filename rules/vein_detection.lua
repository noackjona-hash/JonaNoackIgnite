-- vein_detection.lua
-- IGNITE Medical Imaging Suite v5.0.0
-- Differenzierung zwischen oberflaechlichen Venen und entzuendlichen Herden.

function evaluate_hotspot(hotspot, stats)
    local delta_t = hotspot.max_val - stats.median
    local circularity = hotspot.circularity

    -- Stark elongierte Strukturen mit geringer Zirkularitaet sind Venen/Adern
    if circularity < 0.10 then
        return {
            risk_level = "BENIGN",
            recommendation = "Klassifiziert als oberflaechliche Vene (tubulaere Geometrie, Zirkularitaet < 0.10). Keine pathologische Relevanz.",
            score = 0.5
        }
    elseif delta_t > 20.0 and circularity >= 0.20 then
        return {
            risk_level = "CRITICAL",
            recommendation = "Kompakter, kreisfoermiger Herd mit signifikanter Hyperthermie. Sehr unwahrscheinlich ein Gefaess: Entzuendungsfokus.",
            score = 9.0
        }
    else
        return {
            risk_level = "MODERATE",
            recommendation = "Grenzfall zwischen Gefaessabzweigung und kleiner Entzuendungszone.",
            score = 4.0
        }
    end
end
