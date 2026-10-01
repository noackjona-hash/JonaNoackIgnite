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

// func fmaVectorFloat32AVX2(src, dst *float32, factor float32, count int)
// Computes dst[i] += factor * src[i] for count float32 elements
TEXT ·fmaVectorFloat32AVX2(SB), NOSPLIT, $0-32
    MOVQ src+0(FP), SI
    MOVQ dst+8(FP), DI
    VMOVSS factor+16(FP), X0
    MOVQ count+24(FP), CX

    VSHUFPS $0, X0, X0, X0
    VINSERTF128 $1, X0, Y0, Y0

    CMPQ CX, $8
    JL scalar_fma

loop_avx2_fma:
    VMOVUPS (SI), Y1
    VMOVUPS (DI), Y2
    VMULPS Y0, Y1, Y3
    VADDPS Y3, Y2, Y4
    VMOVUPS Y4, (DI)

    ADDQ $32, SI
    ADDQ $32, DI
    SUBQ $8, CX
    CMPQ CX, $8
    JGE loop_avx2_fma
    VZEROUPPER

scalar_fma:
    CMPQ CX, $0
    JLE done_fma

loop_scalar_fma:
    VMOVSS (SI), X1
    VMULSS X0, X1, X2
    VMOVSS (DI), X3
    VADDSS X2, X3, X4
    VMOVSS X4, (DI)

    ADDQ $4, SI
    ADDQ $4, DI
    DECQ CX
    JNZ loop_scalar_fma

done_fma:
    RET

// func mulScalarFloat32AVX2(src, dst *float32, factor float32, count int)
// Computes dst[i] = factor * src[i] for count float32 elements
TEXT ·mulScalarFloat32AVX2(SB), NOSPLIT, $0-32
    MOVQ src+0(FP), SI
    MOVQ dst+8(FP), DI
    VMOVSS factor+16(FP), X0
    MOVQ count+24(FP), CX

    VSHUFPS $0, X0, X0, X0
    VINSERTF128 $1, X0, Y0, Y0

    CMPQ CX, $8
    JL scalar_mul

loop_avx2_mul:
    VMOVUPS (SI), Y1
    VMULPS Y0, Y1, Y2
    VMOVUPS Y2, (DI)

    ADDQ $32, SI
    ADDQ $32, DI
    SUBQ $8, CX
    CMPQ CX, $8
    JGE loop_avx2_mul
    VZEROUPPER

scalar_mul:
    CMPQ CX, $0
    JLE done_mul

loop_scalar_mul:
    VMOVSS (SI), X1
    VMULSS X0, X1, X2
    VMOVSS X2, (DI)

    ADDQ $4, SI
    ADDQ $4, DI
    DECQ CX
    JNZ loop_scalar_mul

done_mul:
    RET

// func thresholdMaskAVX2(diff, orig, mask, dst *byte, count int, threshold, origMedian byte)
TEXT ·thresholdMaskAVX2(SB), NOSPLIT, $0-48
    MOVQ diff+0(FP), SI
    MOVQ orig+8(FP), DX
    MOVQ mask+16(FP), R8
    MOVQ dst+24(FP), DI
    MOVQ count+32(FP), CX

    // Broadcast threshold to all 32 bytes of Y0
    MOVBLZX threshold+40(FP), AX
    MOVQ $0x0101010101010101, BX
    IMULQ BX, AX
    VMOVQ AX, X0
    VPBROADCASTQ X0, Y0

    // Broadcast origMedian to all 32 bytes of Y1
    MOVBLZX origMedian+41(FP), AX
    IMULQ BX, AX
    VMOVQ AX, X1
    VPBROADCASTQ X1, Y1

    CMPQ CX, $32
    JL scalar_thresh

loop_avx2_thresh:
    VMOVDQU (SI), Y2 // diff

    // diff >= threshold: max(diff, threshold) == diff
    VPMAXUB Y0, Y2, Y3
    VPCMPEQB Y2, Y3, Y4 // Y4 = 0xFF where diff >= threshold

    // If orig != nil
    CMPQ DX, $0
    JE skip_orig_check
    VMOVDQU (DX), Y5
    VPMAXUB Y1, Y5, Y6
    VPCMPEQB Y5, Y6, Y7 // Y7 = 0xFF where orig >= origMedian
    VPAND Y7, Y4, Y4

skip_orig_check:
    // If mask != nil
    CMPQ R8, $0
    JE skip_mask_check
    VMOVDQU (R8), Y8
    VPAND Y8, Y4, Y4 // Apply mask

skip_mask_check:
    VMOVDQU Y4, (DI)

    ADDQ $32, SI
    CMPQ DX, $0
    JE no_inc_dx
    ADDQ $32, DX
no_inc_dx:
    CMPQ R8, $0
    JE no_inc_r8
    ADDQ $32, R8
no_inc_r8:
    ADDQ $32, DI
    SUBQ $32, CX
    CMPQ CX, $32
    JGE loop_avx2_thresh
    VZEROUPPER

scalar_thresh:
    CMPQ CX, $0
    JLE done_thresh

loop_scalar_thresh:
    MOVB (SI), AL
    CMPB AL, threshold+40(FP)
    JB fail_thresh

    CMPQ DX, $0
    JE check_mask_scalar
    MOVB (DX), BL
    CMPB BL, origMedian+41(FP)
    JB fail_thresh

check_mask_scalar:
    CMPQ R8, $0
    JE pass_thresh
    MOVB (R8), BL
    CMPB BL, $0
    JE fail_thresh

pass_thresh:
    MOVB $255, (DI)
    JMP next_scalar_thresh

fail_thresh:
    MOVB $0, (DI)

next_scalar_thresh:
    INCQ SI
    CMPQ DX, $0
    JE no_inc_dx_scalar
    INCQ DX
no_inc_dx_scalar:
    CMPQ R8, $0
    JE no_inc_r8_scalar
    INCQ R8
no_inc_r8_scalar:
    INCQ DI
    DECQ CX
    JNZ loop_scalar_thresh

done_thresh:
    RET
