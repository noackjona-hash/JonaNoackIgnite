; ==============================================================================
; IGNITE Medical Imaging Suite — x86_64 SIMD Assembly Kernel
; Jugend forscht 2026 — Jona Noack
;
; Funktion: simd_threshold(const uint8_t* src, uint8_t* dst, uint8_t threshold, size_t count)
;
; Zweck im medizinischen Algorithmus:
;   Stufe 29 der IGNITE-Pipeline: Vektorisierter Schwellwertvergleich
;   dst[i] = (src[i] >= threshold) ? 255 : 0
;   Binarisiert das Gewebebild blitzschnell zur Maskierung potentieller Ulzera.
;
; Aufrufkonvention (Windows x64 ABI):
;   RCX = Zeiger auf src
;   RDX = Zeiger auf dst
;   R8B = Schwellwert (threshold als 8-Bit Wert)
;   R9  = Anzahl der Pixel (count)
; ==============================================================================

global simd_threshold
section .text

simd_threshold:
    test r9, r9
    jz .done

    ; Broadcast des 8-Bit Schwellwertes in alle 16 Bytes von XMM2
    movd xmm2, r8d
    punpcklbw xmm2, xmm2
    punpcklwd xmm2, xmm2
    pshufd xmm2, xmm2, 0        ; XMM2 enthält nun 16x den Schwellwert

.vec_loop:
    cmp r9, 16
    jb .scalar_loop

    movdqu xmm0, [rcx]          ; Lade 16 Pixel

    ; Vorzeichenlose Sättigungssubtraktion: diff = max(0, src - thresh)
    movdqu xmm1, xmm0
    psubusb xmm1, xmm2

    ; Erzeuge Maske: Wenn diff > 0, dann 255, sonst 0
    pxor xmm3, xmm3
    pcmpeqb xmm1, xmm3          ; xmm1 = 0xFF wo diff == 0
    pcmpeqb xmm4, xmm4          ; xmm4 = 0xFF überall
    pxor xmm1, xmm4             ; Invertiere: 0xFF wo diff > 0

    movdqu [rdx], xmm1          ; 16 binarisierte Pixel schreiben

    add rcx, 16
    add rdx, 16
    sub r9, 16
    jmp .vec_loop

.scalar_loop:
    test r9, r9
    jz .done

    mov al, [rcx]
    cmp al, r8b
    jae .set_max
    mov byte [rdx], 0
    jmp .next

.set_max:
    mov byte [rdx], 255

.next:
    inc rcx
    inc rdx
    dec r9
    jnz .scalar_loop

.done:
    ret
