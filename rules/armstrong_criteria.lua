-- armstrong_criteria.lua
-- IGNITE Medical Imaging Suite v5.0.0
-- Klinische Entscheidungskriterien nach Armstrong et al. (1997, 2007)
-- mit Differentialdiagnose: Pathologische Entzündung vs. Biomechanische Druckstelle

function evaluate_hotspot(hotspot, stats)
    -- delta_t entspricht dem relativen Temperaturanstieg gegenüber dem gesunden Gewebemedian
    local baseline = stats.orig_median or stats.median or 120.0
    local delta_t = hotspot.max_val - baseline
    local circularity = hotspot.circularity or 0.5
    local edge_grad = hotspot.edge_gradient or 0.0
    local halo_delta = hotspot.halo_delta or 0.0
    local laplacian = hotspot.thermal_laplacian or 0.0
    local peak_to_mean = hotspot.peak_to_mean or 1.0

    -- Biophysikalische Kriterien:
    -- 1. Steiler Randgradient (>= 3.0) signalisiert scharfe Hornhautbegrenzung (Druckstelle/Callus)
    local is_sharp_edge = edge_grad >= 3.0
    -- 2. Signifikanter Perifokal-Halo (>= 5.0) signalisiert reaktive Kapillarhyperämie (Entzündung)
    local has_halo = halo_delta >= 5.0
    -- 3. Stark negativer Laplace-Kern (<= -3.5) oder hohe Spitzheit: aktiver metabolischer Wärmequell-Fokus
    local is_focal_metabolic = laplacian <= -3.5 or peak_to_mean >= 1.25

    -- 1. Kritisches Kriterium nach Armstrong (Delta T >= 2.2 K, in 8-Bit ca. >= 22 Intensitätseinheiten)
    if delta_t >= 22.0 then
        if is_sharp_edge and not has_halo then
            -- Steile Hornhautgrenze + extreme Hitze = Entzündete Druckstelle unter isolierender Hyperkeratose
            return {
                risk_level = "CRITICAL",
                diagnosis_type = "INFLAMED_PRESSURE_POINT",
                recommendation = "AKUT GEFÄHRDET: Entzündete Druckstelle / Prä-Ulkus unter Hyperkeratose (Armstrong Delta T >= 2.2 K). Hohes Ulzerationsrisiko! Sofortige Entlastung (Total Contact Cast / orthopädischer Entlastungsschuh) und podologisches Debridement der Hornhautplatte indiziert.",
                score = 9.8
            }
        elseif circularity >= 0.12 then
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

    -- 2. Grenzbefund / Moderate Hyperthermie (1.2 K bis 2.1 K, ca. 12 bis 21 Einheiten)
    elseif delta_t >= 12.0 then
        if is_sharp_edge and not has_halo then
            -- Typische mechanische Druckstelle ohne floride Weichteilinfektion
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

    -- 3. Geringgradige Erwärmung / Physiologisch (Delta T < 1.2 K)
    else
        if is_sharp_edge then
            return {
                risk_level = "LOW",
                diagnosis_type = "PRESSURE_POINT",
                recommendation = "Oberflächliche Verhornung / milde Druckstelle ohne akute Entzündungszeichen. Regelmäßige podologische Pflege ausreichend.",
                score = 2.0
            }
        else
            return {
                risk_level = "BENIGN",
                diagnosis_type = "BENIGN",
                recommendation = "Physiologische Normaltemperatur / unkritischer Gewebebefund. Keine Intervention erforderlich.",
                score = 1.0
            }
        end
    end
end

