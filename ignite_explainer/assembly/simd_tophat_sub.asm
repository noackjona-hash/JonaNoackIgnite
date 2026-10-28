; ==============================================================================
; IGNITE Medical Imaging Suite — x86_64 SIMD Assembly Kernel
; Jugend forscht 2026 — Jona Noack
;
; Funktion: simd_saturating_sub(const uint8_t* a, const uint8_t* b, uint8_t* dst, size_t count)
;
; Zweck im medizinischen Algorithmus:
;   Stufe 24 der IGNITE-Pipeline: Morphologischer White Top-Hat
;   WTH(I) = I - (I o B)
;   Berechnet die vorzeichenlose sättigende Differenz: dst[i] = max(0, a[i] - b[i])
;   Dadurch werden fokale Hyperthermiepeaks (Entzündungsherde) isoliert,
;   während negative Differenzen (kältere Areale) ohne Unterlauf auf 0 geclippt werden.
;
; Aufrufkonvention (Windows x64 ABI):
;   RCX = Zeiger auf Array a (Originalbild I)
;   RDX = Zeiger auf Array b (Morphologisch geöffnetes Bild I o B)
;   R8  = Zeiger auf Zielarray dst (Top-Hat Differenzbild)
;   R9  = Anzahl der Pixel (count)
; ==============================================================================

global simd_saturating_sub
section .text

simd_saturating_sub:
    ; 1. Sicherheitsprüfung: Wenn count == 0, sofort beenden
    test r9, r9
    jz .done

.vector_loop:
    ; Prüfe, ob mindestens 16 Bytes verbleiben
    cmp r9, 16
    jb .scalar_loop

    ; 16 Pixel parallel mit SSE2 laden
    movdqu xmm0, [rcx]           ; Lade 16 Bytes von Bild A (Original) in XMM0
    movdqu xmm1, [rdx]           ; Lade 16 Bytes von Bild B (Opening) in XMM1

    ; Sättigende vorzeichenlose Subtraktion: dst = max(0, a - b)
    ; Verhindert arithmetischen Unterlauf (z.B. 10 - 25 = 0 statt 241)
    psubusb xmm0, xmm1          ; 16 Pixel in einem einzigen Taktzyklus berechnet!

    ; Ergebnis in das Zielarray schreiben
    movdqu [r8], xmm0           ; Schreibe 16 Bytes in dst

    ; Zeiger um 16 Bytes weiterschalten
    add rcx, 16
    add rdx, 16
    add r8, 16
    sub r9, 16
    jmp .vector_loop

.scalar_loop:
    ; Reste bearbeiten (für Bildbreiten, die kein Vielfaches von 16 sind)
    test r9, r9
    jz .done

    mov al, [rcx]               ; Lade 1 Byte von A in AL
    mov r10b, [rdx]             ; Lade 1 Byte von B in R10B
    sub al, r10b                ; AL = AL - R10B
    jnc .store                  ; Wenn Carry-Flag = 0 (kein Unterlauf), weiter

    xor al, al                  ; Bei Unterlauf: AL = 0 (Clipping)

.store:
    mov [r8], al                ; Byte abspeichern
    inc rcx
    inc rdx
    inc r8
    dec r9
    jnz .scalar_loop

.done:
    ret
