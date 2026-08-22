param(
  [Parameter(Mandatory=$true)]
  [string]$TemplateOpju,
  [string]$OutputDir = '',
  [string]$Stamp = '',
  [bool]$Headless = $true,
  [bool]$CloseOrigin = $true,
  [bool]$ExportTemplateComparison = $true,
  [bool]$EnforceTemplateComparison = $true,
  [double]$ComparisonMeanTolerance = 0.0,
  [double]$ComparisonMaxTolerance = 0.0,
  [switch]$Force,
  [switch]$KeepIntermediate
)

$ErrorActionPreference = 'Stop'

if (-not ('HplcPathSecurity' -as [type])) {
  Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;

public static class HplcPathSecurity {
    private const uint InvalidFileAttributes = 0xFFFFFFFF;
    private const uint FileAttributeReparsePoint = 0x00000400;

    [StructLayout(LayoutKind.Sequential)]
    private struct ByHandleFileInformation {
        public uint FileAttributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFileAttributes(string path);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandle(
        IntPtr handle,
        out ByHandleFileInformation information
    );

    public static bool IsReparsePoint(string path) {
        uint attributes = GetFileAttributes(path);
        if (attributes == InvalidFileAttributes) {
            int error = Marshal.GetLastWin32Error();
            if (error == 2 || error == 3) return false;
            throw new IOException(
                "Could not inspect path attributes safely: " + path,
                new Win32Exception(error)
            );
        }
        return (attributes & FileAttributeReparsePoint) != 0;
    }

    public static string GetFileIdentity(string path) {
        using (var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.ReadWrite | FileShare.Delete
        )) {
            ByHandleFileInformation information;
            if (!GetFileInformationByHandle(
                stream.SafeFileHandle.DangerousGetHandle(),
                out information
            )) {
                throw new IOException(
                    "Could not read file identity safely: " + path,
                    new Win32Exception(Marshal.GetLastWin32Error())
                );
            }
            return string.Format(
                "{0:X8}:{1:X8}:{2:X8}",
                information.VolumeSerialNumber,
                information.FileIndexHigh,
                information.FileIndexLow
            );
        }
    }
}
"@
}

function To-OriginPath([string]$Path) {
  return ($Path -replace '\\', '/')
}

function Get-FileSha256([string]$Path) {
  $stream = [System.IO.File]::OpenRead([System.IO.Path]::GetFullPath($Path))
  $algorithm = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = $algorithm.ComputeHash($stream)
    return ([System.BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
  }
  finally {
    $algorithm.Dispose()
    $stream.Dispose()
  }
}

function Resolve-RunPath([string]$Path, [string]$BaseDir) {
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $BaseDir $Path))
}

function Get-ProjectOutputRoot([string]$ProjectRoot) {
  foreach ($configPath in @((Join-Path $ProjectRoot 'config\local.yaml'), (Join-Path $ProjectRoot 'config\default.yaml'))) {
    if (-not (Test-Path -LiteralPath $configPath)) { continue }
    $section = ''
    foreach ($rawLine in Get-Content -LiteralPath $configPath -Encoding UTF8) {
      $line = ($rawLine -replace '#.*$', '').Trim()
      if ([string]::IsNullOrWhiteSpace($line)) { continue }
      if (($rawLine -notmatch '^\s') -and ($line -match '^([^:]+):\s*$')) {
        $section = $Matches[1].Trim()
        continue
      }
      if (($section -eq 'paths') -and ($line -match '^(output_root|output):\s*(.*)$')) {
        $value = $Matches[2].Trim().Trim('"').Trim([char]39)
        if ([string]::IsNullOrWhiteSpace($value)) {
          throw "Configured paths.$($Matches[1]) must have a non-empty scalar path value: $configPath"
        }
        try {
          $candidate = Resolve-RunPath $value $ProjectRoot
        }
        catch {
          throw "Configured paths.$($Matches[1]) could not be resolved safely: $configPath"
        }
        Assert-ProjectOutputRootSafe $candidate $ProjectRoot
        return $candidate
      }
      if (($section -eq 'paths') -and ($line -match '^(output_root|output)\b')) {
        throw "Configured output root entry is malformed and was rejected: $configPath"
      }
    }
  }
  $outputName = [string]([char]36755) + [string]([char]20986)
  $fallback = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $ProjectRoot) $outputName))
  Assert-ProjectOutputRootSafe $fallback $ProjectRoot
  return $fallback
}

function Assert-UnderOrEqual([string]$Path, [string]$Parent, [string]$Message) {
  $resolvedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $resolvedParent = [System.IO.Path]::GetFullPath($Parent).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  if ($resolvedPath.Equals($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) { return }
  $prefix = $resolvedParent + [System.IO.Path]::DirectorySeparatorChar
  if ($resolvedPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { return }
  throw $Message
}

function Test-UnderOrEqual([string]$Path, [string]$Parent) {
  $resolvedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $resolvedParent = [System.IO.Path]::GetFullPath($Parent).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  if ($resolvedPath.Equals($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
  $prefix = $resolvedParent + [System.IO.Path]::DirectorySeparatorChar
  return $resolvedPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-ProjectOutputRootSafe([string]$OutputRoot, [string]$ProjectRoot) {
  $candidate = [System.IO.Path]::GetFullPath($OutputRoot)
  $project = [System.IO.Path]::GetFullPath($ProjectRoot)
  $protectedTrees = @(
    $project,
    (Join-Path $project 'input\raw_data'),
    (Join-Path $project 'templates')
  )
  foreach ($protected in $protectedTrees) {
    if ((Test-UnderOrEqual $candidate $protected) -or (Test-UnderOrEqual $protected $candidate)) {
      throw (
        'Configured output root must be independent from the project, raw-data, ' +
        'template, and input trees: ' + $candidate
      )
    }
  }
}

function Assert-OutputSeparatedFromTemplateTree(
  [string]$OutputRoot,
  [string]$OutputPath,
  [string]$TemplatePath
) {
  $templateDirectory = [System.IO.Path]::GetFullPath((Split-Path -Parent $TemplatePath))
  foreach ($candidate in @($OutputRoot, $OutputPath)) {
    $full = [System.IO.Path]::GetFullPath($candidate)
    if ((Test-UnderOrEqual $full $templateDirectory) -or (Test-UnderOrEqual $templateDirectory $full)) {
      throw (
        'Configured output root and OutputDir must be independent from the ' +
        'TemplateOpju source directory: ' + $templateDirectory
      )
    }
  }
}

function Assert-NoReparsePointInPath([string]$Path, [string]$Label) {
  $current = [System.IO.Path]::GetFullPath($Path)
  while (-not [string]::IsNullOrWhiteSpace($current)) {
    if ([HplcPathSecurity]::IsReparsePoint($current)) {
      throw "$Label path chain contains a symbolic link, junction, or reparse point: $current"
    }
    $parent = [System.IO.Directory]::GetParent($current)
    if ($null -eq $parent) { break }
    $next = $parent.FullName
    if ($next.Equals($current, [System.StringComparison]::OrdinalIgnoreCase)) { break }
    $current = $next
  }
}

function Assert-NotSameFile([string]$TemplatePath, [string]$TargetPath) {
  $templateFull = [System.IO.Path]::GetFullPath($TemplatePath)
  $targetFull = [System.IO.Path]::GetFullPath($TargetPath)
  if ($templateFull.Equals($targetFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Planned output aliases TemplateOpju: $targetFull"
  }
  if ([System.IO.File]::Exists($targetFull)) {
    $templateIdentity = [HplcPathSecurity]::GetFileIdentity($templateFull)
    $targetIdentity = [HplcPathSecurity]::GetFileIdentity($targetFull)
    if ($templateIdentity.Equals($targetIdentity, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Planned output is the same file as TemplateOpju: $targetFull"
    }
  }
}

function Assert-SafeOutputDirectoryTarget(
  [string]$Path,
  [string]$OutputRoot,
  [string]$Label
) {
  Assert-UnderOrEqual $Path $OutputRoot "$Label must stay under its declared output root: $Path"
  Assert-NoReparsePointInPath $Path $Label
  if ([System.IO.File]::Exists([System.IO.Path]::GetFullPath($Path))) {
    throw "$Label collides with an existing file: $Path"
  }
}

function Assert-SafeOutputFileTarget(
  [string]$Path,
  [string]$OutputRoot,
  [string]$TemplatePath,
  [string]$Label
) {
  Assert-UnderOrEqual $Path $OutputRoot "$Label must stay under its declared output root: $Path"
  Assert-NoReparsePointInPath $Path $Label
  if ([System.IO.Directory]::Exists([System.IO.Path]::GetFullPath($Path))) {
    throw "$Label file target collides with an existing directory: $Path"
  }
  Assert-NotSameFile $TemplatePath $Path
}

function Assert-NoReparsePointInTree([string]$Root, [string]$Label) {
  Assert-NoReparsePointInPath $Root $Label
  if (-not [System.IO.Directory]::Exists($Root)) { return }
  $pending = New-Object 'System.Collections.Generic.Stack[string]'
  $pending.Push([System.IO.Path]::GetFullPath($Root))
  while ($pending.Count -gt 0) {
    $directory = $pending.Pop()
    foreach ($entry in [System.IO.Directory]::EnumerateFileSystemEntries($directory)) {
      if ([HplcPathSecurity]::IsReparsePoint($entry)) {
        throw "$Label contains a symbolic link, junction, or reparse point: $entry"
      }
      if ([System.IO.Directory]::Exists($entry)) {
        $pending.Push($entry)
      }
    }
  }
}

function Assert-OutputTreeDoesNotAliasTemplate(
  [string]$Root,
  [string]$TemplatePath
) {
  if (-not [System.IO.Directory]::Exists($Root)) { return }
  Assert-NoReparsePointInTree $Root 'Existing HPLC output package'
  $templateIdentity = [HplcPathSecurity]::GetFileIdentity(
    [System.IO.Path]::GetFullPath($TemplatePath)
  )
  foreach (
    $candidate in [System.IO.Directory]::EnumerateFiles(
      [System.IO.Path]::GetFullPath($Root),
      '*',
      [System.IO.SearchOption]::AllDirectories
    )
  ) {
    $candidateIdentity = [HplcPathSecurity]::GetFileIdentity($candidate)
    if (
      $templateIdentity.Equals(
        $candidateIdentity,
        [System.StringComparison]::OrdinalIgnoreCase
      )
    ) {
      throw "Planned output is the same file as TemplateOpju: $candidate"
    }
  }
}

function Assert-HplcCalibrationInputs(
  [object[]]$Points,
  [object[]]$Series
) {
  if ($Points.Count -lt 2) {
    throw 'HPLC calibration requires at least two standard points.'
  }
  if ($Series.Count -ne 3) {
    throw 'HPLC calibration requires exactly the three locked calibration series.'
  }
  $seenPages = @{}
  $previousX = [double]::NegativeInfinity
  foreach ($item in $Series) {
    foreach ($field in @('Key', 'Page', 'TemplateGraph', 'Name')) {
      if ([string]::IsNullOrWhiteSpace([string]$item[$field])) {
        throw "HPLC calibration series has an empty required field: $field"
      }
    }
    $pageKey = ([string]$item.Page).ToLowerInvariant()
    if ($seenPages.ContainsKey($pageKey)) {
      throw "HPLC calibration graph page is duplicated: $($item.Page)"
    }
    $seenPages[$pageKey] = $true
  }
  foreach ($point in $Points) {
    $x = [double]$point.X
    if ([double]::IsNaN($x) -or [double]::IsInfinity($x) -or $x -le $previousX) {
      throw 'HPLC calibration concentrations must be finite and strictly increasing.'
    }
    foreach ($item in $Series) {
      $y = [double]$point[$item.Key]
      if ([double]::IsNaN($y) -or [double]::IsInfinity($y)) {
        throw "HPLC calibration response is not finite for $($item.Key)."
      }
    }
    $previousX = $x
  }
}

function Assert-HplcStagedPackageComplete(
  [string]$PackageRoot,
  [string[]]$RequiredRelativePaths,
  [string]$MetadataRelativePath,
  [string]$ComparisonRelativePath,
  [bool]$ExpectComparison
) {
  if (-not [System.IO.Directory]::Exists($PackageRoot)) {
    throw "HPLC staged package directory is missing: $PackageRoot"
  }
  Assert-NoReparsePointInTree $PackageRoot 'HPLC staged package'
  foreach ($relativePath in $RequiredRelativePaths) {
    if (
      [string]::IsNullOrWhiteSpace($relativePath) -or
      [System.IO.Path]::IsPathRooted($relativePath)
    ) {
      throw "HPLC staged package has an invalid required relative path: $relativePath"
    }
    $candidate = [System.IO.Path]::GetFullPath(
      (Join-Path $PackageRoot $relativePath)
    )
    Assert-UnderOrEqual $candidate $PackageRoot (
      "HPLC staged package path escapes its root: $relativePath"
    )
    if (
      -not [System.IO.File]::Exists($candidate) -or
      (Get-Item -LiteralPath $candidate).Length -le 0
    ) {
      throw "HPLC staged package artifact is missing or empty: $relativePath"
    }
  }

  $metadataFile = [System.IO.Path]::GetFullPath(
    (Join-Path $PackageRoot $MetadataRelativePath)
  )
  try {
    $metadataObject = Get-Content -LiteralPath $metadataFile -Raw -Encoding UTF8 |
      ConvertFrom-Json
  }
  catch {
    throw (
      'HPLC staged package metadata is not valid JSON: ' +
      $_.Exception.Message
    )
  }
  if (
    ([string]$metadataObject.processing_status) -ne 'success' -or
    [string]::IsNullOrWhiteSpace([string]$metadataObject.origin_file) -or
    @($metadataObject.figure_tif).Count -ne 3 -or
    @($metadataObject.preview_png).Count -ne 3
  ) {
    throw 'HPLC staged package metadata does not describe one complete three-page success.'
  }

  if ($ExpectComparison) {
    $comparisonFile = [System.IO.Path]::GetFullPath(
      (Join-Path $PackageRoot $ComparisonRelativePath)
    )
    $comparisonRows = @(Import-Csv -LiteralPath $comparisonFile -Delimiter "`t")
    if ($comparisonRows.Count -ne 3) {
      throw 'HPLC staged package comparison report must contain exactly three graph rows.'
    }
    foreach ($row in $comparisonRows) {
      if (
        ([string]$row.ExactPixelMatch) -ne 'True' -or
        ([string]$row.Status) -ne 'exact_pixel_match'
      ) {
        throw "HPLC staged package contains an unverified graph comparison: $($row.Page)"
      }
    }
  }
}

function Commit-HplcOutputPackage(
  [string]$StagedDir,
  [string]$FinalDir,
  [string]$BackupDir,
  [bool]$AllowExisting,
  [string[]]$RequiredRelativePaths,
  [string]$MetadataRelativePath,
  [string]$ComparisonRelativePath,
  [bool]$ExpectComparison
) {
  Assert-HplcStagedPackageComplete `
    $StagedDir `
    $RequiredRelativePaths `
    $MetadataRelativePath `
    $ComparisonRelativePath `
    $ExpectComparison
  Assert-NoReparsePointInPath $FinalDir 'HPLC final package'
  Assert-NoReparsePointInPath $BackupDir 'HPLC transaction backup'
  if (
    [System.IO.File]::Exists($FinalDir) -or
    [System.IO.File]::Exists($BackupDir) -or
    [System.IO.Directory]::Exists($BackupDir)
  ) {
    throw 'HPLC package commit target or transaction backup path is not available.'
  }

  $finalExists = [System.IO.Directory]::Exists($FinalDir)
  if ($finalExists -and (-not $AllowExisting)) {
    throw 'HPLC final package exists without overwrite authorization.'
  }
  if ($finalExists) {
    Assert-NoReparsePointInTree $FinalDir 'Existing HPLC output package'
  }

  $finalParent = Split-Path -Parent $FinalDir
  Assert-NoReparsePointInPath $finalParent 'HPLC final package parent'
  New-Item -ItemType Directory -Path $finalParent -Force | Out-Null
  Assert-NoReparsePointInPath $finalParent 'HPLC final package parent'

  $oldMoved = $false
  $newMoved = $false
  try {
    if ($finalExists) {
      Move-Item -LiteralPath $FinalDir -Destination $BackupDir -ErrorAction Stop
      $oldMoved = $true
    }
    Move-Item -LiteralPath $StagedDir -Destination $FinalDir -ErrorAction Stop
    $newMoved = $true
    Assert-HplcStagedPackageComplete `
      $FinalDir `
      $RequiredRelativePaths `
      $MetadataRelativePath `
      $ComparisonRelativePath `
      $ExpectComparison
  }
  catch {
    $commitFailure = $_.Exception.Message
    $rollbackFailures = @()
    if ($newMoved -and [System.IO.Directory]::Exists($FinalDir)) {
      try {
        if ([System.IO.Directory]::Exists($StagedDir)) {
          throw "staging path unexpectedly exists: $StagedDir"
        }
        Move-Item -LiteralPath $FinalDir -Destination $StagedDir -ErrorAction Stop
        $newMoved = $false
      }
      catch {
        $rollbackFailures += 'new package rollback: ' + $_.Exception.Message
      }
    }
    if ($oldMoved -and [System.IO.Directory]::Exists($BackupDir)) {
      if ([System.IO.Directory]::Exists($FinalDir)) {
        $rollbackFailures += (
          'prior package retained at transaction backup because final path is occupied: ' +
          $BackupDir
        )
      }
      else {
        try {
          Move-Item -LiteralPath $BackupDir -Destination $FinalDir -ErrorAction Stop
          $oldMoved = $false
        }
        catch {
          $rollbackFailures += 'prior package restore: ' + $_.Exception.Message
        }
      }
    }
    if ($rollbackFailures.Count -gt 0) {
      throw (
        'HPLC package commit failed: ' + $commitFailure +
        '; rollback was incomplete: ' + ($rollbackFailures -join '; ')
      )
    }
    throw (
      'HPLC package commit failed and the prior package was restored: ' +
      $commitFailure
    )
  }

  if ($oldMoved -and [System.IO.Directory]::Exists($BackupDir)) {
    try {
      Assert-NoReparsePointInTree $BackupDir 'HPLC transaction backup cleanup'
      Remove-Item -LiteralPath $BackupDir -Recurse -Force -ErrorAction Stop
    }
    catch {
      Write-Warning (
        'The new HPLC package is committed and verified, but the recoverable ' +
        'transaction backup could not be removed: ' + $BackupDir
      )
    }
  }
}

function Has-AssistantTrace([string]$Text) {
  if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
  return ($Text -match '(?i)(codex|chatgpt|openai)')
}

function Get-NeutralOriginStagePath([string]$Stamp, [string]$ProjectRoot) {
  $candidateBases = @()
  foreach ($base in @($env:TEMP, $env:LOCALAPPDATA, [System.IO.Path]::GetTempPath())) {
    if (-not [string]::IsNullOrWhiteSpace($base)) {
      $candidateBases += (Join-Path $base 'ResearchDataOriginPipeline\origin_stage')
    }
  }
  $projectDrive = [System.IO.Path]::GetPathRoot($ProjectRoot)
  if (-not [string]::IsNullOrWhiteSpace($projectDrive)) {
    $candidateBases += (Join-Path $projectDrive 'RDOP_OriginStage')
  }

  $seen = @{}
  foreach ($base in $candidateBases) {
    $stageLeaf = 'hplc_' + $Stamp + '_' + $PID + '_' + [guid]::NewGuid().ToString('N').Substring(0, 8)
    $stagePath = [System.IO.Path]::GetFullPath((Join-Path $base $stageLeaf))
    $key = $stagePath.ToLowerInvariant()
    if ($seen.ContainsKey($key)) { continue }
    $seen[$key] = $true
    if (Has-AssistantTrace $stagePath) { continue }
    Assert-NoReparsePointInPath $stagePath 'Origin stage'
    if ([System.IO.File]::Exists($stagePath) -or [System.IO.Directory]::Exists($stagePath)) { continue }
    return $stagePath
  }
  throw 'Could not select a safe, unused Origin staging path without assistant/tool labels.'
}

function Remove-NeutralOriginStage([string]$StagePath) {
  if ([string]::IsNullOrWhiteSpace($StagePath)) { return }
  $full = [System.IO.Path]::GetFullPath($StagePath)
  $leaf = Split-Path -Leaf $full
  if ($leaf -notlike 'hplc_*') {
    throw "Refusing to remove non-run-specific Origin stage: $full"
  }
  if (Has-AssistantTrace $full) {
    throw "Refusing to remove Origin stage with assistant/tool labels: $full"
  }
  if (Test-Path -LiteralPath $full) {
    Assert-NoReparsePointInTree $full 'Origin stage cleanup'
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
  }
}

function To-RunRelativePath([string]$Path, [string]$Root) {
  $full = [System.IO.Path]::GetFullPath($Path)
  $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
  if ($full.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    return ($full.Substring($rootFull.Length).TrimStart('\', '/') -replace '\\', '/')
  }
  return [System.IO.Path]::GetFileName($full)
}

function Convert-ToSafeOriginName([string]$Name, [string]$Fallback = 'Data') {
  $clean = ([regex]::Replace($Name, '[^A-Za-z0-9_]+', '_')).Trim('_')
  if ([string]::IsNullOrWhiteSpace($clean)) { $clean = $Fallback }
  if ($clean[0] -match '[0-9]') { $clean = $Fallback + '_' + $clean }
  if ($clean.Length -gt 24) { $clean = $clean.Substring(0, 24).Trim('_') }
  if ([string]::IsNullOrWhiteSpace($clean)) { $clean = $Fallback }
  return $clean
}

function Escape-OriginText([string]$Text) {
  return $Text.Replace('"', '\"').Replace("`r", ' ').Replace("`n", ' ')
}

function Write-Utf8Lines([string]$Path, [string[]]$Lines) {
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllLines($Path, $Lines, $utf8NoBom)
}

function Write-Log([string]$Message) {
  Add-Content -LiteralPath $script:LogPath -Encoding UTF8 -Value $Message
}

function Wait-ForOutputFile([string]$Path, [int]$TimeoutSeconds = 20) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if ((Test-Path -LiteralPath $Path) -and ((Get-Item -LiteralPath $Path).Length -gt 0)) {
      return
    }
    Start-Sleep -Milliseconds 250
  }
  throw "Expected output file was not created or was empty: $Path"
}

function Get-OriginProcessIds() {
  return @(Get-Process -Name Origin* -ErrorAction SilentlyContinue | ForEach-Object { [int]$_.Id })
}

function Get-OriginProcessIdsStartedByScript([int[]]$BeforePids) {
  $known = @{}
  foreach ($pidValue in $BeforePids) { $known[$pidValue] = $true }
  $deadline = (Get-Date).AddSeconds(10)
  while ((Get-Date) -lt $deadline) {
    $owned = @(
      Get-Process -Name Origin* -ErrorAction SilentlyContinue |
      Where-Object { -not $known.ContainsKey([int]$_.Id) } |
      ForEach-Object { [int]$_.Id }
    )
    if ($owned.Count -gt 0) {
      Start-Sleep -Milliseconds 500
      $stabilized = @(
        Get-Process -Name Origin* -ErrorAction SilentlyContinue |
        Where-Object { -not $known.ContainsKey([int]$_.Id) } |
        ForEach-Object { [int]$_.Id }
      )
      if ($stabilized.Count -eq 1) { return $stabilized }
      throw (
        'Origin.Application launch did not yield exactly one provable task-owned ' +
        'Origin PID; no Origin process will be force-closed.'
      )
    }
    Start-Sleep -Milliseconds 100
  }
  throw 'Origin.Application launched without a provable task-owned Origin PID.'
}

function Close-OriginProcessesStartedByScript([int[]]$OwnedPids) {
  $owned = @{}
  foreach ($pidValue in $OwnedPids) {
    if ($pidValue -gt 0) { $owned[$pidValue] = $true }
  }
  if ($owned.Count -eq 0) { return }
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline) {
    $remaining = @(
      Get-Process -Id @($owned.Keys) -ErrorAction SilentlyContinue |
      Where-Object { $_.ProcessName -like 'Origin*' }
    )
    if ($remaining.Count -eq 0) { return }
    Start-Sleep -Milliseconds 500
  }
  $remaining = @(
    Get-Process -Id @($owned.Keys) -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -like 'Origin*' }
  )
  foreach ($process in $remaining) {
    Stop-Process -Id $process.Id -Force -ErrorAction Stop
  }
  Start-Sleep -Milliseconds 500
  $stillRunning = @(
    Get-Process -Id @($owned.Keys) -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -like 'Origin*' }
  )
  if ($stillRunning.Count -gt 0) {
    throw (
      'Task-owned Origin PID(s) remained after bounded close: ' +
      (($stillRunning | ForEach-Object { $_.Id }) -join ',')
    )
  }
}

function Get-OriginPageRasterSpec($App, [string]$PageName, [int]$Dpi) {
  if ($Dpi -lt 72 -or $Dpi -gt 1200) {
    throw "TIF export DPI must be an integer from 72 through 1200; got $Dpi"
  }
  Assert-HplcGraphExists $App $PageName
  $App.Execute('win -a ' + $PageName + ';') | Out-Null
  $pageWidth = [double]$App.Evaluate('page.width')
  $pageHeight = [double]$App.Evaluate('page.height')
  if (
    [double]::IsNaN($pageWidth) -or
    [double]::IsInfinity($pageWidth) -or
    [double]::IsNaN($pageHeight) -or
    [double]::IsInfinity($pageHeight) -or
    $pageWidth -le 0 -or
    $pageHeight -le 0
  ) {
    throw "Origin graph page $PageName has invalid dimensions: ${pageWidth}x${pageHeight}"
  }
  $expectedWidth = [Math]::Max(
    1,
    [int][Math]::Round(
      $pageWidth * $Dpi / 1000.0,
      [System.MidpointRounding]::AwayFromZero
    )
  )
  $expectedHeight = [Math]::Max(
    1,
    [int][Math]::Round(
      $pageHeight * $Dpi / 1000.0,
      [System.MidpointRounding]::AwayFromZero
    )
  )
  return [pscustomobject]@{
    PageWidth = $pageWidth
    PageHeight = $pageHeight
    ExpectedWidth = $expectedWidth
    ExpectedHeight = $expectedHeight
  }
}

function Assert-TifPhysicalResolution(
  [string]$Path,
  [double]$PageWidth,
  [double]$PageHeight,
  [int]$Dpi
) {
  if (-not (Test-Path -LiteralPath $Path)) { throw "TIF output does not exist: $Path" }
  Add-Type -AssemblyName System.Drawing -ErrorAction Stop
  $image = $null
  $sensitiveTagIds = @()
  try {
    $image = [System.Drawing.Image]::FromFile($Path)
    if ($image.RawFormat.Guid -ne [System.Drawing.Imaging.ImageFormat]::Tiff.Guid) {
      throw "Artifact is not a readable TIFF: $Path"
    }
    $width = [int]$image.Width
    $height = [int]$image.Height
    $taggedDpiX = [double]$image.HorizontalResolution
    $taggedDpiY = [double]$image.VerticalResolution
    $sensitivePattern = '(?i)(?:(?<![A-Za-z0-9])(?:[A-Z]:[\\/]|\\\\[^\\/\s]+[\\/]|/(?:home|users|mnt|media|private|tmp|var/tmp)/)|(?<![A-Za-z0-9])(?:codex|chatgpt|openai|assistant|agent)(?![A-Za-z0-9]))'
    foreach ($property in $image.PropertyItems) {
      $utf8Text = [System.Text.Encoding]::UTF8.GetString($property.Value)
      $utf16Text = [System.Text.Encoding]::Unicode.GetString($property.Value)
      if (($utf8Text -match $sensitivePattern) -or ($utf16Text -match $sensitivePattern)) {
        $sensitiveTagIds += [int]$property.Id
      }
    }
  }
  catch {
    throw ("TIF physical-resolution readback failed for " + $Path + ": " + $_.Exception.Message)
  }
  finally {
    if ($image) { $image.Dispose() }
  }

  $expectedWidth = [Math]::Max(
    1,
    [int][Math]::Round(
      $PageWidth * $Dpi / 1000.0,
      [System.MidpointRounding]::AwayFromZero
    )
  )
  $expectedHeight = [Math]::Max(
    1,
    [int][Math]::Round(
      $PageHeight * $Dpi / 1000.0,
      [System.MidpointRounding]::AwayFromZero
    )
  )
  $toleranceX = [Math]::Max(2, [int][Math]::Ceiling($expectedWidth * 0.005))
  $toleranceY = [Math]::Max(2, [int][Math]::Ceiling($expectedHeight * 0.005))
  $effectiveDpiX = $width * 1000.0 / $PageWidth
  $effectiveDpiY = $height * 1000.0 / $PageHeight
  $effectiveToleranceX = $toleranceX * 1000.0 / $PageWidth
  $effectiveToleranceY = $toleranceY * 1000.0 / $PageHeight
  $failures = @()
  if ([Math]::Abs($taggedDpiX - $Dpi) -gt 1.0 -or [Math]::Abs($taggedDpiY - $Dpi) -gt 1.0) {
    $failures += ('tagged DPI is {0:0.###}x{1:0.###}, expected {2}x{2}' -f $taggedDpiX, $taggedDpiY, $Dpi)
  }
  if ([Math]::Abs($width - $expectedWidth) -gt $toleranceX -or [Math]::Abs($height - $expectedHeight) -gt $toleranceY) {
    $failures += ('pixel dimensions are {0}x{1}, expected {2}x{3} within +-{4}x+-{5} px' -f $width, $height, $expectedWidth, $expectedHeight, $toleranceX, $toleranceY)
  }
  if ([Math]::Abs($effectiveDpiX - $Dpi) -gt $effectiveToleranceX -or [Math]::Abs($effectiveDpiY - $Dpi) -gt $effectiveToleranceY) {
    $failures += ('effective physical DPI is {0:0.###}x{1:0.###}, expected {2}x{2}' -f $effectiveDpiX, $effectiveDpiY, $Dpi)
  }
  if ($sensitiveTagIds.Count -gt 0) {
    $failures += ('sensitive local-path or tool-trace metadata is present in TIFF tag(s) ' + (($sensitiveTagIds | Sort-Object -Unique) -join ','))
  }
  if ($failures.Count -gt 0) {
    throw (
      "TIF is not native $Dpi dpi evidence for Origin page ${PageWidth}x${PageHeight} (0.001 inch): " +
      ($failures -join '; ')
    )
  }
  return [pscustomobject]@{
    Width = $width
    Height = $height
    TaggedDpiX = $taggedDpiX
    TaggedDpiY = $taggedDpiY
    EffectiveDpiX = $effectiveDpiX
    EffectiveDpiY = $effectiveDpiY
  }
}

function Export-GraphPng($App, [string]$PageName, [string]$Directory, [string]$BaseName) {
  $path = Join-Path $Directory ($BaseName + '.png')
  Assert-SafeOutputDirectoryTarget $Directory $script:OutputDirForSafety 'PNG output directory'
  Assert-SafeOutputFileTarget $path $script:OutputDirForSafety $script:TemplateOpjuForSafety 'PNG output'
  New-Item -ItemType Directory -Path $Directory -Force | Out-Null
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
  $App.Execute('win -a ' + $PageName + '; expGraph type:=png path:="' + (To-OriginPath $Directory) + '" filename:="' + $BaseName + '" overwrite:=replace;') | Out-Null
  Wait-ForOutputFile $path
  return $path
}

function Reset-ProjectIdentityForArtifactExport($App) {
  $ok = $App.Execute('doc -rn; doc -s;')
  $projectPath = [string]$App.LTStr('%X')
  $projectName = [string]$App.LTStr('%G')
  if (
    -not $ok -or
    -not [string]::IsNullOrWhiteSpace($projectPath) -or
    -not $projectName.Equals('UNTITLED', [System.StringComparison]::OrdinalIgnoreCase)
  ) {
    throw 'Origin did not clear the in-memory project identity before artifact export.'
  }
}

function Export-GraphTif($App, [string]$PageName, [string]$Directory, [string]$BaseName, [int]$ExportDpi) {
  $path = Join-Path $Directory ($BaseName + '.tif')
  Assert-SafeOutputDirectoryTarget $Directory $script:OutputDirForSafety 'TIF output directory'
  Assert-SafeOutputFileTarget $path $script:OutputDirForSafety $script:TemplateOpjuForSafety 'TIF output'
  New-Item -ItemType Directory -Path $Directory -Force | Out-Null
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
  $rasterSpec = Get-OriginPageRasterSpec $App $PageName $ExportDpi
  $App.Execute(
    'win -a ' + $PageName +
    '; expGraph type:=tif path:="' + (To-OriginPath $Directory) +
    '" filename:="' + $BaseName +
    '" overwrite:=replace sysopts:=0 tr.Margin:=2 tr1.Unit:=2 tr1.Width:=' + $rasterSpec.ExpectedWidth +
    ' tr2.TIF.dotsperinch:=' + $ExportDpi + ';'
  ) | Out-Null
  Wait-ForOutputFile $path
  $evidence = Assert-TifPhysicalResolution $path $rasterSpec.PageWidth $rasterSpec.PageHeight $ExportDpi
  $script:TifResolutionEvidence[$BaseName] = [ordered]@{
    requested_dpi = $ExportDpi
    page_width_origin_units = $rasterSpec.PageWidth
    page_height_origin_units = $rasterSpec.PageHeight
    width_px = $evidence.Width
    height_px = $evidence.Height
    expected_width_px = $rasterSpec.ExpectedWidth
    expected_height_px = $rasterSpec.ExpectedHeight
    tagged_dpi_x = $evidence.TaggedDpiX
    tagged_dpi_y = $evidence.TaggedDpiY
    effective_dpi_x = $evidence.EffectiveDpiX
    effective_dpi_y = $evidence.EffectiveDpiY
    sensitive_metadata_scan = 'pass'
  }
  Write-Log (
    'TIF_DPI_EVIDENCE=' + $PageName +
    ';page=' + $rasterSpec.PageWidth + 'x' + $rasterSpec.PageHeight +
    ';pixels=' + $evidence.Width + 'x' + $evidence.Height +
    ';tagged_dpi=' + $evidence.TaggedDpiX + 'x' + $evidence.TaggedDpiY +
    ';effective_dpi=' + $evidence.EffectiveDpiX + 'x' + $evidence.EffectiveDpiY
  )
  return $path
}

function Assert-HplcGraphExists($App, [string]$PageName) {
  $layer = $App.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $App.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { throw "Required HPLC template graph page was not found: $PageName" }
  $App.Execute('win -a ' + $PageName + ';') | Out-Null
  $activePage = [string]$App.LTStr('page.name$')
  if (-not $activePage.Equals($PageName, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Required HPLC graph page could not be activated exactly: expected $PageName, got $activePage"
  }
}

function Assert-HplcTemplateStructure($App, [object[]]$RequiredSeries) {
  foreach ($item in $RequiredSeries) {
    $pageName = [string]$item.TemplateGraph
    Assert-HplcGraphExists $App $pageName
    $layerCount = [int]$App.Evaluate('page.nlayers')
    if ($layerCount -lt 1) {
      throw "Required HPLC template graph has no graph layer: $pageName"
    }
    foreach ($expression in @('page.width', 'page.height', 'layer.width', 'layer.height')) {
      $value = [double]$App.Evaluate($expression)
      if (
        [double]::IsNaN($value) -or
        [double]::IsInfinity($value) -or
        $value -le 0
      ) {
        throw (
          "Required HPLC template graph has invalid structure: " +
          $pageName + ':' + $expression + '=' + $value
        )
      }
    }
  }
}

function Sanitize-Graph($App, [string]$PageName) {
  $App.Execute('win -a ' + $PageName + ';') | Out-Null
  $layerCount = [int]$App.Evaluate('page.nlayers')
  while ($layerCount -gt 1) {
    $App.Execute('layer -d ' + $layerCount + ';') | Out-Null
    $layerCount = [int]$App.Evaluate('page.nlayers')
  }

  $layer = $App.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $App.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { return }

  $keep = @('YR', 'XT', 'YL', 'XB', '3D', '__BCO2', '__FRAMESRCDATAINFOS', 'Legend')
  for ($i = $layer.GraphObjects.Count - 1; $i -ge 0; $i--) {
    $obj = $layer.GraphObjects.Item($i)
    $name = ''
    try { $name = $obj.Name } catch {}
    if ($keep -notcontains $name) {
      try { $obj.Destroy() | Out-Null } catch {}
    }
  }
}

function Apply-HplcYAxisStyle($App, [string]$PageName, [int]$YDivideBy, [string]$YTitle) {
  $App.Execute('win -a ' + $PageName + ';') | Out-Null
  $App.Execute('layer.x.ticks=2; layer.x.ticklength=8; layer.x.label.pt=28; layer.x.label.bold=1; layer.x.showLabels=1; layer.x.showAxes=3; layer.x.label.dir=1; layer.x.label.rotate=0;') | Out-Null
  $App.Execute('layer.y.label.divideBy=' + $YDivideBy + '; layer.y.ticks=2; layer.y.ticklength=8; layer.y.tickthickness=3; layer.y.label.pt=22; layer.y.label.bold=1; layer.y.showLabels=1; layer.y.showAxes=3; layer.y2.ticks=0;') | Out-Null
  $App.Execute('label -yl "' + $YTitle + '";') | Out-Null
}

function Assert-HplcYAxisStyle($App, [string]$PageName, [int]$ExpectedYDivideBy) {
  $App.Execute('win -a ' + $PageName + ';') | Out-Null
  $divideBy = [double]$App.Evaluate('layer.y.label.divideby')
  $ticks = [int]$App.Evaluate('layer.y.ticks')
  if ([Math]::Abs($divideBy - $ExpectedYDivideBy) -gt 0.001) {
    throw "HPLC Y-axis divideBy was not applied on $PageName; expected $ExpectedYDivideBy, got $divideBy"
  }
  if ($ticks -ne 2) {
    throw "HPLC Y-axis outward ticks were not applied on $PageName; expected ticks=2, got $ticks"
  }
}

function Set-Legend(
  $App,
  [string]$PageName,
  [string]$Substance,
  [double]$Slope,
  [double]$Intercept,
  [double]$R2,
  [int]$LegendLeft,
  [int]$LegendTop,
  [int]$LegendWidth,
  [int]$LegendHeight
) {
  $App.Execute('win -a ' + $PageName + ';') | Out-Null
  $layer = $App.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $App.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { return }

  $rows = @(
    ('\l(1) \b( ' + $Substance + ')'),
    ('\b(y = ' + $Slope.ToString('0.0000', [Globalization.CultureInfo]::InvariantCulture) + 'x + ' + $Intercept.ToString('0.0000', [Globalization.CultureInfo]::InvariantCulture) + ')'),
    ('\b(R\+(2) = ' + $R2.ToString('0.000000', [Globalization.CultureInfo]::InvariantCulture) + ')')
  )

  for ($i = 0; $i -lt $layer.GraphObjects.Count; $i++) {
    $obj = $layer.GraphObjects.Item($i)
    $name = ''
    try { $name = $obj.Name } catch {}
    if ($name -eq 'Legend') {
      $obj.Text = ($rows -join "`r`n")
      try {
        $obj.Left = $LegendLeft
        $obj.Top = $LegendTop
        $obj.Width = $LegendWidth
        $obj.Height = $LegendHeight
      } catch {}
    }
  }
}

function Get-HplcGraphObject($App, [string]$PageName, [string]$ObjectName) {
  $layer = $App.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $App.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { return $null }
  for ($i = 0; $i -lt $layer.GraphObjects.Count; $i++) {
    $obj = $layer.GraphObjects.Item($i)
    $name = ''
    try { $name = $obj.Name } catch {}
    if ($name -eq $ObjectName) { return $obj }
  }
  return $null
}

function Set-HplcTextObjectBounds(
  $App,
  [string]$PageName,
  [string]$ObjectName,
  [int]$Left,
  [int]$Top,
  [int]$Width,
  [int]$Height
) {
  $App.Execute('win -a ' + $PageName + ';') | Out-Null
  $obj = Get-HplcGraphObject $App $PageName $ObjectName
  if (-not $obj) { throw "HPLC graph object $ObjectName was not found on $PageName" }
  $obj.Left = $Left
  $obj.Top = $Top
  $obj.Width = $Width
  $obj.Height = $Height
}

function Assert-HplcTextObjectBounds(
  $App,
  [string]$PageName,
  [string]$ObjectName,
  [int]$ExpectedLeft,
  [int]$ExpectedTop,
  [int]$ExpectedWidth,
  [int]$ExpectedHeight
) {
  $App.Execute('win -a ' + $PageName + ';') | Out-Null
  $obj = Get-HplcGraphObject $App $PageName $ObjectName
  if (-not $obj) { throw "HPLC graph object $ObjectName was not found on $PageName" }
  $actual = @([int]$obj.Left, [int]$obj.Top, [int]$obj.Width, [int]$obj.Height)
  $expected = @($ExpectedLeft, $ExpectedTop, $ExpectedWidth, $ExpectedHeight)
  for ($i = 0; $i -lt $expected.Count; $i++) {
    if ([Math]::Abs($actual[$i] - $expected[$i]) -gt 1) {
      throw "HPLC graph object $ObjectName bounds differ on $PageName; expected $($expected -join ','), got $($actual -join ',')"
    }
  }
}

function Set-OriginWorksheetColumn($App, [int]$ColumnIndex, [double[]]$Values) {
  for ($rowIndex = 0; $rowIndex -lt $Values.Count; $rowIndex++) {
    $rowNumber = $rowIndex + 1
    $value = ([double]$Values[$rowIndex]).ToString('G17', [Globalization.CultureInfo]::InvariantCulture)
    $App.Execute('wcol(' + $ColumnIndex + ')[' + $rowNumber + ']=' + $value + ';') | Out-Null
  }
}

function Initialize-OriginCalibrationWorksheet($App, [string]$BookName, [string]$DisplayName, [int]$RowCount) {
  $sheetName = Convert-ToSafeOriginName ([System.IO.Path]::GetFileNameWithoutExtension($DisplayName)) 'Data'
  $App.Execute('newbook name:="' + $BookName + '";') | Out-Null
  $safeDisplayName = Escape-OriginText $DisplayName
  $App.Execute('page.longname$="' + $safeDisplayName + '"; page.comments$=""; page.comment$="";') | Out-Null
  $App.Execute('wks.name$="' + $sheetName + '"; wks.longname$="' + $safeDisplayName + '"; wks.comments$=""; wks.comment$=""; wks.ncols=3; wks.nrows=' + $RowCount + ';') | Out-Null
  $App.Execute('wks.col1.type=4; wks.col2.type=1; wks.col3.type=1;') | Out-Null
  $App.Execute('wks.col1.lname$="Concentration_mM"; wks.col2.lname$="Measured"; wks.col3.lname$="Origin_Linear_Fit";') | Out-Null
  $App.Execute('wks.col1.comment$=""; wks.col2.comment$=""; wks.col3.comment$="";') | Out-Null
}

function Sanitize-ProjectPages($App) {
  $App.Execute('doc -e W { page.comments$=""; page.comment$=""; wks.comments$=""; wks.comment$=""; }; doc -e P { page.comments$=""; page.comment$=""; };') | Out-Null
}

function Import-And-PlotCalibration(
  $App,
  [string]$Template,
  [string]$PageName,
  [string]$Substance,
  [string]$XTitle,
  [string]$YTitle,
  [double]$YTo,
  [double]$YInc,
  [int]$YDivideBy,
  [int]$LegendLeft,
  [int]$LegendTop,
  [int]$LegendWidth,
  [int]$LegendHeight,
  [int]$XTitleLeft,
  [int]$XTitleTop,
  [int]$XTitleWidth,
  [int]$XTitleHeight,
  [int]$YTitleLeft,
  [int]$YTitleTop,
  [int]$YTitleWidth,
  [int]$YTitleHeight,
  [double[]]$Concentrations,
  [double[]]$Measured
) {
  $axis_title_size=36
  $dataFileName = $Substance + '_calibration_data.tsv'
  $bookName = Convert-ToSafeOriginName ([System.IO.Path]::GetFileNameWithoutExtension($dataFileName)) 'Data'
  if ($Concentrations.Count -ne $Measured.Count) {
    throw "HPLC calibration series length mismatch on $PageName"
  }
  Initialize-OriginCalibrationWorksheet $App $bookName $dataFileName $Concentrations.Count
  Set-OriginWorksheetColumn $App 1 $Concentrations
  Set-OriginWorksheetColumn $App 2 $Measured
  $App.Execute('fitlr iy:=(1,2) oy:=(1,3);') | Out-Null
  $intercept = [double]$App.Evaluate('fitlr.a')
  $slope = [double]$App.Evaluate('fitlr.b')
  $r = [double]$App.Evaluate('fitlr.r')
  $r2 = $r * $r

  $plotCmd = 'worksheet -s 1 2; plotxy iy:=(1,2) plot:=202 ogl:=[<new template:="' + (To-OriginPath $Template) + '" name:="' + $PageName + '">];'
  $App.Execute($plotCmd) | Out-Null
  $App.Execute('win -a ' + $PageName + '; page.longname$="' + $Substance + ' calibration curve"; page.comments$=""; page.comment$=""; page.width=6432; page.height=4923;') | Out-Null
  $App.Execute('layer -b s 0;') | Out-Null
  $App.Execute('layer.left=17.89; layer.top=11.6; layer.width=68.19; layer.height=71.81; layer -a; layer.x.from=0; layer.x.to=2.1; layer.x.inc=0.5; layer.y.from=0; layer.y.to=' + $YTo + '; layer.y.inc=' + $YInc + ';') | Out-Null
  $App.Execute('layer.x.label.pt=28; layer.y.label.pt=22; layer.x.title.pt=' + $axis_title_size + '; layer.y.title.pt=' + $axis_title_size + ';') | Out-Null
  $App.Execute('axis -ps Y A 3; axis -ps Y L 1; layer.y.showAxes=3; layer.y.showLabels=1; layer.y.opposite=1; layer.y.showopposite=1; layer.y.label.dir=1; layer.y.label.rotate=0; layer.y.label.pt=22; layer.y.label.bold=1; layer.y.ticks=2; layer.y.tickthickness=3; layer.y.ticklength=8; layer.y.label.divideBy=' + $YDivideBy + '; layer.y2.ticks=0; layer.x.thickness=3; layer.y.thickness=3; layer.y2.thickness=3; doc -e DY {set %C -c color(255,128,0);};') | Out-Null
  $App.Execute('label -xb "\b(' + $XTitle + ')"; label -yl "' + $YTitle + '";') | Out-Null
  Apply-HplcYAxisStyle $App $PageName $YDivideBy $YTitle
  $App.Execute('legendupdate mode:=lname; doc -e DY {set %C -sx 0; set %C -sy 0; set %C -sxs 1; set %C -sys 1; set %C -lw 3; set %C -z 7;};') | Out-Null
  Sanitize-Graph $App $PageName
  Set-HplcTextObjectBounds $App $PageName 'XB' $XTitleLeft $XTitleTop $XTitleWidth $XTitleHeight
  Set-HplcTextObjectBounds $App $PageName 'YL' $YTitleLeft $YTitleTop $YTitleWidth $YTitleHeight
  Set-Legend $App $PageName $Substance $slope $intercept $r2 $LegendLeft $LegendTop $LegendWidth $LegendHeight
  Apply-HplcYAxisStyle $App $PageName $YDivideBy $YTitle
  Set-HplcTextObjectBounds $App $PageName 'XB' $XTitleLeft $XTitleTop $XTitleWidth $XTitleHeight
  Set-HplcTextObjectBounds $App $PageName 'YL' $YTitleLeft $YTitleTop $YTitleWidth $YTitleHeight
  Assert-HplcYAxisStyle $App $PageName $YDivideBy
  Assert-HplcTextObjectBounds $App $PageName 'XB' $XTitleLeft $XTitleTop $XTitleWidth $XTitleHeight
  Assert-HplcTextObjectBounds $App $PageName 'YL' $YTitleLeft $YTitleTop $YTitleWidth $YTitleHeight
  return @{
    Slope = $slope
    Intercept = $intercept
    R2 = $r2
  }
}

if (-not ('HplcImageComparer' -as [type])) {
  Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public sealed class HplcImageDiffResult {
    public bool SameSize;
    public int TemplateWidth;
    public int TemplateHeight;
    public int GeneratedWidth;
    public int GeneratedHeight;
    public long PixelCount;
    public long ChangedPixels;
    public double MeanAbsDelta;
    public int MaxAbsDelta;
}

public static class HplcImageComparer {
    public static HplcImageDiffResult Compare(string templatePath, string generatedPath) {
        using (var sourceTemplate = new Bitmap(templatePath))
        using (var sourceGenerated = new Bitmap(generatedPath)) {
            var result = new HplcImageDiffResult {
                TemplateWidth = sourceTemplate.Width,
                TemplateHeight = sourceTemplate.Height,
                GeneratedWidth = sourceGenerated.Width,
                GeneratedHeight = sourceGenerated.Height,
                SameSize = sourceTemplate.Width == sourceGenerated.Width && sourceTemplate.Height == sourceGenerated.Height
            };
            if (!result.SameSize) return result;
            using (var template = ToArgb(sourceTemplate))
            using (var generated = ToArgb(sourceGenerated)) {
                var rectangle = new Rectangle(0, 0, template.Width, template.Height);
                var templateData = template.LockBits(rectangle, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                var generatedData = generated.LockBits(rectangle, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                try {
                    int templateStride = Math.Abs(templateData.Stride);
                    int generatedStride = Math.Abs(generatedData.Stride);
                    var templateBytes = new byte[templateStride * template.Height];
                    var generatedBytes = new byte[generatedStride * generated.Height];
                    Marshal.Copy(templateData.Scan0, templateBytes, 0, templateBytes.Length);
                    Marshal.Copy(generatedData.Scan0, generatedBytes, 0, generatedBytes.Length);
                    long sum = 0;
                    int max = 0;
                    long changed = 0;
                    for (int y = 0; y < template.Height; y++) {
                        int templateRow = y * templateStride;
                        int generatedRow = y * generatedStride;
                        for (int x = 0; x < template.Width; x++) {
                            bool pixelChanged = false;
                            int templateOffset = templateRow + x * 4;
                            int generatedOffset = generatedRow + x * 4;
                            for (int channel = 0; channel < 3; channel++) {
                                int delta = Math.Abs(templateBytes[templateOffset + channel] - generatedBytes[generatedOffset + channel]);
                                sum += delta;
                                if (delta > max) max = delta;
                                if (delta != 0) pixelChanged = true;
                            }
                            if (pixelChanged) changed++;
                        }
                    }
                    result.PixelCount = (long)template.Width * template.Height;
                    result.ChangedPixels = changed;
                    result.MeanAbsDelta = result.PixelCount == 0 ? 0 : (double)sum / (result.PixelCount * 3L);
                    result.MaxAbsDelta = max;
                    return result;
                }
                finally {
                    template.UnlockBits(templateData);
                    generated.UnlockBits(generatedData);
                }
            }
        }
    }

    private static Bitmap ToArgb(Bitmap source) {
        var output = new Bitmap(source.Width, source.Height, PixelFormat.Format32bppArgb);
        using (var graphics = Graphics.FromImage(output)) graphics.DrawImageUnscaled(source, 0, 0);
        return output;
    }
}
"@
}

function Compare-ImageFiles([string]$TemplatePath, [string]$GeneratedPath, [double]$MeanTolerance, [double]$MaxTolerance) {
  if (-not (Test-Path -LiteralPath $TemplatePath)) { throw "Template image missing: $TemplatePath" }
  if (-not (Test-Path -LiteralPath $GeneratedPath)) { throw "Generated image missing: $GeneratedPath" }
  $difference = [HplcImageComparer]::Compare($TemplatePath, $GeneratedPath)
  if (-not $difference.SameSize) {
    return [pscustomobject]@{
      Pass = $false
      ExactPixelMatch = $false
      TemplateWidth = $difference.TemplateWidth
      TemplateHeight = $difference.TemplateHeight
      GeneratedWidth = $difference.GeneratedWidth
      GeneratedHeight = $difference.GeneratedHeight
      Samples = 0
      ChangedPixels = 0
      MeanAbsDelta = ''
      MaxAbsDelta = ''
      Status = 'dimension_mismatch'
    }
  }
  $passed = ($difference.MeanAbsDelta -le $MeanTolerance) -and ($difference.MaxAbsDelta -le $MaxTolerance)
  $exact = $difference.ChangedPixels -eq 0
  return [pscustomobject]@{
    Pass = $passed
    ExactPixelMatch = $exact
    TemplateWidth = $difference.TemplateWidth
    TemplateHeight = $difference.TemplateHeight
    GeneratedWidth = $difference.GeneratedWidth
    GeneratedHeight = $difference.GeneratedHeight
    Samples = $difference.PixelCount
    ChangedPixels = $difference.ChangedPixels
    MeanAbsDelta = $difference.MeanAbsDelta.ToString('0.0000', [Globalization.CultureInfo]::InvariantCulture)
    MaxAbsDelta = $difference.MaxAbsDelta
    Status = if ($exact) { 'exact_pixel_match' } elseif ($passed) { 'within_explicit_tolerance' } else { 'pixel_delta_exceeds_tolerance' }
  }
}

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path (Get-ProjectOutputRoot $projectRoot) 'hplc_calibration_origin'
}
$finalOutputDir = Resolve-RunPath $OutputDir $projectRoot
$projectOutputRoot = Get-ProjectOutputRoot $projectRoot
Assert-UnderOrEqual $finalOutputDir $projectOutputRoot ("OutputDir must stay under the configured output root: " + $finalOutputDir)
if (
  [System.IO.Path]::GetFullPath($finalOutputDir).TrimEnd('\', '/').Equals(
    [System.IO.Path]::GetFullPath($projectOutputRoot).TrimEnd('\', '/'),
    [System.StringComparison]::OrdinalIgnoreCase
  )
) {
  throw 'OutputDir must be a dedicated package directory below the configured output root.'
}
Assert-NoReparsePointInPath $projectOutputRoot 'Configured output root'
Assert-SafeOutputDirectoryTarget $finalOutputDir $projectOutputRoot 'HPLC final output directory'
Assert-NoReparsePointInPath $finalOutputDir 'OutputDir'
if ($EnforceTemplateComparison -and (($ComparisonMeanTolerance -ne 0.0) -or ($ComparisonMaxTolerance -ne 0.0))) {
  throw 'Strict template comparison requires zero mean and max pixel tolerances.'
}
if ($EnforceTemplateComparison -and (-not $ExportTemplateComparison)) {
  throw 'Strict template comparison cannot be enforced when comparison export is disabled.'
}
if ([string]::IsNullOrWhiteSpace($Stamp)) {
  $Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
}
if ($Stamp -match '(?i)(codex|chatgpt|openai)') {
  throw "Stamp must not include assistant or tool labels."
}
if (($Stamp -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]*$') -or ($Stamp -eq '.') -or ($Stamp -eq '..')) {
  throw 'Stamp must be one safe filename component using only letters, digits, underscore, dot, or hyphen.'
}

$ExportDpi = 600
$templateOpjuPath = Resolve-RunPath $TemplateOpju $projectRoot
Assert-NoReparsePointInPath $templateOpjuPath 'TemplateOpju'
if (-not [System.IO.File]::Exists($templateOpjuPath)) {
  throw ("HPLC calibration template OPJU not found: " + (Split-Path -Leaf $templateOpjuPath))
}
Assert-OutputSeparatedFromTemplateTree $projectOutputRoot $finalOutputDir $templateOpjuPath
$templateHashBefore = Get-FileSha256 $templateOpjuPath

if (Test-UnderOrEqual $templateOpjuPath $finalOutputDir) {
  throw 'TemplateOpju must be outside OutputDir so no output cleanup can modify or delete the source template.'
}
$replaceExistingOutput = $false
if ([System.IO.Directory]::Exists($finalOutputDir)) {
  Assert-NoReparsePointInTree $finalOutputDir 'Existing HPLC output package'
  Assert-OutputTreeDoesNotAliasTemplate $finalOutputDir $templateOpjuPath
  $existingOutputEntry = Get-ChildItem -LiteralPath $finalOutputDir -Force -ErrorAction Stop | Select-Object -First 1
  if (($null -ne $existingOutputEntry) -and (-not $Force)) {
    throw 'OutputDir is not empty; rerun with -Force or choose a new output directory.'
  }
  $replaceExistingOutput = $true
}

$transactionId = (
  $Stamp + '_' + $PID + '_' +
  [guid]::NewGuid().ToString('N').Substring(0, 12)
)
$transactionOutputDir = Join-Path $projectOutputRoot (
  '.hplc_package_stage_' + $transactionId
)
$transactionBackupDir = Join-Path $projectOutputRoot (
  '.hplc_package_backup_' + $transactionId
)
foreach ($transactionPath in @($transactionOutputDir, $transactionBackupDir)) {
  Assert-SafeOutputDirectoryTarget `
    $transactionPath `
    $projectOutputRoot `
    'HPLC transaction directory'
  if ([System.IO.Directory]::Exists($transactionPath)) {
    throw "HPLC transaction path already exists: $transactionPath"
  }
}
$OutputDir = $transactionOutputDir

$dataDir = Join-Path $OutputDir 'processed_data'
$originDir = Join-Path $OutputDir 'origin_files'
$previewDir = Join-Path $OutputDir 'figures_preview'
$tifDir = Join-Path $OutputDir 'figures_tif'
$metadataDir = Join-Path $OutputDir 'metadata\HPLC_calibration_curves'
$comparisonDir = Join-Path $OutputDir 'template_comparison'
$templateOriginalPreviewDir = Join-Path $comparisonDir 'template_original_preview'
$templateOriginalTifDir = Join-Path $comparisonDir 'template_original_tif'
$templatePreviewDir = Join-Path $comparisonDir 'template_preview'
$templateTifDir = Join-Path $comparisonDir 'template_tif'
$logDir = Join-Path $OutputDir 'logs'
$outputOpju = Join-Path $originDir ('HPLC_calibration_curves_' + $Stamp + '.opju')
$comparisonReport = Join-Path $comparisonDir 'comparison_report.tsv'
$metadataPath = Join-Path $metadataDir 'metadata.json'
$script:LogPath = Join-Path $logDir 'origin_run_log.txt'

$yTitlePower3 = '\b(Peak area \(40)10\+(3) mAU*s\(41))'
$yTitlePower2 = '\b(Peak area \(40)10\+(2) mAU*s\(41))'

$series = @(
  @{ Key='Sulfoxide'; Page='Cal_Sulfoxide'; TemplateGraph='Cal_Sulfoxide'; Name='Anisole sulfoxide'; YTo=3200; YInc=500; YDivideBy=1000; YTitle=$yTitlePower3; LegendLeft=1585; LegendTop=880; LegendWidth=2429; LegendHeight=826; XTitleLeft=1927; XTitleTop=4487; XTitleWidth=2835; XTitleHeight=338; YTitleLeft=362; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204 },
  @{ Key='Sulfone'; Page='Cal_Sulfone'; TemplateGraph='Cal_Sulfone'; Name='Anisole sulfone'; YTo=1100; YInc=200; YDivideBy=100; YTitle=$yTitlePower2; LegendLeft=1740; LegendTop=808; LegendWidth=2308; LegendHeight=826; XTitleLeft=1927; XTitleTop=4487; XTitleWidth=2835; XTitleHeight=338; YTitleLeft=413; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204 },
  @{ Key='Sulfide'; Page='Cal_Sulfide'; TemplateGraph='Cal_Sulfide'; Name='Anisole sulfide'; YTo=23000; YInc=5000; YDivideBy=1000; YTitle=$yTitlePower3; LegendLeft=1578; LegendTop=850; LegendWidth=2457; LegendHeight=760; XTitleLeft=1927; XTitleTop=4487; XTitleWidth=2835; XTitleHeight=338; YTitleLeft=413; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204 }
)

$stageRoot = Get-NeutralOriginStagePath $Stamp $projectRoot
$stageTemplateDir = Join-Path $stageRoot 'origin_templates'
$workingTemplate = Join-Path $stageRoot ('template_working_copy_' + $Stamp + '.opju')
$plannedOutputDirectories = @(
  $OutputDir,
  $dataDir,
  $originDir,
  $previewDir,
  $tifDir,
  $metadataDir,
  $comparisonDir,
  $templateOriginalPreviewDir,
  $templateOriginalTifDir,
  $templatePreviewDir,
  $templateTifDir,
  $logDir
)
$plannedOutputFiles = @(
  $outputOpju,
  $comparisonReport,
  $metadataPath,
  $script:LogPath,
  (Join-Path $dataDir 'final_calibration_data.tsv')
)
foreach ($s in $series) {
  $plannedOutputFiles += (Join-Path $dataDir ($s.Key + '_plot_data.tsv'))
  $plannedOutputFiles += (Join-Path $previewDir ($s.Page + '_' + $Stamp + '.png'))
  $plannedOutputFiles += (Join-Path $tifDir ($s.Page + '_' + $Stamp + '.tif'))
  $plannedOutputFiles += (Join-Path $templateOriginalPreviewDir ($s.Page + '_template_original.png'))
  $plannedOutputFiles += (Join-Path $templateOriginalTifDir ($s.Page + '_template_original.tif'))
  $plannedOutputFiles += (Join-Path $templatePreviewDir ($s.Page + '_template.png'))
  $plannedOutputFiles += (Join-Path $templateTifDir ($s.Page + '_template.tif'))
}
$requiredOutputFiles = @(
  $outputOpju,
  $metadataPath,
  $script:LogPath,
  (Join-Path $dataDir 'final_calibration_data.tsv')
)
foreach ($s in $series) {
  $requiredOutputFiles += (Join-Path $dataDir ($s.Key + '_plot_data.tsv'))
  $requiredOutputFiles += (Join-Path $previewDir ($s.Page + '_' + $Stamp + '.png'))
  $requiredOutputFiles += (Join-Path $tifDir ($s.Page + '_' + $Stamp + '.tif'))
  if ($ExportTemplateComparison) {
    $requiredOutputFiles += (Join-Path $templateOriginalPreviewDir ($s.Page + '_template_original.png'))
    $requiredOutputFiles += (Join-Path $templateOriginalTifDir ($s.Page + '_template_original.tif'))
    $requiredOutputFiles += (Join-Path $templatePreviewDir ($s.Page + '_template.png'))
    $requiredOutputFiles += (Join-Path $templateTifDir ($s.Page + '_template.tif'))
  }
}
if ($ExportTemplateComparison) {
  $requiredOutputFiles += $comparisonReport
}
$plannedStageDirectories = @($stageRoot, $stageTemplateDir)
$plannedStageFiles = @($workingTemplate)
foreach ($s in $series) {
  $plannedStageFiles += (Join-Path $stageTemplateDir ('hplc_' + $s.TemplateGraph + '_' + $Stamp + '.otpu'))
}

foreach ($directory in $plannedOutputDirectories) {
  Assert-SafeOutputDirectoryTarget $directory $OutputDir 'HPLC output directory'
}
foreach ($target in $plannedOutputFiles) {
  Assert-SafeOutputFileTarget $target $OutputDir $templateOpjuPath 'HPLC planned output'
}
foreach ($directory in $plannedStageDirectories) {
  Assert-SafeOutputDirectoryTarget $directory $stageRoot 'Origin stage directory'
}
foreach ($target in $plannedStageFiles) {
  Assert-SafeOutputFileTarget $target $stageRoot $templateOpjuPath 'Origin stage file'
}

$script:OutputDirForSafety = $OutputDir
$script:TemplateOpjuForSafety = $templateOpjuPath

$originPidsBefore = Get-OriginProcessIds
if ($originPidsBefore.Count -gt 0) {
  throw 'Origin is already running; close every Origin session before running the HPLC calibration helper.'
}

$points = @(
  @{ Point='S1'; X=0.05; Sulfoxide=67.848; Sulfone=22.553; Sulfide=504.621 },
  @{ Point='S2'; X=0.10; Sulfoxide=145.164; Sulfone=47.271; Sulfide=1054.405 },
  @{ Point='S3'; X=0.25; Sulfoxide=379.292; Sulfone=127.723; Sulfide=2863.680 },
  @{ Point='S4'; X=0.50; Sulfoxide=755.397; Sulfone=252.807; Sulfide=5612.688 },
  @{ Point='S5'; X=1.00; Sulfoxide=1505.311; Sulfone=502.702; Sulfide=11264.664 },
  @{ Point='S6'; X=1.50; Sulfoxide=2208.395; Sulfone=739.446; Sulfide=16408.434 },
  @{ Point='S7'; X=2.00; Sulfoxide=2959.872; Sulfone=991.845; Sulfide=21670.291 }
)
Assert-HplcCalibrationInputs $points $series

$masterHeader = 'Point' + "`t" + 'Concentration_mM' + "`t" + 'Sulfoxide_area_mAU_s' + "`t" + 'Sulfone_area_mAU_s' + "`t" + 'Sulfide_area_mAU_s'
$masterLines = @($masterHeader)
foreach ($p in $points) {
  $masterLines += ($p.Point + "`t" + $p.X.ToString('0.00', [Globalization.CultureInfo]::InvariantCulture) + "`t" + $p.Sulfoxide.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture) + "`t" + $p.Sulfone.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture) + "`t" + $p.Sulfide.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture))
}

New-Item -ItemType Directory -Path $stageRoot, $stageTemplateDir -Force | Out-Null
Assert-SafeOutputFileTarget $workingTemplate $stageRoot $templateOpjuPath 'Origin template working copy'
Copy-Item -LiteralPath $templateOpjuPath -Destination $workingTemplate -Force

$templateOriginalPreviewMap = @{}
$templatePreviewMap = @{}
$generatedPreviewMap = @{}
$generatedTifMap = @{}
$fitMap = @{}
$script:TifResolutionEvidence = @{}

$app = $null
$ownedOriginPids = @()
$originRunSucceeded = $false
try {
  $app = New-Object -ComObject Origin.Application
  $ownedOriginPids = @(Get-OriginProcessIdsStartedByScript $originPidsBefore)
  $app.Visible = if ($Headless) { 0 } else { 1 }
  $app.Load($workingTemplate) | Out-Null
  Assert-HplcTemplateStructure $app $series

  New-Item -ItemType Directory -Path $dataDir, $originDir, $previewDir, $tifDir, $metadataDir, $comparisonDir, $templateOriginalPreviewDir, $templateOriginalTifDir, $templatePreviewDir, $templateTifDir, $logDir -Force | Out-Null
  Write-Utf8Lines (Join-Path $dataDir 'final_calibration_data.tsv') $masterLines
  foreach ($s in $series) {
    $lines = @()
    foreach ($p in $points) {
      $x = [double]$p.X
      $y = [double]$p[$s.Key]
      $lines += ($x.ToString('0.00', [Globalization.CultureInfo]::InvariantCulture) + "`t" + $y.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture))
    }
    Write-Utf8Lines (Join-Path $dataDir ($s.Key + '_plot_data.tsv')) $lines
  }

  Write-Log 'Origin.Application launched'
  Write-Log ('TemplateOpju=' + [System.IO.Path]::GetFileName($templateOpjuPath))
  Write-Log ('OutputDir=' + [System.IO.Path]::GetFileName($finalOutputDir))
  Reset-ProjectIdentityForArtifactExport $app

  foreach ($s in $series) {
    $templateBase = 'hplc_' + $s.TemplateGraph + '_' + $Stamp
    $templatePath = Join-Path $stageTemplateDir ($templateBase + '.otpu')
    $app.Execute('win -a ' + $s.TemplateGraph + ';') | Out-Null
    Assert-HplcGraphExists $app $s.TemplateGraph
    if ($ExportTemplateComparison) {
      $templateOriginalPreviewMap[$s.Page] = Export-GraphPng $app $s.TemplateGraph $templateOriginalPreviewDir ($s.Page + '_template_original')
      Export-GraphTif $app $s.TemplateGraph $templateOriginalTifDir ($s.Page + '_template_original') $ExportDpi | Out-Null
    }
    Apply-HplcYAxisStyle $app $s.TemplateGraph $s.YDivideBy $s.YTitle
    if ($ExportTemplateComparison) {
      $templatePreviewMap[$s.Page] = Export-GraphPng $app $s.TemplateGraph $templatePreviewDir ($s.Page + '_template')
      Export-GraphTif $app $s.TemplateGraph $templateTifDir ($s.Page + '_template') $ExportDpi | Out-Null
    }
    foreach ($expr in @('page.width', 'page.height', 'page.nlayers', 'layer.left', 'layer.top', 'layer.width', 'layer.height', 'layer.x.thickness', 'layer.y.thickness')) {
      ($s.TemplateGraph + ':' + $expr + '=' + $app.Evaluate($expr)) | Add-Content -LiteralPath $script:LogPath -Encoding UTF8
    }
    Assert-SafeOutputFileTarget $templatePath $stageRoot $templateOpjuPath 'Origin format-theme stage output'
    if (Test-Path -LiteralPath $templatePath) { Remove-Item -LiteralPath $templatePath -Force }
    $app.Execute('template_saveas pg:=' + $s.TemplateGraph + ' category:="HPLC_Calibration" template:="' + $templateBase + '" filepath:="' + (To-OriginPath $stageTemplateDir) + '" emf:=0 bmp:=1 loadsys:=0;') | Out-Null
    Wait-ForOutputFile $templatePath
    $s.TemplatePath = $templatePath
  }

  $app.NewProject() | Out-Null
  $xTitle = 'Concentration (mM)'
  foreach ($s in $series) {
    $xValues = @()
    $yValues = @()
    foreach ($p in $points) {
      $xValues += [double]$p.X
      $yValues += [double]$p[$s.Key]
    }
    $fitMap[$s.Page] = Import-And-PlotCalibration $app $s.TemplatePath $s.Page $s.Name $xTitle $s.YTitle $s.YTo $s.YInc $s.YDivideBy $s.LegendLeft $s.LegendTop $s.LegendWidth $s.LegendHeight $s.XTitleLeft $s.XTitleTop $s.XTitleWidth $s.XTitleHeight $s.YTitleLeft $s.YTitleTop $s.YTitleWidth $s.YTitleHeight $xValues $yValues
  }

  Sanitize-ProjectPages $app
  $app.Save($outputOpju) | Out-Null
  Wait-ForOutputFile $outputOpju
  $app.NewProject() | Out-Null
  $app.Load($outputOpju) | Out-Null
  Reset-ProjectIdentityForArtifactExport $app
  Write-Log ('ReopenedFinalOpju=' + [System.IO.Path]::GetFileName($outputOpju))
  foreach ($s in $series) {
    Assert-HplcGraphExists $app $s.Page
  }
  foreach ($s in $series) {
    $baseName = $s.Page + '_' + $Stamp
    $generatedPreviewMap[$s.Page] = Export-GraphPng $app $s.Page $previewDir $baseName
    $generatedTifMap[$s.Page] = Export-GraphTif $app $s.Page $tifDir $baseName $ExportDpi
  }
  $originRunSucceeded = $true
}
finally {
  if (($CloseOrigin -or (-not $originRunSucceeded)) -and $null -ne $app) {
    try { $app.Exit() | Out-Null } catch {}
    Close-OriginProcessesStartedByScript $ownedOriginPids
  }
}

if ($ExportTemplateComparison) {
  $comparisonLines = @(
    'Page' + "`t" + 'OriginalTemplatePng' + "`t" + 'ExpectedTemplatePng' + "`t" + 'GeneratedPng' + "`t" + 'TemplateWidth' + "`t" + 'TemplateHeight' + "`t" + 'GeneratedWidth' + "`t" + 'GeneratedHeight' + "`t" + 'PixelCount' + "`t" + 'ChangedPixels' + "`t" + 'MeanAbsDelta' + "`t" + 'MaxAbsDelta' + "`t" + 'ExactPixelMatch' + "`t" + 'Status'
  )
  $failedComparisons = @()
  $comparisonExact = $true
  foreach ($s in $series) {
    $result = Compare-ImageFiles $templatePreviewMap[$s.Page] $generatedPreviewMap[$s.Page] $ComparisonMeanTolerance $ComparisonMaxTolerance
    $comparisonLines += (
      $s.Page + "`t" +
      (To-RunRelativePath $templateOriginalPreviewMap[$s.Page] $OutputDir) + "`t" +
      (To-RunRelativePath $templatePreviewMap[$s.Page] $OutputDir) + "`t" +
      (To-RunRelativePath $generatedPreviewMap[$s.Page] $OutputDir) + "`t" +
      $result.TemplateWidth + "`t" +
      $result.TemplateHeight + "`t" +
      $result.GeneratedWidth + "`t" +
      $result.GeneratedHeight + "`t" +
      $result.Samples + "`t" +
      $result.ChangedPixels + "`t" +
      $result.MeanAbsDelta + "`t" +
      $result.MaxAbsDelta + "`t" +
      $result.ExactPixelMatch + "`t" +
      $result.Status
    )
    if (-not $result.ExactPixelMatch) { $comparisonExact = $false }
    if (-not $result.Pass) { $failedComparisons += $s.Page + ':' + $result.Status }
  }
  Write-Utf8Lines $comparisonReport $comparisonLines
  if ($EnforceTemplateComparison -and $failedComparisons.Count -gt 0) {
    throw ("Template comparison failed: " + ($failedComparisons -join '; '))
  }
}

if (-not $KeepIntermediate) {
  try { Remove-NeutralOriginStage $stageRoot } catch { Write-Log ('Origin stage cleanup skipped: ' + $_.Exception.Message) }
}

$templateHashAfter = Get-FileSha256 $templateOpjuPath
if ($templateHashAfter -ne $templateHashBefore) {
  throw 'TemplateOpju changed during the HPLC calibration run; outputs are rejected.'
}
$transactionalValidation = @(
  'final OPJU reopened before graph export',
  'three native 600 dpi TIFF exports validated',
  'three PNG previews exported',
  'metadata parsed and required artifact inventory verified'
)
if ($ExportTemplateComparison) {
  $transactionalValidation += 'three strict full-pixel template comparisons passed'
}
$metadataPayload = [ordered]@{
  dataset_id = ('HPLC_calibration_curves_' + $Stamp)
  data_type = 'HPLC/LC exported data'
  processing_status = 'success'
  manual_check_required = $true
  origin_file = (To-RunRelativePath $outputOpju $OutputDir)
  processed_data = (To-RunRelativePath (Join-Path $dataDir 'final_calibration_data.tsv') $OutputDir)
  figure_tif = @($series | ForEach-Object { To-RunRelativePath $generatedTifMap[$_.Page] $OutputDir })
  preview_png = @($series | ForEach-Object { To-RunRelativePath $generatedPreviewMap[$_.Page] $OutputDir })
  template_original_preview_png = if ($ExportTemplateComparison) { @($series | ForEach-Object { To-RunRelativePath $templateOriginalPreviewMap[$_.Page] $OutputDir }) } else { @() }
  template_expected_preview_png = if ($ExportTemplateComparison) { @($series | ForEach-Object { To-RunRelativePath $templatePreviewMap[$_.Page] $OutputDir }) } else { @() }
  template_comparison_report = if ($ExportTemplateComparison) { To-RunRelativePath $comparisonReport $OutputDir } else { $null }
  template_comparison_exact_pixel_match = if ($ExportTemplateComparison) { $comparisonExact } else { $null }
  template_source = [ordered]@{
    filename = [System.IO.Path]::GetFileName($templateOpjuPath)
    sha256_before = $templateHashBefore
    sha256_after = $templateHashAfter
    used_read_only_via_working_copy = $true
  }
  tif_resolution_evidence = @(
    $series | ForEach-Object {
      $baseName = $_.Page + '_' + $Stamp
      [ordered]@{
        page = $_.Page
        figure_tif = To-RunRelativePath $generatedTifMap[$_.Page] $OutputDir
        evidence = $script:TifResolutionEvidence[$baseName]
      }
    }
  )
  calibration_fit = @(
    $series | ForEach-Object {
      $fit = $fitMap[$_.Page]
      [ordered]@{
        page = $_.Page
        substance = $_.Name
        slope = $fit.Slope
        intercept = $fit.Intercept
        r_squared = $fit.R2
      }
    }
  )
  overwrite_authorized = [bool]$Force
  transactional_package_commit = $true
  transactional_validation = $transactionalValidation
  manual_check_items = @(
    'confirm HPLC calibration point identity, integration boundaries, and calibration applicability before quantitative use',
    'confirm Origin graph formatting against the accepted HPLC calibration template comparison report'
  )
  forbidden_claims = @(
    'do not infer product identity, yield, selectivity, or mechanism from calibration-curve plotting alone'
  )
}
Assert-SafeOutputFileTarget $metadataPath $OutputDir $templateOpjuPath 'HPLC metadata output'
($metadataPayload | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $metadataPath -Encoding UTF8

$requiredRelativePaths = @(
  $requiredOutputFiles |
  ForEach-Object { To-RunRelativePath $_ $OutputDir }
)
$metadataRelativePath = To-RunRelativePath $metadataPath $OutputDir
$comparisonRelativePath = To-RunRelativePath $comparisonReport $OutputDir
Assert-HplcStagedPackageComplete `
  $OutputDir `
  $requiredRelativePaths `
  $metadataRelativePath `
  $comparisonRelativePath `
  $ExportTemplateComparison
Commit-HplcOutputPackage `
  $OutputDir `
  $finalOutputDir `
  $transactionBackupDir `
  $replaceExistingOutput `
  $requiredRelativePaths `
  $metadataRelativePath `
  $comparisonRelativePath `
  $ExportTemplateComparison

Write-Output ("OUTPUT_DIR=" + (Split-Path -Leaf $finalOutputDir))
Write-Output ("OPJU=" + (To-RunRelativePath $outputOpju $OutputDir))
Write-Output ("DATA=" + (To-RunRelativePath (Join-Path $dataDir 'final_calibration_data.tsv') $OutputDir))
Write-Output ("METADATA=" + (To-RunRelativePath $metadataPath $OutputDir))
Write-Output ("LOG=" + (To-RunRelativePath $script:LogPath $OutputDir))
if ($ExportTemplateComparison) {
  Write-Output ("COMPARISON_REPORT=" + (To-RunRelativePath $comparisonReport $OutputDir))
}
foreach ($s in $series) {
  $fit = $fitMap[$s.Page]
  Write-Output ("PNG=" + (To-RunRelativePath $generatedPreviewMap[$s.Page] $OutputDir))
  Write-Output ("TIF=" + (To-RunRelativePath $generatedTifMap[$s.Page] $OutputDir))
  Write-Output ($s.Page + "_FIT=slope=" + $fit.Slope.ToString('0.0000', [Globalization.CultureInfo]::InvariantCulture) + ";intercept=" + $fit.Intercept.ToString('0.0000', [Globalization.CultureInfo]::InvariantCulture) + ";r2=" + $fit.R2.ToString('0.000000', [Globalization.CultureInfo]::InvariantCulture))
}
