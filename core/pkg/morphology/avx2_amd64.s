#include "textflag.h"

// ============================================================================
// IGNITE v5.0.0 HIGH-PERFORMANCE x86_64 AVX2 SIMD ASSEMBLY KERNELS
// ============================================================================

// func minVectorAVX2(src, dst *byte, count int)
// Computes dst[i] = min(dst[i], src[i]) for count bytes using 256-bit AVX2 VPMINUB
TEXT ·minVectorAVX2(SB), NOSPLIT, $0-24
    MOVQ src+0(FP), SI
    MOVQ dst+8(FP), DI
    MOVQ count+16(FP), CX

    CMPQ CX, $32
    JL scalar_min

loop_avx2_min:
    VMOVDQU (SI), Y0
    VMOVDQU (DI), Y1
    VPMINUB Y0, Y1, Y2
    VMOVDQU Y2, (DI)

    ADDQ $32, SI
    ADDQ $32, DI
    SUBQ $32, CX
    CMPQ CX, $32
    JGE loop_avx2_min
    VZEROUPPER

scalar_min:
    CMPQ CX, $0
    JLE done_min

loop_scalar_min:
    MOVB (SI), AL
    MOVB (DI), BL
    CMPB AL, BL
    JAE next_scalar_min
    MOVB AL, (DI)

next_scalar_min:
    INCQ SI
    INCQ DI
    DECQ CX
    JNZ loop_scalar_min

done_min:
    RET

// func maxVectorAVX2(src, dst *byte, count int)
// Computes dst[i] = max(dst[i], src[i]) for count bytes using 256-bit AVX2 VPMAXUB
TEXT ·maxVectorAVX2(SB), NOSPLIT, $0-24
    MOVQ src+0(FP), SI
    MOVQ dst+8(FP), DI
    MOVQ count+16(FP), CX

    CMPQ CX, $32
    JL scalar_max

loop_avx2_max:
    VMOVDQU (SI), Y0
    VMOVDQU (DI), Y1
    VPMAXUB Y0, Y1, Y2
    VMOVDQU Y2, (DI)

    ADDQ $32, SI
    ADDQ $32, DI
    SUBQ $32, CX
    CMPQ CX, $32
    JGE loop_avx2_max
    VZEROUPPER

scalar_max:
    CMPQ CX, $0
    JLE done_max

loop_scalar_max:
    MOVB (SI), AL
    MOVB (DI), BL
    CMPB AL, BL
    JBE next_scalar_max
    MOVB AL, (DI)

next_scalar_max:
    INCQ SI
    INCQ DI
    DECQ CX
    JNZ loop_scalar_max

done_max:
    RET

// func subVectorAVX2(a, b, dst *byte, count int)
// Computes dst[i] = max(0, a[i] - b[i]) using 256-bit AVX2 VPSUBUSB
TEXT ·subVectorAVX2(SB), NOSPLIT, $0-32
    MOVQ a+0(FP), SI
    MOVQ b+8(FP), DX
    MOVQ dst+16(FP), DI
    MOVQ count+24(FP), CX

    CMPQ CX, $32
    JL scalar_sub

loop_avx2_sub:
    VMOVDQU (SI), Y0
    VMOVDQU (DX), Y1
    VPSUBUSB Y1, Y0, Y2
    VMOVDQU Y2, (DI)

    ADDQ $32, SI
    ADDQ $32, DX
    ADDQ $32, DI
    SUBQ $32, CX
    CMPQ CX, $32
    JGE loop_avx2_sub
    VZEROUPPER

scalar_sub:
    CMPQ CX, $0
    JLE done_sub

loop_scalar_sub:
    MOVB (SI), AL
    MOVB (DX), BL
    SUBB BL, AL
    JNC store_sub
    XORB AL, AL

store_sub:
    MOVB AL, (DI)
    INCQ SI
    INCQ DX
    INCQ DI
    DECQ CX
    JNZ loop_scalar_sub

done_sub:
    RET

// func absDiffVectorAVX2(a, b, dst *byte, count int)
// Computes dst[i] = |a[i] - b[i]| for 32 pixels in parallel: max(a-b, 0) | max(b-a, 0)
TEXT ·absDiffVectorAVX2(SB), NOSPLIT, $0-32
    MOVQ a+0(FP), SI
    MOVQ b+8(FP), DX
    MOVQ dst+16(FP), DI
    MOVQ count+24(FP), CX

    CMPQ CX, $32
    JL scalar_abs_diff

loop_avx2_abs_diff:
    VMOVDQU (SI), Y0
    VMOVDQU (DX), Y1

    VPSUBUSB Y1, Y0, Y2 // Y2 = max(0, a - b)
    VPSUBUSB Y0, Y1, Y3 // Y3 = max(0, b - a)
    VPOR Y2, Y3, Y4     // Y4 = |a - b|
    VMOVDQU Y4, (DI)

    ADDQ $32, SI
    ADDQ $32, DX
    ADDQ $32, DI
    SUBQ $32, CX
    CMPQ CX, $32
    JGE loop_avx2_abs_diff
    VZEROUPPER

scalar_abs_diff:
    CMPQ CX, $0
    JLE done_abs_diff

loop_scalar_abs_diff:
    MOVB (SI), AL
    MOVB (DX), BL
    CMPB AL, BL
    JAE a_ge_b
    SUBB AL, BL
    MOVB BL, (DI)
    JMP next_scalar_abs_diff
a_ge_b:
    SUBB BL, AL
    MOVB AL, (DI)

next_scalar_abs_diff:
    INCQ SI
    INCQ DX
    INCQ DI
    DECQ CX
    JNZ loop_scalar_abs_diff

done_abs_diff:
    RET
