-- armstrong_criteria.lua
-- IGNITE Medical Imaging Suite v5.2.0
-- Klinische Entscheidungskriterien nach Armstrong et al. (1997, 2007)
-- mit Differentialdiagnose: Pathologische Entzündung vs. Biomechanische Druckstelle
-- und deterministischer Deeskalation bilateraler Muskelphysiologie (Waden/Oberschenkel)

function evaluate_hotspot(hotspot, stats)
    local contra_delta = hotspot.contra_delta
    if contra_delta == nil then
        local baseline = stats.orig_median or stats.median or 120.0
        contra_delta = hotspot.max_val - baseline
    end
    local prominence = hotspot.local_prominence or contra_delta
    local area = hotspot.area_pixels or 0
    local circularity = hotspot.circularity or 0.5
    local edge_grad = hotspot.edge_gradient or 0.0
    local halo_delta = hotspot.halo_delta or 0.0
    local laplacian = hotspot.thermal_laplacian or 0.0
    local peak_to_mean = hotspot.peak_to_mean or 1.0

    -- Biophysikalische Kriterien:
    local is_sharp_edge = edge_grad >= 3.0
    local has_halo = halo_delta >= 5.0
    local is_focal_metabolic = laplacian <= -3.5 or peak_to_mean >= 1.25

    -- 0. Deeskalation bilateral symmetrischer Muskelphysiologie (Waden / Oberschenkel):
    -- Wenn kontralaterale Asymmetrie unter dem Armstrong-Schwellenwert (1.8 K) liegt und keine fokale Überhöhung vorliegt:
    if contra_delta < 18.0 and prominence < 25.0 then
        return {
            risk_level = "BENIGN",
            diagnosis_type = "BENIGN",
            recommendation = "Physiologische Gewebesymmetrie / normaler Muskelbefund (Armstrong Asymmetrie Delta T < 1.8 K).",
            score = 1.0
        }
    end

    -- 1. Kritisches Kriterium nach Armstrong (Delta T >= 2.2 K, ca. >= 22 Einheiten):
    if contra_delta >= 22.0 or (contra_delta >= 18.0 and prominence >= 30.0) then
        if is_sharp_edge and not has_halo then
            -- Steile Hornhautgrenze + Asymmetrie = Entzündete Druckstelle unter isolierender Hyperkeratose
            return {
                risk_level = "CRITICAL",
                diagnosis_type = "INFLAMED_PRESSURE_POINT",
                recommendation = "AKUT GEFÄHRDET: Entzündete Druckstelle / Prä-Ulkus unter Hyperkeratose (Armstrong Delta T >= 2.2 K). Hohes Ulzerationsrisiko! Sofortige Entlastung (Total Contact Cast / orthopädischer Entlastungsschuh) und podologisches Debridement der Hornhautplatte indiziert.",
                score = 9.8
            }
        elseif circularity >= 0.08 then
            -- Weicher Diffusions-Gradient oder perifokaler Halo = Echte Weichteilentzündung
            return {
                risk_level = "CRITICAL",
                diagnosis_type = "INFLAMMATION",
                recommendation = "Pathologischer Entzündungsherd (Armstrong Delta T >= 2.2 K, perifokaler Diffusionshalo). Verdacht auf floride Weichteilinfektion / Phlegmone. Sofortige Druckentlastung, Kühlung/Ruhigstellung und fachärztliche Wundinspektion indiziert.",
                score = 9.5
            }
        else
            return {
                risk_level = "MODERATE",
                diagnosis_type = "INFLAMMATION",
                recommendation = "Erhöhte Temperaturdifferenz mit linearer Ausdehnung. Verdacht auf reaktive Sehnenreizung oder oberflächliche Venenbegleitentzündung. Verlaufskontrolle in 48 Stunden.",
                score = 5.5
            }
        end

    -- 2. Grenzbefund / Moderate Hyperthermie (1.2 K bis 2.1 K):
    elseif (contra_delta >= 12.0 or prominence >= 25.0) and area >= 200 then
        if is_sharp_edge and not has_halo then
            return {
                risk_level = "MODERATE",
                diagnosis_type = "PRESSURE_POINT",
                recommendation = "Biomechanische Druckstelle / Hyperkeratose (1.2 K <= Delta T < 2.2 K, scharfe Hornhautgrenze ohne Entzündungshalo). Mechanische Überlastung / Reibungsspitze. Orthopädische Schuhzurichtung, Druckverteilungseinlage und Hornhautabtragung empfohlen.",
                score = 5.2
            }
        elseif has_halo or is_focal_metabolic then
            return {
                risk_level = "MODERATE",
                diagnosis_type = "INFLAMMATION",
                recommendation = "Subklinische Weichteilentzündung (1.2 K <= Delta T < 2.2 K, perifokale Gefäßerweiterung). Beginnende Gewebehyperämie. Belastungsreduktion und Nachkontrolle in 48 Stunden.",
                score = 6.0
            }
        else
            return {
                risk_level = "MODERATE",
                diagnosis_type = "PRESSURE_POINT",
                recommendation = "Mäßige Gewebeerwärmung an Belastungszone. Verdacht auf mechanische Reibungsdruckstelle. Entlastendes Schuhwerk prüfen.",
                score = 4.8
            }
        end

    -- 3. Geringgradige Erwärmung / Physiologisch:
    else
        return {
            risk_level = "BENIGN",
            diagnosis_type = "BENIGN",
            recommendation = "Physiologische Normaltemperatur / unkritischer Gewebebefund. Keine Intervention erforderlich.",
            score = 1.0
        }
    end
end
