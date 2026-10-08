using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace Ignite.Desktop.Services
{
    public static class Mesh3DExportService
    {
        public struct Vertex3D
        {
            public float X, Y, Z;
            public float Nx, Ny, Nz;
            public byte R, G, B;
        }

        public struct Face3D
        {
            public int V1, V2, V3;
        }

        public class MeshData
        {
            public List<Vertex3D> Vertices { get; set; } = new();
            public List<Face3D> Faces { get; set; } = new();
        }

        /// <summary>
        /// Generates a triangulated 3D mesh from a depth map (mm) and thermal byte matrix.
        /// </summary>
        public static MeshData BuildMesh(
            byte[]? depthBytes,
            byte[]? thermalBytes,
            byte[]? maskBytes,
            int width,
            int height,
            double maxDepthMm = 35.0,
            double pixelPitchMm = 0.6,
            int step = 2)
        {
            if (step < 1) step = 1;
            var mesh = new MeshData();
            int[] gridIdx = new int[width * height];
            Array.Fill(gridIdx, -1);

            // 1. Generate Vertices
            for (int y = 0; y < height; y += step)
            {
                int rowOff = y * width;
                for (int x = 0; x < width; x += step)
                {
                    int idx = rowOff + x;
                    if (maskBytes != null && idx < maskBytes.Length && maskBytes[idx] == 0)
                        continue;

                    double normZ = depthBytes != null && idx < depthBytes.Length ? depthBytes[idx] / 255.0 : 0.0;
                    float z = (float)(normZ * maxDepthMm);

                    float xMm = (float)((x - width / 2.0) * pixelPitchMm);
                    float yMm = (float)((height / 2.0 - y) * pixelPitchMm);

                    // Compute finite differences for normal
                    float zL = (x > 0 && depthBytes != null) ? (float)(depthBytes[idx - 1] / 255.0 * maxDepthMm) : z;
                    float zR = (x < width - 1 && depthBytes != null) ? (float)(depthBytes[idx + 1] / 255.0 * maxDepthMm) : z;
                    float zU = (y > 0 && depthBytes != null) ? (float)(depthBytes[idx - width] / 255.0 * maxDepthMm) : z;
                    float zD = (y < height - 1 && depthBytes != null) ? (float)(depthBytes[idx + width] / 255.0 * maxDepthMm) : z;

                    double dzdx = (zR - zL) / (2.0 * pixelPitchMm);
                    double dzdy = (zD - zU) / (2.0 * pixelPitchMm);
                    double lenN = Math.Sqrt(dzdx * dzdx + dzdy * dzdy + 1.0);
                    float nx = (float)(-dzdx / lenN);
                    float ny = (float)(dzdy / lenN);
                    float nz = (float)(1.0 / lenN);

                    byte rawT = (thermalBytes != null && idx < thermalBytes.Length) ? thermalBytes[idx] : (byte)128;
                    var (r, g, b) = ColorizeRaw(rawT);

                    int vIdx = mesh.Vertices.Count;
                    gridIdx[idx] = vIdx;
                    mesh.Vertices.Add(new Vertex3D
                    {
                        X = xMm,
                        Y = yMm,
                        Z = z,
                        Nx = nx,
                        Ny = ny,
                        Nz = nz,
                        R = r,
                        G = g,
                        B = b
                    });
                }
            }

            // 2. Triangulate Quads
            for (int y = 0; y < height - step; y += step)
            {
                for (int x = 0; x < width - step; x += step)
                {
                    int iTL = y * width + x;
                    int iTR = y * width + (x + step);
                    int iBL = (y + step) * width + x;
                    int iBR = (y + step) * width + (x + step);

                    int vTL = gridIdx[iTL];
                    int vTR = gridIdx[iTR];
                    int vBL = gridIdx[iBL];
                    int vBR = gridIdx[iBR];

                    if (vTL >= 0 && vBL >= 0 && vTR >= 0)
                    {
                        mesh.Faces.Add(new Face3D { V1 = vTL, V2 = vBL, V3 = vTR });
                    }
                    if (vTR >= 0 && vBL >= 0 && vBR >= 0)
                    {
                        mesh.Faces.Add(new Face3D { V1 = vTR, V2 = vBL, V3 = vBR });
                    }
                }
            }

            return mesh;
        }

        public static (byte R, byte G, byte B) ColorizeRaw(byte raw)
        {
            double u = raw / 255.0;
            double r, g, b;
            if (u < 0.25)
            {
                double t = u / 0.25;
                r = 0.0;
                g = 0.0;
                b = 0.2 + 0.8 * t;
            }
            else if (u < 0.5)
            {
                double t = (u - 0.25) / 0.25;
                r = 0.7 * t;
                g = 0.1 * t;
                b = 1.0 - 0.2 * t;
            }
            else if (u < 0.75)
            {
                double t = (u - 0.5) / 0.25;
                r = 0.7 + 0.3 * t;
                g = 0.1 + 0.7 * t;
                b = 0.8 * (1.0 - t);
            }
            else
            {
                double t = (u - 0.75) / 0.25;
                r = 1.0;
                g = 0.8 + 0.2 * t;
                b = 0.5 * t;
            }
            return (
                (byte)Math.Clamp((int)Math.Round(r * 255.0), 0, 255),
                (byte)Math.Clamp((int)Math.Round(g * 255.0), 0, 255),
                (byte)Math.Clamp((int)Math.Round(b * 255.0), 0, 255)
            );
        }

        public static void ExportObj(string filePath, MeshData mesh, string patientId = "123456789")
        {
            var inv = CultureInfo.InvariantCulture;
            using var sw = new StreamWriter(filePath, false, Encoding.UTF8);

            sw.WriteLine("# IGNITE PACS Medical Workstation - 3D Wavefront Mesh");
            sw.WriteLine($"# Patient ID: {patientId} - Generated: {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
            sw.WriteLine($"# Vertices: {mesh.Vertices.Count}, Faces: {mesh.Faces.Count}");

            foreach (var v in mesh.Vertices)
            {
                float rf = v.R / 255.0f;
                float gf = v.G / 255.0f;
                float bf = v.B / 255.0f;
                sw.WriteLine(string.Format(inv, "v {0:F3} {1:F3} {2:F3} {3:F4} {4:F4} {5:F4}", v.X, v.Y, v.Z, rf, gf, bf));
            }

            foreach (var v in mesh.Vertices)
            {
                sw.WriteLine(string.Format(inv, "vn {0:F4} {1:F4} {2:F4}", v.Nx, v.Ny, v.Nz));
            }

            foreach (var f in mesh.Faces)
            {
                int v1 = f.V1 + 1;
                int v2 = f.V2 + 1;
                int v3 = f.V3 + 1;
                sw.WriteLine($"f {v1}//{v1} {v2}//{v2} {v3}//{v3}");
            }
        }

        public static void ExportPly(string filePath, MeshData mesh, string patientId = "123456789")
        {
            var inv = CultureInfo.InvariantCulture;
            using var sw = new StreamWriter(filePath, false, Encoding.UTF8);

            sw.WriteLine("ply");
            sw.WriteLine("format ascii 1.0");
            sw.WriteLine($"comment IGNITE PACS Patient {patientId} Thermographic Mesh");
            sw.WriteLine($"element vertex {mesh.Vertices.Count}");
            sw.WriteLine("property float x");
            sw.WriteLine("property float y");
            sw.WriteLine("property float z");
            sw.WriteLine("property float nx");
            sw.WriteLine("property float ny");
            sw.WriteLine("property float nz");
            sw.WriteLine("property uchar red");
            sw.WriteLine("property uchar green");
            sw.WriteLine("property uchar blue");
            sw.WriteLine($"element face {mesh.Faces.Count}");
            sw.WriteLine("property list uchar int vertex_indices");
            sw.WriteLine("end_header");

            foreach (var v in mesh.Vertices)
            {
                sw.WriteLine(string.Format(inv, "{0:F3} {1:F3} {2:F3} {3:F4} {4:F4} {5:F4} {6} {7} {8}",
                    v.X, v.Y, v.Z, v.Nx, v.Ny, v.Nz, v.R, v.G, v.B));
            }

            foreach (var f in mesh.Faces)
            {
                sw.WriteLine($"3 {f.V1} {f.V2} {f.V3}");
            }
        }

        public static void ExportStl(string filePath, MeshData mesh)
        {
            using var fs = new FileStream(filePath, FileMode.Create, FileAccess.Write);
            using var bw = new BinaryWriter(fs);

            // 80-byte header
            byte[] header = new byte[80];
            byte[] title = Encoding.ASCII.GetBytes("IGNITE PACS 3D Reconstruction - Jugend forscht 2026");
            Array.Copy(title, header, Math.Min(title.Length, 80));
            bw.Write(header);

            // Triangle count
            bw.Write((uint)mesh.Faces.Count);

            foreach (var f in mesh.Faces)
            {
                var v1 = mesh.Vertices[f.V1];
                var v2 = mesh.Vertices[f.V2];
                var v3 = mesh.Vertices[f.V3];

                // Compute normal
                float ax = v2.X - v1.X;
                float ay = v2.Y - v1.Y;
                float az = v2.Z - v1.Z;
                float bx = v3.X - v1.X;
                float by = v3.Y - v1.Y;
                float bz = v3.Z - v1.Z;

                float nx = ay * bz - az * by;
                float ny = az * bx - ax * bz;
                float nz = ax * by - ay * bx;
                float len = (float)Math.Sqrt(nx * nx + ny * ny + nz * nz);
                if (len > 1e-6f)
                {
                    nx /= len;
                    ny /= len;
                    nz /= len;
                }
                else
                {
                    nx = 0; ny = 0; nz = 1;
                }

                // Normal (3 floats)
                bw.Write(nx);
                bw.Write(ny);
                bw.Write(nz);

                // V1 (3 floats)
                bw.Write(v1.X);
                bw.Write(v1.Y);
                bw.Write(v1.Z);

                // V2 (3 floats)
                bw.Write(v2.X);
                bw.Write(v2.Y);
                bw.Write(v2.Z);

                // V3 (3 floats)
                bw.Write(v3.X);
                bw.Write(v3.Y);
                bw.Write(v3.Z);

                // Attribute byte count (2 bytes)
                bw.Write((ushort)0);
            }
        }

        public static void ExportXyzPointCloud(string filePath, MeshData mesh, double minT = 20.0, double maxT = 42.0)
        {
            var inv = CultureInfo.InvariantCulture;
            using var sw = new StreamWriter(filePath, false, Encoding.UTF8);

            sw.WriteLine("# X_mm\tY_mm\tZ_mm\tTemp_C\tNx\tNy\tNz\tR\tG\tB");
            foreach (var v in mesh.Vertices)
            {
                // Reconstruct temp from color approximation
                double tempC = minT + (v.R / 255.0) * (maxT - minT);
                sw.WriteLine(string.Format(inv, "{0:F3}\t{1:F3}\t{2:F3}\t{3:F2}\t{4:F4}\t{5:F4}\t{6:F4}\t{7}\t{8}\t{9}",
                    v.X, v.Y, v.Z, tempC, v.Nx, v.Ny, v.Nz, v.R, v.G, v.B));
            }
        }

        public static void ExportDepthMatrixCsv(string filePath, byte[]? depthBytes, int width, int height, double maxDepthMm = 35.0)
        {
            var inv = CultureInfo.InvariantCulture;
            using var sw = new StreamWriter(filePath, false, Encoding.UTF8);

            sw.WriteLine($"# IGNITE PACS - 3D Tiefenprofil Matrix in Millimeter (Breite: {width}, Hoehe: {height}, Z_max: {maxDepthMm} mm)");
            for (int y = 0; y < height; y++)
            {
                int rowOff = y * width;
                var sb = new StringBuilder();
                for (int x = 0; x < width; x++)
                {
                    int idx = rowOff + x;
                    double zMm = (depthBytes != null && idx < depthBytes.Length)
                        ? (depthBytes[idx] / 255.0 * maxDepthMm)
                        : 0.0;
                    sb.Append(string.Format(inv, "{0:F2}", zMm));
                    if (x < width - 1) sb.Append(";");
                }
                sw.WriteLine(sb.ToString());
            }
        }
    }
}
