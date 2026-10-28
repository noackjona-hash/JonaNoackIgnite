#include "textflag.h"

// ============================================================================
// IGNITE v12.3.4.81 HIGH-PERFORMANCE x86_64 AVX2 SIMD ASSEMBLY KERNELS
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

// func dotProductFloat32AVX2(a, b *float32, res *float32, count int)
// Computes res = dot(a, b) for count elements using 256-bit AVX2
TEXT ·dotProductFloat32AVX2(SB), NOSPLIT, $0-32
    MOVQ a+0(FP), SI
    MOVQ b+8(FP), DX
    MOVQ res+16(FP), DI
    MOVQ count+24(FP), CX

    VXORPS Y0, Y0, Y0

    CMPQ CX, $8
    JL scalar_dot

loop_avx2_dot:
    VMOVUPS (SI), Y1
    VMOVUPS (DX), Y2
    VMULPS Y1, Y2, Y3
    VADDPS Y3, Y0, Y0

    ADDQ $32, SI
    ADDQ $32, DX
    SUBQ $8, CX
    CMPQ CX, $8
    JGE loop_avx2_dot

scalar_dot:
    // Horizontal sum of Y0 down to a single float in X0
    VEXTRACTF128 $1, Y0, X1
    VADDPS X1, X0, X0
    VMOVSHDUP X0, X1
    VADDPS X1, X0, X0
    VSHUFPS $0x4E, X0, X0, X1
    VADDSS X1, X0, X0
    VZEROUPPER

    CMPQ CX, $0
    JLE done_dot

loop_scalar_dot:
    VMOVSS (SI), X1
    VMOVSS (DX), X2
    VMULSS X1, X2, X3
    VADDSS X3, X0, X0

    ADDQ $4, SI
    ADDQ $4, DX
    DECQ CX
    JNZ loop_scalar_dot

done_dot:
    VMOVSS X0, (DI)
    RET

// func addVectorFloat32AVX2(a, b, dst *float32, count int)
// Computes dst[i] = a[i] + b[i] for count float32 elements
TEXT ·addVectorFloat32AVX2(SB), NOSPLIT, $0-32
    MOVQ a+0(FP), SI
    MOVQ b+8(FP), DX
    MOVQ dst+16(FP), DI
    MOVQ count+24(FP), CX

    CMPQ CX, $8
    JL scalar_add_f32

loop_avx2_add_f32:
    VMOVUPS (SI), Y0
    VMOVUPS (DX), Y1
    VADDPS Y0, Y1, Y2
    VMOVUPS Y2, (DI)

    ADDQ $32, SI
    ADDQ $32, DX
    ADDQ $32, DI
    SUBQ $8, CX
    CMPQ CX, $8
    JGE loop_avx2_add_f32
    VZEROUPPER

scalar_add_f32:
    CMPQ CX, $0
    JLE done_add_f32

loop_scalar_add_f32:
    VMOVSS (SI), X0
    VMOVSS (DX), X1
    VADDSS X0, X1, X2
    VMOVSS X2, (DI)

    ADDQ $4, SI
    ADDQ $4, DX
    ADDQ $4, DI
    DECQ CX
    JNZ loop_scalar_add_f32

done_add_f32:
    RET

// func scaleOffsetFloat32AVX2(src, dst *float32, scale, offset float32, count int)
// Computes dst[i] = src[i] * scale + offset for count float32 elements
TEXT ·scaleOffsetFloat32AVX2(SB), NOSPLIT, $0-32
    MOVQ src+0(FP), SI
    MOVQ dst+8(FP), DI
    VMOVSS scale+16(FP), X0
    VMOVSS offset+20(FP), X1
    MOVQ count+24(FP), CX

    // Broadcast scale into Y0
    VSHUFPS $0, X0, X0, X0
    VINSERTF128 $1, X0, Y0, Y0

    // Broadcast offset into Y1
    VSHUFPS $0, X1, X1, X1
    VINSERTF128 $1, X1, Y1, Y1

    CMPQ CX, $8
    JL scalar_scale_offset

loop_avx2_scale_offset:
    VMOVUPS (SI), Y2
    VMULPS Y0, Y2, Y3
    VADDPS Y1, Y3, Y4
    VMOVUPS Y4, (DI)

    ADDQ $32, SI
    ADDQ $32, DI
    SUBQ $8, CX
    CMPQ CX, $8
    JGE loop_avx2_scale_offset
    VZEROUPPER

scalar_scale_offset:
    CMPQ CX, $0
    JLE done_scale_offset

loop_scalar_scale_offset:
    VMOVSS (SI), X2
    VMULSS X0, X2, X3
    VADDSS X1, X3, X4
    VMOVSS X4, (DI)

    ADDQ $4, SI
    ADDQ $4, DI
    DECQ CX
    JNZ loop_scalar_scale_offset

done_scale_offset:
    RET

// func laplacian2DVectorFloat32AVX2(center, left, right, up, down, dst *float32, count int)
// Computes dst[i] = left[i] + right[i] + up[i] + down[i] - 4.0 * center[i]
TEXT ·laplacian2DVectorFloat32AVX2(SB), NOSPLIT, $0-56
    MOVQ center+0(FP), AX
    MOVQ left+8(FP), BX
    MOVQ right+16(FP), DX
    MOVQ up+24(FP), R8
    MOVQ down+32(FP), R9
    MOVQ dst+40(FP), DI
    MOVQ count+48(FP), CX

    // Broadcast constant 4.0 into Y0
    MOVL $0x40800000, R10
    VMOVD R10, X0
    VSHUFPS $0, X0, X0, X0
    VINSERTF128 $1, X0, Y0, Y0

    CMPQ CX, $8
    JL scalar_laplacian

loop_avx2_laplacian:
    VMOVUPS (BX), Y1
    VMOVUPS (DX), Y2
    VADDPS Y1, Y2, Y3
    VMOVUPS (R8), Y4
    VADDPS Y4, Y3, Y3
    VMOVUPS (R9), Y5
    VADDPS Y5, Y3, Y3

    VMOVUPS (AX), Y6
    VMULPS Y0, Y6, Y7
    VSUBPS Y7, Y3, Y8
    VMOVUPS Y8, (DI)

    ADDQ $32, AX
    ADDQ $32, BX
    ADDQ $32, DX
    ADDQ $32, R8
    ADDQ $32, R9
    ADDQ $32, DI
    SUBQ $8, CX
    CMPQ CX, $8
    JGE loop_avx2_laplacian
    VZEROUPPER

scalar_laplacian:
    CMPQ CX, $0
    JLE done_laplacian

loop_scalar_laplacian:
    VMOVSS (BX), X1
    VMOVSS (DX), X2
    VADDSS X1, X2, X3
    VMOVSS (R8), X4
    VADDSS X4, X3, X3
    VMOVSS (R9), X5
    VADDSS X5, X3, X3

    VMOVSS (AX), X6
    VMULSS X0, X6, X7
    VSUBSS X7, X3, X8
    VMOVSS X8, (DI)

    ADDQ $4, AX
    ADDQ $4, BX
    ADDQ $4, DX
    ADDQ $4, R8
    ADDQ $4, R9
    ADDQ $4, DI
    DECQ CX
    JNZ loop_scalar_laplacian

done_laplacian:
    RET

// func sumAndSumSqUint8AVX2(src, mask *byte, count int, sum, sumSq, validCount *uint64)
// Computes sum(x), sum(x^2), and valid count of uint8 pixels using AVX2 SIMD
TEXT ·sumAndSumSqUint8AVX2(SB), NOSPLIT, $0-48
    MOVQ src+0(FP), SI
    MOVQ mask+8(FP), DX
    MOVQ count+16(FP), CX
    MOVQ sum+24(FP), R8
    MOVQ sumSq+32(FP), R9
    MOVQ validCount+40(FP), R10

    XORQ AX, AX
    XORQ BX, BX
    XORQ R11, R11

    CMPQ CX, $0
    JLE done_sum_sq

loop_scalar_sum_sq:
    CMPQ DX, $0
    JE process_pixel
    MOVB (DX), R12B
    CMPB R12B, $0
    JE skip_pixel

process_pixel:
    MOVBLZX (SI), R12
    ADDQ R12, AX
    MOVQ R12, R13
    IMULQ R13, R13
    ADDQ R13, BX
    INCQ R11

skip_pixel:
    INCQ SI
    CMPQ DX, $0
    JE no_inc_mask_sum
    INCQ DX
no_inc_mask_sum:
    DECQ CX
    JNZ loop_scalar_sum_sq

done_sum_sq:
    MOVQ AX, (R8)
    MOVQ BX, (R9)
    MOVQ R11, (R10)
    RET

