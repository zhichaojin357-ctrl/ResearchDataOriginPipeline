// This bridge deliberately contains no reimplementation of an Agilent
// algorithm. It loads the matching OpenLab runtime from the directory
// containing the compiled executable. The maintained Python caller can
// materialize the project's hash-verified runtime bundle into that directory.
//
// The formal Python caller is responsible for providing an isolated copy of a
// result set as <work-area>.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.ServiceModel;
using System.Text;
using Agilent.Acaml21.Utilities;
using Agilent.Chromatography.DataAnalysis.Services;

internal static class OpenLabVendorBridge
{
    private const int ExitSuccess = 0;
    private const int ExitJobFailure = 1;
    private const int ExitUsage = 64;
    private const int ExitConfigurationFailure = 65;
    private const int ExitUnexpectedFailure = 70;

    private sealed class JobResult
    {
        internal int LineNumber;
        internal string AcamlRelative = string.Empty;
        internal string InjectionGuid = string.Empty;
        internal string RawDxRelative = string.Empty;
        internal string AcamlPath = string.Empty;
        internal string RawDxPath = string.Empty;
        internal string RxPath = string.Empty;
        internal bool AcamlChecksumValid;
        internal bool AcamlChecksumRebuilt;
        internal int? InjectionCount;
        internal bool RxExists;
        internal bool CanProcess;
        internal bool Processed;
        internal readonly List<string> LoadErrors = new List<string>();
        internal readonly List<string> Warnings = new List<string>();
        internal readonly List<string> Failures = new List<string>();

        internal bool Succeeded
        {
            get
            {
                return Processed
                    && LoadErrors.Count == 0
                    && Failures.Count == 0
                    && RxExists;
            }
        }

        internal string Status
        {
            get { return Succeeded ? "succeeded" : "failed"; }
        }
    }

    private sealed class BridgeReport
    {
        internal string WorkAreaRelative = ".";
        internal string MethodRelative = string.Empty;
        internal string JobsRelative = string.Empty;
        internal string ReportRelative = string.Empty;
        internal readonly List<string> GlobalErrors = new List<string>();
        internal readonly List<JobResult> Jobs = new List<JobResult>();

        internal bool Succeeded
        {
            get
            {
                return GlobalErrors.Count == 0 && Jobs.Count > 0 && Jobs.All(job => job.Succeeded);
            }
        }
    }

    private static int Main(string[] args)
    {
        if (args == null || args.Length != 4)
        {
            Console.Error.WriteLine(
                "Usage: OpenLabVendorBridge.exe <work-area> <method-relative> <jobs.tsv> <report-json>");
            return ExitUsage;
        }

        string workArea = null;
        string reportPath = null;
        bool enteredProcessingStage = false;
        var report = new BridgeReport();
        try
        {
            workArea = ValidateWorkArea(args[0]);
            report.WorkAreaRelative = ".";
            report.MethodRelative = ValidateRelativeText(args[1], "method-relative");
            report.JobsRelative = ValidateRelativeText(args[2], "jobs.tsv");
            report.ReportRelative = ValidateRelativeText(args[3], "report-json");

            string methodPath = ResolveInsideWorkArea(workArea, report.MethodRelative, "method-relative");
            string jobsPath = ResolveInsideWorkArea(workArea, report.JobsRelative, "jobs.tsv");
            reportPath = ResolveInsideWorkArea(workArea, report.ReportRelative, "report-json");

            if (!string.Equals(Path.GetExtension(jobsPath), ".tsv", StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("jobs.tsv must name a .tsv file.");
            }
            if (!string.Equals(Path.GetExtension(reportPath), ".json", StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("report-json must name a .json file.");
            }
            if (!string.Equals(Path.GetExtension(methodPath), ".pmx", StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("method-relative must name a .pmx processing method.");
            }
            if (!File.Exists(methodPath))
            {
                throw new FileNotFoundException("The processing method does not exist inside work-area.", methodPath);
            }
            if (!File.Exists(jobsPath))
            {
                throw new FileNotFoundException("The jobs TSV does not exist inside work-area.", jobsPath);
            }
            if (File.Exists(reportPath))
            {
                throw new IOException("Refusing to overwrite an existing report-json file.");
            }

            LoadJobs(jobsPath, workArea, report);
            if (report.Jobs.Count == 0)
            {
                report.GlobalErrors.Add("jobs.tsv did not contain any jobs.");
            }

            string processingServerPath = Path.Combine(
                AppDomain.CurrentDomain.BaseDirectory,
                "Agilent.Chromatography.DataAnalysis.Processing.ProcessingServer.exe");
            if (!File.Exists(processingServerPath))
            {
                report.GlobalErrors.Add("The Agilent ProcessingServer executable is missing beside this bridge executable.");
            }

            if (report.GlobalErrors.Count == 0 && report.Jobs.Any(job => job.CanProcess))
            {
                enteredProcessingStage = true;
                ProcessJobs(workArea, report.MethodRelative, processingServerPath, report);
            }

            WriteReport(reportPath, report);
            return report.Succeeded ? ExitSuccess : ExitJobFailure;
        }
        catch (Exception exception)
        {
            string message = FormatException(exception);
            Console.Error.WriteLine(message);
            report.GlobalErrors.Add(message);
            if (!string.IsNullOrEmpty(reportPath))
            {
                try
                {
                    if (!File.Exists(reportPath))
                    {
                        WriteReport(reportPath, report);
                    }
                }
                catch (Exception reportException)
                {
                    Console.Error.WriteLine("Could not write failure report: " + FormatException(reportException));
                }
            }

            return enteredProcessingStage ? ExitUnexpectedFailure : ExitConfigurationFailure;
        }
    }

    private static void LoadJobs(string jobsPath, string workArea, BridgeReport report)
    {
        string[] lines = File.ReadAllLines(jobsPath, Encoding.UTF8);
        var seenAcaml = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var seenRx = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        for (int index = 0; index < lines.Length; index++)
        {
            string line = lines[index];
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var job = new JobResult { LineNumber = index + 1 };
            report.Jobs.Add(job);
            string[] columns = line.Split(new[] { '\t' }, StringSplitOptions.None);
            if (columns.Length != 3)
            {
                job.Failures.Add("jobs.tsv row must contain exactly three TAB-separated columns.");
                continue;
            }

            job.AcamlRelative = columns[0].Trim();
            job.InjectionGuid = columns[1].Trim();
            job.RawDxRelative = columns[2].Trim();
            Guid ignoredInjectionId;
            try
            {
                job.AcamlRelative = ValidateRelativeText(job.AcamlRelative, "single_acaml_relative");
                job.RawDxRelative = ValidateRelativeText(job.RawDxRelative, "raw_dx_relative");
                if (!Guid.TryParse(job.InjectionGuid, out ignoredInjectionId))
                {
                    throw new InvalidOperationException("injection_guid is not a valid GUID.");
                }
                job.InjectionGuid = ignoredInjectionId.ToString("D");

                job.AcamlPath = ResolveInsideWorkArea(workArea, job.AcamlRelative, "single_acaml_relative");
                job.RawDxPath = ResolveInsideWorkArea(workArea, job.RawDxRelative, "raw_dx_relative");
                job.RxPath = Path.ChangeExtension(job.RawDxPath, ".rx");
                if (!string.Equals(Path.GetExtension(job.AcamlPath), ".acaml", StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException("single_acaml_relative must name an .acaml file.");
                }
                if (!string.Equals(Path.GetExtension(job.RawDxPath), ".dx", StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException("raw_dx_relative must name a .dx file.");
                }
                if (!File.Exists(job.AcamlPath))
                {
                    throw new FileNotFoundException("The single-injection ACAML file does not exist inside work-area.", job.AcamlPath);
                }
                if (!File.Exists(job.RawDxPath))
                {
                    throw new FileNotFoundException("The raw DX file does not exist inside work-area.", job.RawDxPath);
                }
                if (!seenAcaml.Add(job.AcamlPath))
                {
                    throw new InvalidOperationException("Duplicate single_acaml_relative is not allowed in one bridge run.");
                }
                if (!seenRx.Add(job.RxPath))
                {
                    throw new InvalidOperationException("Duplicate raw_dx_relative is not allowed in one bridge run.");
                }

                try
                {
                    job.AcamlChecksumValid = AcamlChecksum.VerifyFile(job.AcamlPath);
                }
                catch (Agilent.Acaml.Core.ChecksumException)
                {
                    // VerifyFile throws for some structurally edited ACAML
                    // files instead of returning false. The job file is a
                    // derived artifact inside work-area, so rebuild it below.
                    job.AcamlChecksumValid = false;
                }
                if (!job.AcamlChecksumValid)
                {
                    RebuildDerivedAcamlChecksum(job);
                }
                if (!job.AcamlChecksumValid)
                {
                    throw new InvalidOperationException("ACAML checksum verification failed after rebuilding the derived ACAML checksum.");
                }
                VerifyAcamlJobBinding(job.AcamlPath, job.InjectionGuid, Path.GetFileName(job.RawDxPath));
                job.CanProcess = true;
            }
            catch (Exception exception)
            {
                job.Failures.Add(FormatException(exception));
            }
        }
    }

    private static void ProcessJobs(
        string workArea,
        string methodRelative,
        string processingServerPath,
        BridgeReport report)
    {
        Agilent.OpenLab.CDSShared.ProcessingClients.ProcessingServer.UseLocalServices = true;
        Agilent.OpenLab.CDSShared.ProcessingClients.ProcessingServer.ServerExePath = processingServerPath;

        string previousCurrentDirectory = Environment.CurrentDirectory;
        try
        {
            // OpenLab resolves the validated relative PMX path from the
            // process working directory. Keeping it at the isolated work-area
            // prevents the PMX absolute path from becoming a nested copy.
            Environment.CurrentDirectory = workArea;
            using (var client = new DataAnalysisClient(
                new Uri("http://localhost"),
                string.Empty,
                null,
                workArea))
            {
                foreach (JobResult job in report.Jobs.Where(item => item.CanProcess))
                {
                    ProcessOneJob(client, methodRelative, job);
                }
            }
        }
        catch (FaultException<ExceptionDetail> fault)
        {
            string message = "DataAnalysisClient fault: " + fault.Message;
            report.GlobalErrors.Add(message);
            foreach (JobResult pending in report.Jobs.Where(item => item.CanProcess && !item.Processed && item.Failures.Count == 0))
            {
                pending.Failures.Add(message);
            }
        }
        catch (Exception exception)
        {
            string message = "DataAnalysisClient failure: " + FormatException(exception);
            report.GlobalErrors.Add(message);
            foreach (JobResult pending in report.Jobs.Where(item => item.CanProcess && !item.Processed && item.Failures.Count == 0))
            {
                pending.Failures.Add(message);
            }
        }
        finally
        {
            Environment.CurrentDirectory = previousCurrentDirectory;
        }
    }

    private static void ProcessOneJob(
        DataAnalysisClient client,
        string methodRelative,
        JobResult job)
    {
        try
        {
            List<InjectionParameters> injectionParameters = client.DataAccess
                // This query API requires a fully resolved ACAML path in the
                // tested OpenLab runtime. It is read-only. The processing
                // call also requires the ACAML absolute path, but receives the
                // PMX as a validated work-area-relative path to avoid OpenLab
                // creating a nested copy of its absolute source path.
                .GetInjectionParameters(job.AcamlPath)
                .ToList();
            job.InjectionCount = injectionParameters.Count;
            if (injectionParameters.Count != 1)
            {
                job.Failures.Add("DataAccess.GetInjectionParameters did not return exactly one injection.");
                return;
            }

            ProcessingLog log = client.Processing.ModifyAndReprocessSingleRun(
                job.AcamlPath,
                methodRelative,
                injectionParameters.Single());
            if (log == null)
            {
                job.Failures.Add("The vendor processing service returned no processing log.");
                return;
            }

            job.LoadErrors.AddRange(log.AllLoadErrorMessages ?? new string[0]);
            job.Warnings.AddRange(log.AllWarningMessages ?? new string[0]);
            job.Failures.AddRange(log.AllFailureMessages ?? new string[0]);
            job.RxExists = File.Exists(job.RxPath);
            if (!job.RxExists)
            {
                job.Failures.Add("The corresponding .rx file was not produced in work-area.");
            }
            job.Processed = true;
        }
        catch (FaultException<ExceptionDetail> fault)
        {
            job.Failures.Add("Vendor processing fault: " + fault.Message);
        }
        catch (Exception exception)
        {
            job.Failures.Add("Vendor processing exception: " + FormatException(exception));
        }
    }

    private static string ValidateWorkArea(string workAreaArgument)
    {
        if (string.IsNullOrWhiteSpace(workAreaArgument))
        {
            throw new InvalidOperationException("work-area is required.");
        }
        if (!Path.IsPathRooted(workAreaArgument))
        {
            throw new InvalidOperationException("work-area must be an absolute path to an isolated copy.");
        }
        string workArea = Path.GetFullPath(workAreaArgument);
        if (!Directory.Exists(workArea))
        {
            throw new DirectoryNotFoundException("work-area does not exist.");
        }
        workArea = TrimTrailingDirectorySeparator(workArea);
        if ((File.GetAttributes(workArea) & FileAttributes.ReparsePoint) != 0)
        {
            throw new InvalidOperationException("work-area must not be a reparse point.");
        }
        return workArea;
    }

    private static string ValidateRelativeText(string relativePath, string label)
    {
        if (string.IsNullOrWhiteSpace(relativePath))
        {
            throw new InvalidOperationException(label + " is required.");
        }
        if (Path.IsPathRooted(relativePath) || relativePath.IndexOf(':') >= 0)
        {
            throw new InvalidOperationException(label + " must be a relative path inside work-area.");
        }
        string[] segments = relativePath.Split(new[] { '\\', '/' }, StringSplitOptions.None);
        if (segments.Any(segment => string.Equals(segment, "..", StringComparison.Ordinal)))
        {
            throw new InvalidOperationException(label + " must not contain '..'.");
        }
        return relativePath;
    }

    private static string ResolveInsideWorkArea(string workArea, string relativePath, string label)
    {
        string fullPath = Path.GetFullPath(Path.Combine(workArea, relativePath));
        string prefix = workArea.EndsWith(Path.DirectorySeparatorChar.ToString(), StringComparison.Ordinal)
            ? workArea
            : workArea + Path.DirectorySeparatorChar;
        if (!fullPath.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(label + " resolves outside work-area.");
        }
        RejectReparsePointPath(workArea, fullPath, label);
        return fullPath;
    }

    private static void VerifyAcamlJobBinding(string acamlPath, string injectionGuid, string rawDxFileName)
    {
        string content = File.ReadAllText(acamlPath, Encoding.UTF8);
        string doubleQuoted = "InjectionId=\"" + injectionGuid + "\"";
        string singleQuoted = "InjectionId='" + injectionGuid + "'";
        if (content.IndexOf(doubleQuoted, StringComparison.OrdinalIgnoreCase) < 0
            && content.IndexOf(singleQuoted, StringComparison.OrdinalIgnoreCase) < 0)
        {
            throw new InvalidOperationException(
                "injection_guid is not the InjectionId recorded in this single-injection ACAML.");
        }
        string rawDoubleQuoted = "RawDataFileName=\"" + rawDxFileName + "\"";
        string rawSingleQuoted = "RawDataFileName='" + rawDxFileName + "'";
        if (content.IndexOf(rawDoubleQuoted, StringComparison.OrdinalIgnoreCase) < 0
            && content.IndexOf(rawSingleQuoted, StringComparison.OrdinalIgnoreCase) < 0)
        {
            throw new InvalidOperationException(
                "raw_dx_relative does not match the RawDataFileName recorded in this single-injection ACAML.");
        }
    }

    private static void RebuildDerivedAcamlChecksum(JobResult job)
    {
        // The formal caller derives a one-injection ACAML in its isolated
        // work-area. ElementTree changes invalidate the embedded checksum, so
        // repair only that job artifact; original ACAML files are never passed
        // as a bridge work-area job.
        string content = File.ReadAllText(job.AcamlPath, Encoding.UTF8);
        string rebuiltContent = AcamlChecksum.SetInString(content);
        File.WriteAllText(job.AcamlPath, rebuiltContent, new UTF8Encoding(false));
        job.AcamlChecksumRebuilt = true;
        job.AcamlChecksumValid = AcamlChecksum.VerifyFile(job.AcamlPath);
    }

    private static void RejectReparsePointPath(string workArea, string fullPath, string label)
    {
        string workAreaComparison = TrimTrailingDirectorySeparator(workArea);
        string currentPath = Directory.Exists(fullPath)
            ? fullPath
            : Path.GetDirectoryName(fullPath);
        bool reachedWorkArea = false;
        while (!string.IsNullOrEmpty(currentPath))
        {
            if ((File.GetAttributes(currentPath) & FileAttributes.ReparsePoint) != 0)
            {
                throw new InvalidOperationException(label + " traverses a reparse point, which is not allowed.");
            }
            if (string.Equals(
                TrimTrailingDirectorySeparator(currentPath),
                workAreaComparison,
                StringComparison.OrdinalIgnoreCase))
            {
                reachedWorkArea = true;
                break;
            }
            currentPath = Path.GetDirectoryName(currentPath);
        }
        if (!reachedWorkArea)
        {
            throw new InvalidOperationException(label + " could not be verified inside work-area.");
        }
        if (File.Exists(fullPath) && (File.GetAttributes(fullPath) & FileAttributes.ReparsePoint) != 0)
        {
            throw new InvalidOperationException(label + " must not be a reparse point.");
        }
    }

    private static string TrimTrailingDirectorySeparator(string path)
    {
        string root = Path.GetPathRoot(path);
        while (path.Length > root.Length && (path.EndsWith("\\", StringComparison.Ordinal) || path.EndsWith("/", StringComparison.Ordinal)))
        {
            path = path.Substring(0, path.Length - 1);
        }
        return path;
    }

    private static string FormatException(Exception exception)
    {
        if (exception == null)
        {
            return "Unknown exception.";
        }
        return exception.GetType().FullName + ": " + exception.Message;
    }

    private static void WriteReport(string reportPath, BridgeReport report)
    {
        string reportDirectory = Path.GetDirectoryName(reportPath);
        if (string.IsNullOrEmpty(reportDirectory) || !Directory.Exists(reportDirectory))
        {
            throw new DirectoryNotFoundException("The report-json parent directory does not exist inside work-area.");
        }
        if (File.Exists(reportPath))
        {
            throw new IOException("Refusing to overwrite an existing report-json file.");
        }

        string temporaryPath = reportPath + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(temporaryPath, SerializeReport(report), new UTF8Encoding(false));
            File.Move(temporaryPath, reportPath);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    private static string SerializeReport(BridgeReport report)
    {
        var builder = new StringBuilder();
        builder.Append("{\n");
        AppendProperty(builder, "bridge", "OpenLabVendorBridge", true, 1);
        AppendProperty(builder, "vendor_engine", "Agilent OpenLab DataAnalysisClient.ModifyAndReprocessSingleRun", true, 1);
        AppendProperty(builder, "work_area_relative", report.WorkAreaRelative, true, 1);
        AppendProperty(builder, "method_relative", report.MethodRelative, true, 1);
        AppendProperty(builder, "jobs_relative", report.JobsRelative, true, 1);
        AppendProperty(builder, "report_relative", report.ReportRelative, true, 1);
        AppendBooleanProperty(builder, "success", report.Succeeded, true, 1);
        AppendStringArrayProperty(builder, "global_errors", report.GlobalErrors, true, 1);
        Indent(builder, 1);
        builder.Append("\"jobs\": [\n");
        for (int i = 0; i < report.Jobs.Count; i++)
        {
            JobResult job = report.Jobs[i];
            Indent(builder, 2);
            builder.Append("{\n");
            AppendNumberProperty(builder, "line_number", job.LineNumber, true, 3);
            AppendProperty(builder, "status", job.Status, true, 3);
            AppendProperty(builder, "single_acaml_relative", job.AcamlRelative, true, 3);
            AppendProperty(builder, "injection_guid", job.InjectionGuid, true, 3);
            AppendProperty(builder, "raw_dx_relative", job.RawDxRelative, true, 3);
            AppendBooleanProperty(builder, "acaml_checksum_valid", job.AcamlChecksumValid, true, 3);
            AppendBooleanProperty(builder, "checksum_rebuilt", job.AcamlChecksumRebuilt, true, 3);
            if (job.InjectionCount.HasValue)
            {
                AppendNumberProperty(builder, "injection_count", job.InjectionCount.Value, true, 3);
            }
            else
            {
                AppendNullProperty(builder, "injection_count", true, 3);
            }
            AppendBooleanProperty(builder, "rx_exists", job.RxExists, true, 3);
            AppendStringArrayProperty(builder, "load_errors", job.LoadErrors, true, 3);
            AppendStringArrayProperty(builder, "warnings", job.Warnings, true, 3);
            AppendStringArrayProperty(builder, "failures", job.Failures, false, 3);
            Indent(builder, 2);
            builder.Append("}");
            if (i + 1 < report.Jobs.Count)
            {
                builder.Append(',');
            }
            builder.Append('\n');
        }
        Indent(builder, 1);
        builder.Append("]\n");
        builder.Append("}\n");
        return builder.ToString();
    }

    private static void AppendProperty(StringBuilder builder, string name, string value, bool comma, int indent)
    {
        Indent(builder, indent);
        builder.Append('"').Append(name).Append("\": \"").Append(EscapeJson(value)).Append('"');
        if (comma)
        {
            builder.Append(',');
        }
        builder.Append('\n');
    }

    private static void AppendBooleanProperty(StringBuilder builder, string name, bool value, bool comma, int indent)
    {
        Indent(builder, indent);
        builder.Append('"').Append(name).Append("\": ").Append(value ? "true" : "false");
        if (comma)
        {
            builder.Append(',');
        }
        builder.Append('\n');
    }

    private static void AppendNumberProperty(StringBuilder builder, string name, int value, bool comma, int indent)
    {
        Indent(builder, indent);
        builder.Append('"').Append(name).Append("\": ").Append(value);
        if (comma)
        {
            builder.Append(',');
        }
        builder.Append('\n');
    }

    private static void AppendNullProperty(StringBuilder builder, string name, bool comma, int indent)
    {
        Indent(builder, indent);
        builder.Append('"').Append(name).Append("\": null");
        if (comma)
        {
            builder.Append(',');
        }
        builder.Append('\n');
    }

    private static void AppendStringArrayProperty(StringBuilder builder, string name, IEnumerable<string> values, bool comma, int indent)
    {
        Indent(builder, indent);
        builder.Append('"').Append(name).Append("\": [");
        bool first = true;
        foreach (string value in values)
        {
            if (!first)
            {
                builder.Append(", ");
            }
            builder.Append('"').Append(EscapeJson(value)).Append('"');
            first = false;
        }
        builder.Append(']');
        if (comma)
        {
            builder.Append(',');
        }
        builder.Append('\n');
    }

    private static string EscapeJson(string value)
    {
        if (value == null)
        {
            return string.Empty;
        }
        var builder = new StringBuilder(value.Length + 16);
        foreach (char character in value)
        {
            switch (character)
            {
                case '\\': builder.Append("\\\\"); break;
                case '"': builder.Append("\\\""); break;
                case '\b': builder.Append("\\b"); break;
                case '\f': builder.Append("\\f"); break;
                case '\n': builder.Append("\\n"); break;
                case '\r': builder.Append("\\r"); break;
                case '\t': builder.Append("\\t"); break;
                default:
                    if (character < 0x20)
                    {
                        builder.Append("\\u").Append(((int)character).ToString("x4"));
                    }
                    else
                    {
                        builder.Append(character);
                    }
                    break;
            }
        }
        return builder.ToString();
    }

    private static void Indent(StringBuilder builder, int count)
    {
        builder.Append(' ', count * 2);
    }
}
