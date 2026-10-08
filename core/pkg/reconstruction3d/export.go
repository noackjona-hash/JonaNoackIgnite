package reconstruction3d

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"math"
	"os"

	"ignite-core/pkg/imageutil"
)

// Vertex3D represents a point in 3D Euclidean space with normal and color.
type Vertex3D struct {
	X, Y, Z    float32
	Nx, Ny, Nz float32
	R, G, B    uint8
}

// Face3D represents a triangular element with 3 zero-based vertex indices.
type Face3D struct {
	V1, V2, V3 int
}

// TriangleMesh3D encapsulates a fully triangulated anatomical surface.
type TriangleMesh3D struct {
	Vertices []Vertex3D
	Faces    []Face3D
}

// GenerateMesh constructs a watertight or open triangulated mesh from heightfield and body mask.
// Step defines decimation (e.g., 1 for full resolution, 2 for half resolution).
func GenerateMesh(depthMap *imageutil.FloatMatrix, src *imageutil.GrayMatrix, bodyMask *imageutil.GrayMatrix, pitchMm float64, step int) *TriangleMesh3D {
	if step < 1 {
		step = 1
	}
	w, h := depthMap.Width, depthMap.Height

	// Map 2D pixel grid to 1D vertex index (-1 if background or skipped)
	gridIdx := make([]int, w*h)
	for i := range gridIdx {
		gridIdx[i] = -1
	}

	mesh := &TriangleMesh3D{
		Vertices: make([]Vertex3D, 0, (w/step)*(h/step)),
		Faces:    make([]Face3D, 0, (w/step)*(h/step)*2),
	}

	// 1. Create Vertices
	for y := 0; y < h; y += step {
		rowOff := y * w
		for x := 0; x < w; x += step {
			idx := rowOff + x
			if bodyMask != nil && bodyMask.Data[idx] == 0 {
				continue
			}

			z := depthMap.Data[idx]
			// Real world coordinates in mm, centered at origin
			xMm := float32(float64(x-w/2) * pitchMm)
			yMm := float32(float64(h/2-y) * pitchMm) // invert Y for standard 3D upright coordinates

			// Compute normal
			var zLeft, zRight, zUp, zDown float32
			if x > 0 {
				zLeft = depthMap.Data[idx-1]
			} else {
				zLeft = z
			}
			if x < w-1 {
				zRight = depthMap.Data[idx+1]
			} else {
				zRight = z
			}
			if y > 0 {
				zUp = depthMap.Data[idx-w]
			} else {
				zUp = z
			}
			if y < h-1 {
				zDown = depthMap.Data[idx+w]
			} else {
				zDown = z
			}

			dzdx := float64(zRight-zLeft) / (2.0 * pitchMm)
			dzdy := float64(zDown-zUp) / (2.0 * pitchMm)
			lenN := math.Sqrt(dzdx*dzdx + dzdy*dzdy + 1.0)
			nx := float32(-dzdx / lenN)
			ny := float32(dzdy / lenN) // invert Y for normal
			nz := float32(1.0 / lenN)

			// Heatmap coloring (Ironbow RGB approximation)
			rawVal := uint8(0)
			if src != nil {
				rawVal = src.Data[idx]
			}
			r, g, b := RawToIronbowRGB(rawVal)

			vIdx := len(mesh.Vertices)
			gridIdx[idx] = vIdx
			mesh.Vertices = append(mesh.Vertices, Vertex3D{
				X:  xMm,
				Y:  yMm,
				Z:  z,
				Nx: nx,
				Ny: ny,
				Nz: nz,
				R:  r,
				G:  g,
				B:  b,
			})
		}
	}

	// 2. Triangulate quads between grid vertices
	for y := 0; y < h-step; y += step {
		for x := 0; x < w-step; x += step {
			iTL := y*w + x
			iTR := y*w + (x + step)
			iBL := (y+step)*w + x
			iBR := (y+step)*w + (x + step)

			vTL := gridIdx[iTL]
			vTR := gridIdx[iTR]
			vBL := gridIdx[iBL]
			vBR := gridIdx[iBR]

			// Triangle 1: Top-Left, Bottom-Left, Top-Right
			if vTL >= 0 && vBL >= 0 && vTR >= 0 {
				mesh.Faces = append(mesh.Faces, Face3D{V1: vTL, V2: vBL, V3: vTR})
			}
			// Triangle 2: Top-Right, Bottom-Left, Bottom-Right
			if vTR >= 0 && vBL >= 0 && vBR >= 0 {
				mesh.Faces = append(mesh.Faces, Face3D{V1: vTR, V2: vBL, V3: vBR})
			}
		}
	}

	return mesh
}

// RawToIronbowRGB converts raw thermal byte [0, 255] to RGB colors according to Ironbow colormap.
func RawToIronbowRGB(val uint8) (uint8, uint8, uint8) {
	u := float64(val) / 255.0
	var r, g, b float64
	if u < 0.25 {
		t := u / 0.25
		r = 0.0
		g = 0.0
		b = 0.2 + 0.8*t
	} else if u < 0.5 {
		t := (u - 0.25) / 0.25
		r = 0.7 * t
		g = 0.1 * t
		b = 1.0 - 0.2*t
	} else if u < 0.75 {
		t := (u - 0.5) / 0.25
		r = 0.7 + 0.3*t
		g = 0.1 + 0.7*t
		b = 0.8 * (1.0 - t)
	} else {
		t := (u - 0.75) / 0.25
		r = 1.0
		g = 0.8 + 0.2*t
		b = 0.5 * t
	}

	return uint8(math.Min(255, math.Max(0, r*255.0))),
		uint8(math.Min(255, math.Max(0, g*255.0))),
		uint8(math.Min(255, math.Max(0, b*255.0)))
}

// ExportOBJ writes Wavefront OBJ file with per-vertex positions, normals, and colors.
func (m *TriangleMesh3D) ExportOBJ(filePath string) error {
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Errorf("failed to create OBJ file: %w", err)
	}
	defer file.Close()

	w := bufio.NewWriter(file)
	defer w.Flush()

	fmt.Fprintf(w, "# IGNITE PACS Medical Workstation - 3D Surface Reconstruction\n")
	fmt.Fprintf(w, "# Vertices: %d, Faces: %d\n", len(m.Vertices), len(m.Faces))

	// Write vertices with RGB color extensions: v X Y Z R G B
	for _, v := range m.Vertices {
		rf := float64(v.R) / 255.0
		gf := float64(v.G) / 255.0
		bf := float64(v.B) / 255.0
		fmt.Fprintf(w, "v %.3f %.3f %.3f %.4f %.4f %.4f\n", v.X, v.Y, v.Z, rf, gf, bf)
	}

	// Write vertex normals: vn Nx Ny Nz
	for _, v := range m.Vertices {
		fmt.Fprintf(w, "vn %.4f %.4f %.4f\n", v.Nx, v.Ny, v.Nz)
	}

	// Write faces: 1-indexed in OBJ: f v1//vn1 v2//vn2 v3//vn3
	for _, f := range m.Faces {
		v1 := f.V1 + 1
		v2 := f.V2 + 1
		v3 := f.V3 + 1
		fmt.Fprintf(w, "f %d//%d %d//%d %d//%d\n", v1, v1, v2, v2, v3, v3)
	}

	return nil
}

// ExportPLY writes Stanford PLY polygon mesh with per-vertex coordinates, normals, and colors.
func (m *TriangleMesh3D) ExportPLY(filePath string) error {
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Errorf("failed to create PLY file: %w", err)
	}
	defer file.Close()

	w := bufio.NewWriter(file)
	defer w.Flush()

	fmt.Fprintf(w, "ply\n")
	fmt.Fprintf(w, "format ascii 1.0\n")
	fmt.Fprintf(w, "comment IGNITE PACS Thermographic 3D Reconstruction\n")
	fmt.Fprintf(w, "element vertex %d\n", len(m.Vertices))
	fmt.Fprintf(w, "property float x\n")
	fmt.Fprintf(w, "property float y\n")
	fmt.Fprintf(w, "property float z\n")
	fmt.Fprintf(w, "property float nx\n")
	fmt.Fprintf(w, "property float ny\n")
	fmt.Fprintf(w, "property float nz\n")
	fmt.Fprintf(w, "property uchar red\n")
	fmt.Fprintf(w, "property uchar green\n")
	fmt.Fprintf(w, "property uchar blue\n")
	fmt.Fprintf(w, "element face %d\n", len(m.Faces))
	fmt.Fprintf(w, "property list uchar int vertex_indices\n")
	fmt.Fprintf(w, "end_header\n")

	for _, v := range m.Vertices {
		fmt.Fprintf(w, "%.3f %.3f %.3f %.4f %.4f %.4f %d %d %d\n",
			v.X, v.Y, v.Z, v.Nx, v.Ny, v.Nz, v.R, v.G, v.B)
	}

	for _, f := range m.Faces {
		fmt.Fprintf(w, "3 %d %d %d\n", f.V1, f.V2, f.V3)
	}

	return nil
}

// ExportSTL writes binary STL file for 3D printing and podiatric milling.
func (m *TriangleMesh3D) ExportSTL(filePath string) error {
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Errorf("failed to create STL file: %w", err)
	}
	defer file.Close()

	w := bufio.NewWriter(file)
	defer w.Flush()

	// 80-byte header
	header := make([]byte, 80)
	copy(header, []byte("IGNITE PACS 3D Medical Model - Jugend forscht 2026"))
	if _, err := w.Write(header); err != nil {
		return err
	}

	// 4-byte face count (uint32 Little Endian)
	triangleCount := uint32(len(m.Faces))
	if err := binary.Write(w, binary.LittleEndian, triangleCount); err != nil {
		return err
	}

	// 50 bytes per facet:
	// Normal: 3 x float32 (12 bytes)
	// V1: 3 x float32 (12 bytes)
	// V2: 3 x float32 (12 bytes)
	// V3: 3 x float32 (12 bytes)
	// Attribute byte count: uint16 (2 bytes) = 0
	buf := make([]byte, 50)
	for _, f := range m.Faces {
		v1 := m.Vertices[f.V1]
		v2 := m.Vertices[f.V2]
		v3 := m.Vertices[f.V3]

		// Face normal: (v2 - v1) x (v3 - v1)
		ax := v2.X - v1.X
		ay := v2.Y - v1.Y
		az := v2.Z - v1.Z
		bx := v3.X - v1.X
		by := v3.Y - v1.Y
		bz := v3.Z - v1.Z

		nx := ay*bz - az*by
		ny := az*bx - ax*bz
		nz := ax*by - ay*bx
		lenNorm := float32(math.Sqrt(float64(nx*nx + ny*ny + nz*nz)))
		if lenNorm > 1e-6 {
			nx /= lenNorm
			ny /= lenNorm
			nz /= lenNorm
		} else {
			nx, ny, nz = 0, 0, 1
		}

		binary.LittleEndian.PutUint32(buf[0:4], math.Float32bits(nx))
		binary.LittleEndian.PutUint32(buf[4:8], math.Float32bits(ny))
		binary.LittleEndian.PutUint32(buf[8:12], math.Float32bits(nz))

		binary.LittleEndian.PutUint32(buf[12:16], math.Float32bits(v1.X))
		binary.LittleEndian.PutUint32(buf[16:20], math.Float32bits(v1.Y))
		binary.LittleEndian.PutUint32(buf[20:24], math.Float32bits(v1.Z))

		binary.LittleEndian.PutUint32(buf[24:28], math.Float32bits(v2.X))
		binary.LittleEndian.PutUint32(buf[28:32], math.Float32bits(v2.Y))
		binary.LittleEndian.PutUint32(buf[32:36], math.Float32bits(v2.Z))

		binary.LittleEndian.PutUint32(buf[36:40], math.Float32bits(v3.X))
		binary.LittleEndian.PutUint32(buf[40:44], math.Float32bits(v3.Y))
		binary.LittleEndian.PutUint32(buf[44:48], math.Float32bits(v3.Z))

		binary.LittleEndian.PutUint16(buf[48:50], 0)

		if _, err := w.Write(buf); err != nil {
			return err
		}
	}

	return nil
}

// ExportXYZ writes tab-separated XYZ point cloud with calibrated temperature values.
func (m *TriangleMesh3D) ExportXYZ(filePath string) error {
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Errorf("failed to create XYZ file: %w", err)
	}
	defer file.Close()

	w := bufio.NewWriter(file)
	defer w.Flush()

	fmt.Fprintf(w, "# X_mm\tY_mm\tZ_mm\tNx\tNy\tNz\tR\tG\tB\n")
	for _, v := range m.Vertices {
		fmt.Fprintf(w, "%.3f\t%.3f\t%.3f\t%.4f\t%.4f\t%.4f\t%d\t%d\t%d\n",
			v.X, v.Y, v.Z, v.Nx, v.Ny, v.Nz, v.R, v.G, v.B)
	}
	return nil
}
