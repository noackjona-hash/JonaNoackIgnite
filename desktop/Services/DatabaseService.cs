using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Data.Sqlite;

namespace Ignite.Desktop.Services
{
    public class AuditEntry
    {
        public int Id { get; set; }
        public DateTime Timestamp { get; set; }
        public string Action { get; set; } = string.Empty;
        public string OperatorId { get; set; } = string.Empty;
        public string Details { get; set; } = string.Empty;
    }

    public class EvaluationRecord
    {
        public int Id { get; set; }
        public string SessionId { get; set; } = string.Empty;
        public string PatientHash { get; set; } = string.Empty;
        public string ImagePath { get; set; } = string.Empty;
        public string Mode { get; set; } = string.Empty;
        public int HotspotCount { get; set; }
        public double MaxDeltaT { get; set; }
        public string HighestRisk { get; set; } = string.Empty;
        public double ExecutionTimeMs { get; set; }
        public DateTime Timestamp { get; set; }
    }

    public class DatabaseService
    {
        private readonly string _connectionString;

        public DatabaseService(string dbPath = "ignite_medical.db")
        {
            _connectionString = $"Data Source={dbPath}";
            InitializeDatabase();
        }

        private void InitializeDatabase()
        {
            using var conn = new SqliteConnection(_connectionString);
            conn.Open();

            string initSql = @"
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS patients (
                    patient_id TEXT PRIMARY KEY,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
                    examiner TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    study_type TEXT DEFAULT 'PODIATRIC_SCREENING'
                );

                CREATE TABLE IF NOT EXISTS evaluations (
                    eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    image_path TEXT NOT NULL,
                    image_hash TEXT NOT NULL,
                    analysis_mode TEXT NOT NULL,
                    threshold_mode TEXT NOT NULL,
                    k_factor REAL NOT NULL,
                    hotspot_count INTEGER NOT NULL,
                    max_delta_t REAL,
                    highest_risk TEXT NOT NULL,
                    execution_time_ms REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    action TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    details TEXT,
                    tamper_checksum TEXT
                );
            ";

            using var cmd = new SqliteCommand(initSql, conn);
            cmd.ExecuteNonQuery();
        }

        public string EnsurePatient(string rawIdentifier)
        {
            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(rawIdentifier + "_IGNITE_SALT_2026"));
            string anonId = "ANON-" + BitConverter.ToString(hash).Replace("-", "").Substring(0, 8);

            using var conn = new SqliteConnection(_connectionString);
            conn.Open();

            string insert = "INSERT OR IGNORE INTO patients (patient_id, notes) VALUES (@id, 'Pseudonymisiert nach DSGVO Art. 4 Abs. 5')";
            using var cmd = new SqliteCommand(insert, conn);
            cmd.Parameters.AddWithValue("@id", anonId);
            cmd.ExecuteNonQuery();

            return anonId;
        }

        public void LogEvaluation(string patientId, string imagePath, string mode, int hotspotCount, double maxDeltaT, string highestRisk, double execMs)
        {
            string sessionId = "SESS-" + Guid.NewGuid().ToString("N").Substring(0, 8);
            using var conn = new SqliteConnection(_connectionString);
            conn.Open();

            // Insert session
            using (var cmdSess = new SqliteCommand("INSERT INTO sessions (session_id, patient_id, examiner) VALUES (@sid, @pid, @examiner)", conn))
            {
                cmdSess.Parameters.AddWithValue("@sid", sessionId);
                cmdSess.Parameters.AddWithValue("@pid", patientId);
                cmdSess.Parameters.AddWithValue("@examiner", Environment.UserName);
                cmdSess.ExecuteNonQuery();
            }

            // Insert eval
            using (var cmdEval = new SqliteCommand(@"
                INSERT INTO evaluations (session_id, image_path, image_hash, analysis_mode, threshold_mode, k_factor, hotspot_count, max_delta_t, highest_risk, execution_time_ms)
                VALUES (@sid, @path, @hash, @mode, 'MAD', 2.5, @cnt, @delta, @risk, @exec)", conn))
            {
                cmdEval.Parameters.AddWithValue("@sid", sessionId);
                cmdEval.Parameters.AddWithValue("@path", imagePath);
                cmdEval.Parameters.AddWithValue("@hash", Path.GetFileName(imagePath));
                cmdEval.Parameters.AddWithValue("@mode", mode);
                cmdEval.Parameters.AddWithValue("@cnt", hotspotCount);
                cmdEval.Parameters.AddWithValue("@delta", maxDeltaT);
                cmdEval.Parameters.AddWithValue("@risk", highestRisk);
                cmdEval.Parameters.AddWithValue("@exec", execMs);
                cmdEval.ExecuteNonQuery();
            }

            // Log audit entry
            LogAuditAction("ANALYZE_IMAGE", $"Scan analysiert ({mode}): {hotspotCount} Herde gefunden, Risiko={highestRisk}");
        }

        public void LogAuditAction(string action, string details)
        {
            using var conn = new SqliteConnection(_connectionString);
            conn.Open();

            using var cmd = new SqliteCommand("INSERT INTO audit_log (action, operator_id, details) VALUES (@act, @op, @det)", conn);
            cmd.Parameters.AddWithValue("@act", action);
            cmd.Parameters.AddWithValue("@op", Environment.UserName);
            cmd.Parameters.AddWithValue("@det", details);
            cmd.ExecuteNonQuery();
        }

        public List<EvaluationRecord> GetRecentEvaluations()
        {
            var list = new List<EvaluationRecord>();
            using var conn = new SqliteConnection(_connectionString);
            conn.Open();

            string sql = @"
                SELECT e.eval_id, e.session_id, s.patient_id, e.image_path, e.analysis_mode, e.hotspot_count, e.max_delta_t, e.highest_risk, e.execution_time_ms, e.timestamp
                FROM evaluations e
                JOIN sessions s ON e.session_id = s.session_id
                ORDER BY e.timestamp DESC LIMIT 50";

            using var cmd = new SqliteCommand(sql, conn);
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                list.Add(new EvaluationRecord
                {
                    Id = reader.GetInt32(0),
                    SessionId = reader.GetString(1),
                    PatientHash = reader.GetString(2),
                    ImagePath = reader.GetString(3),
                    Mode = reader.GetString(4),
                    HotspotCount = reader.GetInt32(5),
                    MaxDeltaT = reader.IsDBNull(6) ? 0.0 : reader.GetDouble(6),
                    HighestRisk = reader.GetString(7),
                    ExecutionTimeMs = reader.GetDouble(8),
                    Timestamp = reader.GetDateTime(9)
                });
            }
            return list;
        }
    }
}
