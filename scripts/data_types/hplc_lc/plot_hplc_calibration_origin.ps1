param(
  [Parameter(Mandatory=$true)]
  [string]$TemplateOpju,
  [string]$OutputDir = '',
  [string]$Stamp = '',
  [bool]$Headless = $true,
  [bool]$CloseOrigin = $true,
  [bool]$ExportTemplateComparison = $true,
  [bool]$EnforceTemplateComparison = $true,
  [double]$ComparisonMeanTolerance = 3.0,
  [double]$ComparisonMaxTolerance = 80.0,
  [switch]$KeepIntermediate
)

$ErrorActionPreference = 'Stop'

function To-OriginPath([string]$Path) {
  return ($Path -replace '\\', '/')
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
      $line = ($rawLine -replace '#.*$', '').TrimEnd()
      if ([string]::IsNullOrWhiteSpace($line)) { continue }
      if (($rawLine -notmatch '^\s') -and ($line -match '^([^:]+):\s*$')) {
        $section = $Matches[1].Trim()
        continue
      }
      if (($section -eq 'paths') -and ($line -match '^(output_root|output):\s*(.+)$')) {
        $value = $Matches[2].Trim().Trim('"').Trim([char]39)
        if (-not [string]::IsNullOrWhiteSpace($value)) {
          return Resolve-RunPath $value $ProjectRoot
        }
      }
    }
  }
  $outputName = [string]([char]36755) + [string]([char]20986)
  return [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $ProjectRoot) $outputName))
}

function Assert-UnderOrEqual([string]$Path, [string]$Parent, [string]$Message) {
  $resolvedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $resolvedParent = [System.IO.Path]::GetFullPath($Parent).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  if ($resolvedPath.Equals($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) { return }
  $prefix = $resolvedParent + [System.IO.Path]::DirectorySeparatorChar
  if ($resolvedPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { return }
  throw $Message
}

function Has-AssistantTrace([string]$Text) {
  if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
  return ($Text -match '(?i)(codex|chatgpt|openai)')
}

function New-NeutralOriginStage([string]$Stamp, [string]$ProjectRoot) {
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
    $stagePath = [System.IO.Path]::GetFullPath((Join-Path $base ('hplc_' + $Stamp)))
    $key = $stagePath.ToLowerInvariant()
    if ($seen.ContainsKey($key)) { continue }
    $seen[$key] = $true
    if (Has-AssistantTrace $stagePath) { continue }
    New-Item -ItemType Directory -Path $stagePath -Force | Out-Null
    return $stagePath
  }
  throw 'Could not create an Origin staging path without assistant/tool labels.'
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

function Close-OriginProcessesStartedByScript([int[]]$BeforePids) {
  $known = @{}
  foreach ($pidValue in $BeforePids) { $known[$pidValue] = $true }
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline) {
    $newProcesses = @(Get-Process -Name Origin* -ErrorAction SilentlyContinue | Where-Object { -not $known.ContainsKey([int]$_.Id) })
    if ($newProcesses.Count -eq 0) { return }
    Start-Sleep -Milliseconds 500
  }
  $newProcesses = @(Get-Process -Name Origin* -ErrorAction SilentlyContinue | Where-Object { -not $known.ContainsKey([int]$_.Id) })
  foreach ($process in $newProcesses) {
    Write-Log ('Forcing leftover script-owned Origin process to close: PID=' + $process.Id)
    try { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue } catch {}
  }
}

function Normalize-TifDpi([string]$Path, [int]$Dpi) {
  if (-not (Test-Path -LiteralPath $Path)) { return }
  try {
    Add-Type -AssemblyName System.Drawing -ErrorAction Stop
    $source = [System.Drawing.Image]::FromFile($Path)
    $bitmap = $null
    $graphics = $null
    try {
      $bitmap = New-Object System.Drawing.Bitmap $source.Width, $source.Height
      $bitmap.SetResolution($Dpi, $Dpi)
      $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
      $graphics.DrawImage($source, 0, 0, $source.Width, $source.Height)
      $tmpPath = $Path + '.tmp.tif'
      if (Test-Path -LiteralPath $tmpPath) { Remove-Item -LiteralPath $tmpPath -Force }
      $bitmap.Save($tmpPath, [System.Drawing.Imaging.ImageFormat]::Tiff)
    }
    finally {
      if ($graphics) { $graphics.Dispose() }
      if ($bitmap) { $bitmap.Dispose() }
      if ($source) { $source.Dispose() }
    }
    Move-Item -LiteralPath $tmpPath -Destination $Path -Force
  }
  catch {
    Write-Log ("TIF DPI normalization skipped for " + $Path + ": " + $_.Exception.Message)
  }
}

function Export-GraphPng($App, [string]$PageName, [string]$Directory, [string]$BaseName) {
  New-Item -ItemType Directory -Path $Directory -Force | Out-Null
  $path = Join-Path $Directory ($BaseName + '.png')
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
  $App.Execute('win -a ' + $PageName + '; expGraph type:=png path:="' + (To-OriginPath $Directory) + '" filename:="' + $BaseName + '" overwrite:=replace;') | Out-Null
  Wait-ForOutputFile $path
  return $path
}

function Export-GraphTif($App, [string]$PageName, [string]$Directory, [string]$BaseName, [int]$ExportDpi) {
  New-Item -ItemType Directory -Path $Directory -Force | Out-Null
  $path = Join-Path $Directory ($BaseName + '.tif')
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
  $App.Execute('win -a ' + $PageName + '; expGraph type:=tif path:="' + (To-OriginPath $Directory) + '" filename:="' + $BaseName + '" overwrite:=replace;') | Out-Null
  Wait-ForOutputFile $path
  Normalize-TifDpi $path $ExportDpi
  return $path
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

function Compare-ImageFiles([string]$TemplatePath, [string]$GeneratedPath, [double]$MeanTolerance, [double]$MaxTolerance) {
  if (-not (Test-Path -LiteralPath $TemplatePath)) { throw "Template image missing: $TemplatePath" }
  if (-not (Test-Path -LiteralPath $GeneratedPath)) { throw "Generated image missing: $GeneratedPath" }
  Add-Type -AssemblyName System.Drawing -ErrorAction Stop
  $templateImage = [System.Drawing.Bitmap]::FromFile($TemplatePath)
  $generatedImage = [System.Drawing.Bitmap]::FromFile($GeneratedPath)
  try {
    $sameSize = ($templateImage.Width -eq $generatedImage.Width) -and ($templateImage.Height -eq $generatedImage.Height)
    if (-not $sameSize) {
      return [pscustomobject]@{
        Pass = $false
        TemplateWidth = $templateImage.Width
        TemplateHeight = $templateImage.Height
        GeneratedWidth = $generatedImage.Width
        GeneratedHeight = $generatedImage.Height
        Samples = 0
        MeanAbsDelta = ''
        MaxAbsDelta = ''
        Status = 'dimension_mismatch'
      }
    }
    $sampleColumns = [Math]::Min(101, $templateImage.Width)
    $sampleRows = [Math]::Min(101, $templateImage.Height)
    $sampleCount = 0
    $sumDelta = 0.0
    $maxDelta = 0
    for ($iy = 0; $iy -lt $sampleRows; $iy++) {
      if ($sampleRows -eq 1) { $y = 0 } else { $y = [int][Math]::Round($iy * ($templateImage.Height - 1) / ($sampleRows - 1)) }
      for ($ix = 0; $ix -lt $sampleColumns; $ix++) {
        if ($sampleColumns -eq 1) { $x = 0 } else { $x = [int][Math]::Round($ix * ($templateImage.Width - 1) / ($sampleColumns - 1)) }
        $a = $templateImage.GetPixel($x, $y)
        $b = $generatedImage.GetPixel($x, $y)
        foreach ($delta in @([Math]::Abs($a.R - $b.R), [Math]::Abs($a.G - $b.G), [Math]::Abs($a.B - $b.B))) {
          $sumDelta += $delta
          if ($delta -gt $maxDelta) { $maxDelta = $delta }
        }
        $sampleCount += 1
      }
    }
    $meanDelta = $sumDelta / ($sampleCount * 3)
    $passed = ($meanDelta -le $MeanTolerance) -and ($maxDelta -le $MaxTolerance)
    return [pscustomobject]@{
      Pass = $passed
      TemplateWidth = $templateImage.Width
      TemplateHeight = $templateImage.Height
      GeneratedWidth = $generatedImage.Width
      GeneratedHeight = $generatedImage.Height
      Samples = $sampleCount
      MeanAbsDelta = $meanDelta.ToString('0.0000', [Globalization.CultureInfo]::InvariantCulture)
      MaxAbsDelta = $maxDelta
      Status = if ($passed) { 'pass' } else { 'pixel_delta_exceeds_tolerance' }
    }
  }
  finally {
    $templateImage.Dispose()
    $generatedImage.Dispose()
  }
}

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path (Get-ProjectOutputRoot $projectRoot) 'hplc_calibration_origin'
}
$OutputDir = Resolve-RunPath $OutputDir $projectRoot
$projectOutputRoot = Get-ProjectOutputRoot $projectRoot
Assert-UnderOrEqual $OutputDir $projectOutputRoot ("OutputDir must stay under the configured output root: " + $OutputDir)
if ([string]::IsNullOrWhiteSpace($Stamp)) {
  $Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
}
if ($Stamp -match '(?i)(codex|chatgpt|openai)') {
  throw "Stamp must not include assistant or tool labels."
}

$ExportDpi = 600
$templateOpjuPath = Resolve-RunPath $TemplateOpju $projectRoot
if (-not (Test-Path -LiteralPath $templateOpjuPath)) {
  throw ("HPLC calibration template OPJU not found: " + (Split-Path -Leaf $templateOpjuPath))
}

$dataDir = Join-Path $OutputDir 'processed_data'
$originDir = Join-Path $OutputDir 'origin_files'
$previewDir = Join-Path $OutputDir 'figures_preview'
$tifDir = Join-Path $OutputDir 'figures_tif'
$metadataDir = Join-Path $OutputDir 'metadata\HPLC_calibration_curves'
$comparisonDir = Join-Path $OutputDir 'template_comparison'
$templatePreviewDir = Join-Path $comparisonDir 'template_preview'
$templateTifDir = Join-Path $comparisonDir 'template_tif'
$logDir = Join-Path $OutputDir 'logs'
$stageRoot = New-NeutralOriginStage $Stamp $projectRoot
$stageTemplateDir = Join-Path $stageRoot 'origin_templates'
New-Item -ItemType Directory -Path $dataDir, $originDir, $previewDir, $tifDir, $metadataDir, $comparisonDir, $logDir, $stageTemplateDir -Force | Out-Null

$script:LogPath = Join-Path $logDir 'origin_run_log.txt'
if (Test-Path -LiteralPath $script:LogPath) { Remove-Item -LiteralPath $script:LogPath -Force }

$workingTemplate = Join-Path $stageRoot ('template_working_copy_' + $Stamp + '.opju')
$outputOpju = Join-Path $originDir ('HPLC_calibration_curves_' + $Stamp + '.opju')
$comparisonReport = Join-Path $comparisonDir 'comparison_report.tsv'
if (Test-Path -LiteralPath $outputOpju) { Remove-Item -LiteralPath $outputOpju -Force }
if (Test-Path -LiteralPath $comparisonReport) { Remove-Item -LiteralPath $comparisonReport -Force }

$points = @(
  @{ Point='S1'; X=0.05; Sulfoxide=67.848; Sulfone=22.553; Sulfide=504.621 },
  @{ Point='S2'; X=0.10; Sulfoxide=145.164; Sulfone=47.271; Sulfide=1054.405 },
  @{ Point='S3'; X=0.25; Sulfoxide=379.292; Sulfone=127.723; Sulfide=2863.680 },
  @{ Point='S4'; X=0.50; Sulfoxide=755.397; Sulfone=252.807; Sulfide=5612.688 },
  @{ Point='S5'; X=1.00; Sulfoxide=1505.311; Sulfone=502.702; Sulfide=11264.664 },
  @{ Point='S6'; X=1.50; Sulfoxide=2208.395; Sulfone=739.446; Sulfide=16408.434 },
  @{ Point='S7'; X=2.00; Sulfoxide=2959.872; Sulfone=991.845; Sulfide=21670.291 }
)

$yTitlePower3 = '\b(Peak area \(40)10\+(3) mAU*s\(41))'
$yTitlePower2 = '\b(Peak area \(40)10\+(2) mAU*s\(41))'

$series = @(
  @{ Key='Sulfoxide'; Page='Cal_Sulfoxide'; TemplateGraph='Cal_Sulfoxide'; Name='Anisole sulfoxide'; YTo=3200; YInc=500; YDivideBy=1000; YTitle=$yTitlePower3; LegendLeft=1585; LegendTop=880; LegendWidth=2429; LegendHeight=826; XTitleLeft=1927; XTitleTop=4487; XTitleWidth=2835; XTitleHeight=338; YTitleLeft=362; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204 },
  @{ Key='Sulfone'; Page='Cal_Sulfone'; TemplateGraph='Cal_Sulfone'; Name='Anisole sulfone'; YTo=1100; YInc=200; YDivideBy=100; YTitle=$yTitlePower2; LegendLeft=1740; LegendTop=808; LegendWidth=2308; LegendHeight=826; XTitleLeft=1927; XTitleTop=4487; XTitleWidth=2835; XTitleHeight=338; YTitleLeft=413; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204 },
  @{ Key='Sulfide'; Page='Cal_Sulfide'; TemplateGraph='Cal_Sulfide'; Name='Anisole sulfide'; YTo=23000; YInc=5000; YDivideBy=1000; YTitle=$yTitlePower3; LegendLeft=1578; LegendTop=850; LegendWidth=2457; LegendHeight=760; XTitleLeft=1927; XTitleTop=4487; XTitleWidth=2835; XTitleHeight=338; YTitleLeft=413; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204 }
)

$masterHeader = 'Point' + "`t" + 'Concentration_mM' + "`t" + 'Sulfoxide_area_mAU_s' + "`t" + 'Sulfone_area_mAU_s' + "`t" + 'Sulfide_area_mAU_s'
$masterLines = @($masterHeader)
foreach ($p in $points) {
  $masterLines += ($p.Point + "`t" + $p.X.ToString('0.00', [Globalization.CultureInfo]::InvariantCulture) + "`t" + $p.Sulfoxide.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture) + "`t" + $p.Sulfone.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture) + "`t" + $p.Sulfide.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture))
}
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

Copy-Item -LiteralPath $templateOpjuPath -Destination $workingTemplate -Force

$templatePreviewMap = @{}
$generatedPreviewMap = @{}
$generatedTifMap = @{}
$fitMap = @{}
$originPidsBefore = Get-OriginProcessIds

$app = New-Object -ComObject Origin.Application
$app.Visible = if ($Headless) { 0 } else { 1 }
try {
  Write-Log 'Origin.Application launched'
  Write-Log ('TemplateOpju=' + [System.IO.Path]::GetFileName($templateOpjuPath))
  Write-Log ('OutputDir=' + [System.IO.Path]::GetFileName($OutputDir))
  $app.Load($workingTemplate) | Out-Null

  foreach ($s in $series) {
    $templateBase = 'hplc_' + $s.TemplateGraph + '_' + $Stamp
    $templatePath = Join-Path $stageTemplateDir ($templateBase + '.otpu')
    $app.Execute('win -a ' + $s.TemplateGraph + ';') | Out-Null
    Apply-HplcYAxisStyle $app $s.TemplateGraph $s.YDivideBy $s.YTitle
    foreach ($expr in @('page.width', 'page.height', 'page.nlayers', 'layer.left', 'layer.top', 'layer.width', 'layer.height', 'layer.x.thickness', 'layer.y.thickness')) {
      ($s.TemplateGraph + ':' + $expr + '=' + $app.Evaluate($expr)) | Add-Content -LiteralPath $script:LogPath -Encoding UTF8
    }
    if (Test-Path -LiteralPath $templatePath) { Remove-Item -LiteralPath $templatePath -Force }
    $app.Execute('template_saveas pg:=' + $s.TemplateGraph + ' category:="HPLC_Calibration" template:="' + $templateBase + '" filepath:="' + (To-OriginPath $stageTemplateDir) + '" emf:=0 bmp:=1 loadsys:=0;') | Out-Null
    Wait-ForOutputFile $templatePath
    $s.TemplatePath = $templatePath
    if ($ExportTemplateComparison) {
      $templatePreviewMap[$s.Page] = Export-GraphPng $app $s.TemplateGraph $templatePreviewDir ($s.Page + '_template')
      Export-GraphTif $app $s.TemplateGraph $templateTifDir ($s.Page + '_template') $ExportDpi | Out-Null
    }
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
  foreach ($s in $series) {
    $baseName = $s.Page + '_' + $Stamp
    $generatedPreviewMap[$s.Page] = Export-GraphPng $app $s.Page $previewDir $baseName
    $generatedTifMap[$s.Page] = Export-GraphTif $app $s.Page $tifDir $baseName $ExportDpi
  }
}
finally {
  if ($CloseOrigin) {
    try { $app.Exit() | Out-Null } catch {}
    Close-OriginProcessesStartedByScript $originPidsBefore
  }
}

if ($ExportTemplateComparison) {
  $comparisonLines = @(
    'Page' + "`t" + 'TemplatePng' + "`t" + 'GeneratedPng' + "`t" + 'TemplateWidth' + "`t" + 'TemplateHeight' + "`t" + 'GeneratedWidth' + "`t" + 'GeneratedHeight' + "`t" + 'SampleCount' + "`t" + 'MeanAbsDelta' + "`t" + 'MaxAbsDelta' + "`t" + 'Status'
  )
  $failedComparisons = @()
  foreach ($s in $series) {
    $result = Compare-ImageFiles $templatePreviewMap[$s.Page] $generatedPreviewMap[$s.Page] $ComparisonMeanTolerance $ComparisonMaxTolerance
    $comparisonLines += (
      $s.Page + "`t" +
      (To-RunRelativePath $templatePreviewMap[$s.Page] $OutputDir) + "`t" +
      (To-RunRelativePath $generatedPreviewMap[$s.Page] $OutputDir) + "`t" +
      $result.TemplateWidth + "`t" +
      $result.TemplateHeight + "`t" +
      $result.GeneratedWidth + "`t" +
      $result.GeneratedHeight + "`t" +
      $result.Samples + "`t" +
      $result.MeanAbsDelta + "`t" +
      $result.MaxAbsDelta + "`t" +
      $result.Status
    )
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

$metadataPath = Join-Path $metadataDir 'metadata.json'
$metadataPayload = [ordered]@{
  dataset_id = ('HPLC_calibration_curves_' + $Stamp)
  data_type = 'HPLC/LC exported data'
  processing_status = 'success'
  manual_check_required = $true
  origin_file = (To-RunRelativePath $outputOpju $OutputDir)
  processed_data = (To-RunRelativePath (Join-Path $dataDir 'final_calibration_data.tsv') $OutputDir)
  figure_tif = @($series | ForEach-Object { To-RunRelativePath $generatedTifMap[$_.Page] $OutputDir })
  preview_png = @($series | ForEach-Object { To-RunRelativePath $generatedPreviewMap[$_.Page] $OutputDir })
  template_comparison_report = if ($ExportTemplateComparison) { To-RunRelativePath $comparisonReport $OutputDir } else { $null }
  manual_check_items = @(
    'confirm HPLC calibration point identity, integration boundaries, and calibration applicability before quantitative use',
    'confirm Origin graph formatting against the accepted HPLC calibration template comparison report'
  )
  forbidden_claims = @(
    'do not infer product identity, yield, selectivity, or mechanism from calibration-curve plotting alone'
  )
}
($metadataPayload | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $metadataPath -Encoding UTF8

Write-Output ("OUTPUT_DIR=" + (Split-Path -Leaf $OutputDir))
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
