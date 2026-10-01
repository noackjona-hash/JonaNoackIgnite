-- armstrong_criteria.lua
-- IGNITE Medical Imaging Suite v5.0.0
-- Klinische Entscheidungskriterien nach Armstrong et al. (1997, 2007)
-- zur Frueherkennung diabetischer Fussulzera und subklinischer Entzuendungen.

function evaluate_hotspot(hotspot, stats)
    -- delta_t entspricht dem relativen Temperaturanstieg gegenueber dem gesunden Gewebe
    local delta_t = hotspot.max_val - stats.median
    local circularity = hotspot.circularity
    local area_pct = hotspot.area_percent

    -- 1. Kritisches Kriterium nach Armstrong (Delta T >= 2.2 K, in 8-Bit ca. >= 22 Intensitaetseinheiten)
    if delta_t >= 22.0 then
        if circularity >= 0.12 then
            return {
                risk_level = "CRITICAL",
                recommendation = "Pathologischer Entzuendungsherd (Armstrong Delta T >= 2.2 K). Hohes Ulzerationsrisiko: Sofortige Druckentlastung, Schonung und Fachaerztliche Wundinspektion indiziert.",
                score = 9.5
            }
        else
            return {
                risk_level = "MODERATE",
                recommendation = "Erhoehte Temperaturdifferenz, jedoch lineare Struktur. Verdacht auf oberflaechliches Blutgefaess oder Sehnenreizung. Verlaufskontrolle in 48 Stunden.",
                score = 5.0
            }
        end
    -- 2. Grenzbefund / Moderate Hyperthermie (1.2 K bis 2.1 K)
    elseif delta_t >= 12.0 then
        return {
            risk_level = "MODERATE",
            recommendation = "Subklinische Gewebeerwaermung (1.2 K <= Delta T < 2.2 K). Beginnende Hyperaemie oder Reibungsdruckstelle. Entlastendes Schuhwerk pruefen und Nachkontrolle in 48h.",
            score = 6.0
        }
    -- 3. Geringgradige Erwaermung / Physiologisch
    else
        return {
            risk_level = "BENIGN",
            recommendation = "Physiologische Normaltemperatur / unkritischer Befund. Keine Intervention erforderlich.",
            score = 1.0
        }
    end
end
