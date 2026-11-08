param(
  [Parameter(Mandatory=$false)]
  [string]$ReferenceOpju = '',

  [Parameter(Mandatory=$false)]
  [string]$ReferenceGraph = 'Graph4',

  [Parameter(Mandatory=$true)]
  [string]$OutputOpju,

  [Parameter(Mandatory=$true)]
  [string]$ExportDir,

  [Parameter(Mandatory=$true)]
  [string]$AllowedOutputRoot,

  [Parameter(Mandatory=$true)]
  [array]$Groups,

  [string]$DefaultPlotType = '200',

  [switch]$AllowRunningOrigin,

  [switch]$Headless,

  [switch]$RefreshReferenceStyle,

  [switch]$KeepIntermediate,

  [switch]$Force,

  [switch]$CloseOrigin
)

$ErrorActionPreference = 'Stop'
$AxisTitleFont = 71
$AxisTitleSize = 36

function To-OriginPath([string]$Path) {
  return ($Path -replace '\\','/')
}

function Get-FullPath([string]$Path) {
  return [System.IO.Path]::GetFullPath($Path)
}

function Test-PathUnderOrEqual([string]$Path, [string]$Root) {
  $fullPath = (Get-FullPath $Path).TrimEnd('\', '/')
  $fullRoot = (Get-FullPath $Root).TrimEnd('\', '/')
  return $fullPath.Equals($fullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $fullPath.StartsWith($fullRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-NoReparsePointInPath([string]$Path, [string]$Label) {
  $current = Get-FullPath $Path
  while ($current) {
    if (Test-Path -LiteralPath $current) {
      $item = Get-Item -LiteralPath $current -Force
      if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "$Label traverses a symlink, junction, or reparse point: $current"
      }
    }
    $parent = Split-Path -Parent $current
    if (-not $parent -or $parent -eq $current) { break }
    $current = $parent
  }
}

function Assert-SafeOutputPath([string]$Path, [string]$Root, [string]$Label) {
  if (-not (Test-PathUnderOrEqual $Path $Root)) {
    throw "$Label must stay under AllowedOutputRoot: $Path"
  }
  Assert-NoReparsePointInPath $Path $Label
  if (Test-Path -LiteralPath $Path -PathType Container) {
    throw "$Label must be a file, not a directory: $Path"
  }
}

function Assert-SafePageName([string]$PageName) {
  if ([string]::IsNullOrWhiteSpace($PageName) -or
      $PageName -in @('.', '..') -or
      $PageName -match '[<>:"/\\|?*\x00-\x1F]' -or
      $PageName.EndsWith('.') -or
      $PageName.EndsWith(' ')) {
    throw "PageName must be one safe filename component: $PageName"
  }
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

function Require-File([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Required file not found: $Path"
  }
}

function Find-DefaultReferenceOpju {
  $scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $projectRoot = Split-Path -Parent (Split-Path -Parent $scriptRoot)
  $relativeReference = 'templates\origin_styles\reference_opju\XRD.opju'
  $candidates = @(
    Join-Path $projectRoot $relativeReference,
    Join-Path (Get-Location).Path $relativeReference
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
  }
  throw "Default project-local Origin reference OPJU not found: $relativeReference"
}

function Get-GroupValue($Group, [string]$Name, $Default = $null) {
  if ($Group -is [hashtable] -and $Group.ContainsKey($Name)) { return $Group[$Name] }
  $prop = $Group.PSObject.Properties[$Name]
  if ($prop) { return $prop.Value }
  return $Default
}

function Convert-ToBoolean($Value, [bool]$Default) {
  if ($null -eq $Value) { return $Default }
  if ($Value -is [bool]) { return [bool]$Value }
  $text = ([string]$Value).Trim().ToLowerInvariant()
  if ($text -in @('1','true','yes','on')) { return $true }
  if ($text -in @('0','false','no','off')) { return $false }
  return $Default
}

function Get-HeaderLabels([string]$DataFile, [int]$ColumnCount) {
  $header = Get-Content -LiteralPath $DataFile -Encoding UTF8 -TotalCount 1
  if (-not $header) { return @() }
  $parts = $header -split "`t|,"
  if ($parts.Count -lt 2) { return @() }
  $end = [Math]::Min($ColumnCount - 1, $parts.Count - 1)
  return @($parts[1..$end] | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Parse-XYPairs([string]$Spec, [int]$ColumnCount) {
  $pairs = New-Object System.Collections.Generic.List[object]
  if ([string]::IsNullOrWhiteSpace($Spec)) { return @() }
  foreach ($part in ($Spec -split ';')) {
    $item = [string]$part
    if ([string]::IsNullOrWhiteSpace($item)) { continue }
    $pieces = @($item -split ':')
    if ($pieces.Count -ne 2) { throw "Invalid XYPairs entry: $item" }
    $x = [int]$pieces[0]
    $y = [int]$pieces[1]
    if ($x -lt 1 -or $x -gt $ColumnCount -or $y -lt 1 -or $y -gt $ColumnCount) {
      throw "XYPairs entry $item is outside ColumnCount $ColumnCount."
    }
    $pairs.Add([pscustomobject]@{ X = $x; Y = $y }) | Out-Null
  }
  return @($pairs.ToArray())
}

function Read-DelimitedTable([string]$DataFile) {
  $lines = @(Get-Content -LiteralPath $DataFile -Encoding UTF8)
  if ($lines.Count -eq 0) { return [pscustomobject]@{ Headers = @(); Rows = @() } }
  $delimiter = if ($lines[0] -like "*`t*") { "`t" } else { "," }
  $rows = @($lines | ConvertFrom-Csv -Delimiter $delimiter)
  $headers = @()
  if ($rows.Count -gt 0) {
    $headers = @($rows[0].PSObject.Properties.Name)
  } else {
    $headers = @($lines[0] -split [regex]::Escape($delimiter))
  }
  return [pscustomobject]@{ Headers = $headers; Rows = $rows }
}

function Set-OriginWorksheetCell($app, [int]$ColumnIndex, [int]$RowNumber, [string]$Value) {
  if ([string]::IsNullOrWhiteSpace($Value)) { return }
  try {
    $number = [double]::Parse($Value, [Globalization.CultureInfo]::InvariantCulture)
    $text = $number.ToString('G17', [Globalization.CultureInfo]::InvariantCulture)
    $app.Execute('wcol(' + $ColumnIndex + ')[' + $RowNumber + ']=' + $text + ';') | Out-Null
    return
  } catch {}
  $escaped = $Value.Replace('"', '\"').Replace("`r", ' ').Replace("`n", ' ')
  $app.Execute('wcol(' + $ColumnIndex + ')[' + $RowNumber + ']$="' + $escaped + '";') | Out-Null
}

function Initialize-OriginDataWorkbook($app, [string]$BookName, [string]$DisplayName, [array]$Headers, [array]$Rows, [int]$ColumnCount) {
  $sheetName = Convert-ToSafeOriginName ([System.IO.Path]::GetFileNameWithoutExtension($DisplayName)) 'Data'
  $safeDisplayName = Escape-OriginText $DisplayName
  $app.Execute('newbook name:="' + $BookName + '";') | Out-Null
  $app.Execute('page.longname$="' + $safeDisplayName + '"; page.comments$=""; page.comment$="";') | Out-Null
  $app.Execute('wks.name$="' + $sheetName + '"; wks.longname$="' + $safeDisplayName + '"; wks.comments$=""; wks.comment$=""; wks.ncols=' + $ColumnCount + '; wks.nrows=' + $Rows.Count + ';') | Out-Null
  $typeCmd = 'wks.col1.type=4;'
  for ($i = 2; $i -le $ColumnCount; $i++) {
    $typeCmd += " wks.col$i.type=1;"
  }
  $app.Execute($typeCmd) | Out-Null
  for ($i = 1; $i -le $ColumnCount; $i++) {
    $header = if (($i - 1) -lt $Headers.Count) { [string]$Headers[$i - 1] } else { 'Column_' + $i }
    $escapedHeader = Escape-OriginText $header
    $app.Execute('wks.col' + $i + '.lname$="' + $escapedHeader + '"; wks.col' + $i + '.comment$="";') | Out-Null
  }
  # newbook may use BookName as a long name; COM requires the actual short name.
  $target = '[' + [string]$app.LTStr('%H') + ']' + $sheetName
  for ($colIndex = 1; $colIndex -le $ColumnCount; $colIndex++) {
    if (($colIndex - 1) -ge $Headers.Count) { continue }
    $name = [string]$Headers[$colIndex - 1]
    $numericValues = New-Object System.Collections.Generic.List[double]
    $completeNumericColumn = $Rows.Count -gt 0
    foreach ($row in $Rows) {
      $value = [string]$row.$name
      if ([string]::IsNullOrWhiteSpace($value)) { $completeNumericColumn = $false; break }
      try {
        $number = [double]::Parse($value, [Globalization.CultureInfo]::InvariantCulture)
        if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
          $completeNumericColumn = $false
          break
        }
        $numericValues.Add($number) | Out-Null
      } catch {
        $completeNumericColumn = $false
        break
      }
    }
    if ($completeNumericColumn) {
      # COM accepts a SAFEARRAY with zero-based starting row/column.
      # https://docs.originlab.com/com/classes/application/putworksheet/
      $written = $false
      try { $written = [bool]$app.PutWorksheet($target, $numericValues.ToArray(), 0, ($colIndex - 1)) } catch {}
      if ($written) { continue }
      Write-Output ('WORKSHEET_COLUMN_FALLBACK=' + $colIndex)
    }
    # Preserve the existing blank/text/nonfinite handling for mixed columns.
    for ($rowIndex = 0; $rowIndex -lt $Rows.Count; $rowIndex++) {
      $row = $Rows[$rowIndex]
      Set-OriginWorksheetCell $app $colIndex ($rowIndex + 1) ([string]$row.$name)
    }
  }
}

function Sanitize-ProjectPages($app) {
  $app.Execute('doc -e W { page.comments$=""; page.comment$=""; wks.comments$=""; wks.comment$=""; }; doc -e P { page.comments$=""; page.comment$=""; };') | Out-Null
}

function Test-CurrentText([string]$Text, [array]$CurrentLabels) {
  if ([string]::IsNullOrWhiteSpace($Text)) { return $true }
  if ($Text -match '2.?theta|2Theta|degree|Intensity|a\.u|%\(\?X\)|%\(\?Y\)') { return $true }
  foreach ($label in $CurrentLabels) {
    if ($label -and $Text -like ('*' + $label + '*')) { return $true }
  }
  return $false
}

function Format-BoldText([string]$Text) {
  if ([string]::IsNullOrWhiteSpace($Text)) { return $Text }
  $formatted = Format-ChemicalFormulaSubscripts $Text
  if ($formatted -match '\\b\(') { return $formatted }
  return '\b(' + $formatted + ')'
}

function Format-LegendLabel([string]$Text) {
  if ($null -eq $Text) { return '' }
  return Format-ChemicalFormulaSubscripts (($Text -replace "`r|`n", ' ').Trim())
}

function Test-ChemicalFormulaToken([string]$Token) {
  if ([string]::IsNullOrWhiteSpace($Token)) { return $false }
  if ($Token -match '\\-\(') { return $false }
  if ($Token -notmatch '\d') { return $false }
  if ($Token -cnotmatch '[A-Z]') { return $false }
  if ($Token -cmatch '\d+[a-z]') { return $false }
  if ($Token -cmatch '^(XRD|XPS|EPR|FTIR|PL|Raman)\d*$') { return $false }
  return $true
}

function Format-ChemicalFormulaSubscripts([string]$Text) {
  if ([string]::IsNullOrWhiteSpace($Text)) { return $Text }
  $tokenPattern = '\b[A-Za-z][A-Za-z0-9()]*\b'
  return [regex]::Replace($Text, $tokenPattern, {
    param($match)
    $token = [string]$match.Value
    if (-not (Test-ChemicalFormulaToken $token)) { return $token }
    return [regex]::Replace($token, '(?<=[A-Za-z\)])(\d+)', '\-($1)')
  })
}

function Set-OriginSeriesLabels($app, [array]$Labels, [array]$XYPairs = @()) {
  for ($i = 0; $i -lt $Labels.Count; $i++) {
    $column = if ($XYPairs.Count -gt 0) { [int]$XYPairs[$i].Y } else { $i + 2 }
    $name = Escape-OriginText (Format-BoldText (Format-LegendLabel $Labels[$i]))
    if (-not $app.Execute('wks.col' + $column + '.lname$="' + $name + '";')) {
      throw "Could not set plotted column $column sample label."
    }
  }
}

function Add-DirectCurveLabels($app, [string]$PageName, [array]$Labels, $Style, [string]$DataFile, [int]$ColumnCount, [array]$XYPairs = @()) {
  $rows = Import-Csv -LiteralPath $DataFile
  if (-not $rows -or $ColumnCount -lt 2) { return }
  $columns = @($rows[0].PSObject.Properties.Name)
  if ($columns.Count -lt $ColumnCount) { return }
  $plotPairs = @()
  if ($XYPairs -and $XYPairs.Count -gt 0) {
    $plotPairs = @($XYPairs)
  } else {
    for ($i = 1; $i -lt $ColumnCount; $i++) {
      $plotPairs += [pscustomobject]@{ X = 1; Y = ($i + 1) }
    }
  }
  $app.Execute('win -a ' + $PageName + '; layer -s 1;') | Out-Null
  $layer = $app.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $app.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { return }
  $xTo = [double]$app.Evaluate('layer.x.to')
  $xRange = $xTo - [double]$app.Evaluate('layer.x.from')
  $xOffset = if ($xRange -gt 0) { $xRange * 0.16 } else { 0.10 }
  $yRange = [double]$app.Evaluate('layer.y.to') - [double]$app.Evaluate('layer.y.from')
  $yLabelOffset = if ($yRange -gt 0) { $yRange * 0.035 } else { 0 }
  for ($i = 0; $i -lt $plotPairs.Count; $i++) {
    if ($i -ge $Labels.Count) { continue }
    $pair = $plotPairs[$i]
    $xColumn = $columns[[int]$pair.X - 1]
    $yColumn = $columns[[int]$pair.Y - 1]
    $point = $null
    $tailValues = New-Object System.Collections.Generic.List[double]
    $tailStart = [Math]::Max(0, $rows.Count - [Math]::Max(25, [int]($rows.Count * 0.04)))
    for ($rowIndex = $rows.Count - 1; $rowIndex -ge 0; $rowIndex--) {
      $row = $rows[$rowIndex]
      $xText = [string]$row.$xColumn
      $yText = [string]$row.$yColumn
      if ([string]::IsNullOrWhiteSpace($xText) -or [string]::IsNullOrWhiteSpace($yText)) { continue }
      try {
        $xVal = [double]::Parse($xText, [Globalization.CultureInfo]::InvariantCulture)
        $yVal = [double]::Parse($yText, [Globalization.CultureInfo]::InvariantCulture)
        if ($rowIndex -ge $tailStart) { $tailValues.Add($yVal) | Out-Null }
        $point = @{ X = $xVal; Y = $yVal }
        break
      } catch {}
    }
    if (-not $point) { continue }
    for ($rowIndex = $tailStart; $rowIndex -lt $rows.Count; $rowIndex++) {
      $row = $rows[$rowIndex]
      $yText = [string]$row.$yColumn
      if ([string]::IsNullOrWhiteSpace($yText)) { continue }
      try {
        $tailValues.Add([double]::Parse($yText, [Globalization.CultureInfo]::InvariantCulture)) | Out-Null
      } catch {}
    }
    $labelY = [double]$point.Y
    if ($tailValues.Count -gt 0) {
      $sortedTail = @($tailValues.ToArray() | Sort-Object)
      $labelY = [double]$sortedTail[[int][Math]::Floor($sortedTail.Count / 2)]
    }
    try {
      $labelText = Format-BoldText ([string]$Labels[$i])
      $safeName = 'DL' + ($i + 1)
      $escaped = $labelText.Replace('"', '\"')
      $labelX = [Math]::Min([double]($point.X - $xOffset), [double]($xTo - $xOffset))
      $xValue = [string]$labelX
      $yValue = [string]([double]($labelY + $yLabelOffset))
      $app.Execute('label -r ' + $safeName + ';') | Out-Null
      $app.Execute('label -n ' + $safeName + ' "' + $escaped + '"; ' + $safeName + '.x=' + $xValue + '; ' + $safeName + '.y=' + $yValue + '; ' + $safeName + '.font=' + $Style.LegendFont + '; ' + $safeName + '.fsize=' + $Style.LegendSize + '; ' + $safeName + '.bold=1; ' + $safeName + '.color=' + $Style.TextColor + ';') | Out-Null
    } catch {}
  }
}

function Get-GraphObjectByName($Layer, [string]$Name) {
  for ($i = 0; $i -lt $Layer.GraphObjects.Count; $i++) {
    $obj = $Layer.GraphObjects.Item($i)
    if ($obj.Name -eq $Name) { return $obj }
  }
  return $null
}

function Set-GraphObjectFormat($Obj, [int]$Font, [double]$Size, [double]$Color) {
  if (-not $Obj) { return }
  try { $Obj.SetNumProp('font', $Font) | Out-Null } catch {}
  try { $Obj.SetNumProp('fsize', $Size) | Out-Null } catch {}
  try { $Obj.SetNumProp('color', $Color) | Out-Null } catch {}
}

function New-CachedGraph4Style {
  return [ordered]@{
    PageWidth = 6432.0
    PageHeight = 4923.0
    LayerLeft = 17.89
    LayerTop = 11.6
    LayerWidth = 68.19
    LayerHeight = 71.81
    XFrom = 5.0
    XTo = 80.0
    XStep = 10.0
    YFrom = -6000.0
    YTo = 19000.0
    YStep = 5000.0
    AxisThickness = 3.0
    XLabelFont = 71
    YLabelFont = 71
    XLabelSize = 28.0
    YLabelSize = 36.0
    XTicks = 2
    YTicks = 0
    XTitleFont = $AxisTitleFont
    YTitleFont = $AxisTitleFont
    XTitleSize = $AxisTitleSize
    YTitleSize = $AxisTitleSize
    TextColor = 1
    LegendLeft = 3569
    LegendTop = 827
    LegendWidth = 1800
    LegendHeight = 893
    LegendFont = 71
    LegendSize = 26.0
    # Okabe-Ito inspired, colorblind-accessible Origin OColor values from color(r,g,b).
    # Order avoids relying on red/green alone and keeps black available for the 8th trace.
    Palette = @(28471808, 16818150, 24354304, 16801493, 32093270, 27752908, 21161200, 16777216)
  }
}

function Get-ReferenceStyle($app, [string]$PageName) {
  $app.Execute('win -a ' + $PageName + '; layer -s 1;') | Out-Null
  $layer = $app.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $app.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { throw "Reference graph layer not found: $PageName" }

  $legend = Get-GraphObjectByName $layer 'Legend'
  $xb = Get-GraphObjectByName $layer 'XB'
  $yl = Get-GraphObjectByName $layer 'YL'

  $pageWidth = [double]$app.Evaluate('page.width')
  $pageHeight = [double]$app.Evaluate('page.height')
  $layerLeft = [double]$app.Evaluate('layer.left')
  $layerTop = [double]$app.Evaluate('layer.top')
  $layerWidth = [double]$app.Evaluate('layer.width')
  $layerHeight = [double]$app.Evaluate('layer.height')

  $style = [ordered]@{
    PageWidth = $pageWidth
    PageHeight = $pageHeight
    LayerLeft = $layerLeft
    LayerTop = $layerTop
    LayerWidth = $layerWidth
    LayerHeight = $layerHeight
    XFrom = [double]$app.Evaluate('layer.x.from')
    XTo = [double]$app.Evaluate('layer.x.to')
    XStep = [double]$app.Evaluate('layer.x.inc')
    YFrom = [double]$app.Evaluate('layer.y.from')
    YTo = [double]$app.Evaluate('layer.y.to')
    YStep = [double]$app.Evaluate('layer.y.inc')
    AxisThickness = [double]$app.Evaluate('layer.x.thickness')
    XLabelFont = [int]$app.Evaluate('layer.x.label.font')
    YLabelFont = [int]$app.Evaluate('layer.y.label.font')
    XLabelSize = [double]$app.Evaluate('layer.x.label.pt')
    YLabelSize = [double]$app.Evaluate('layer.y.label.pt')
    XTicks = [int]$app.Evaluate('layer.x.ticks')
    YTicks = [int]$app.Evaluate('layer.y.ticks')
    XTitleFont = $AxisTitleFont
    YTitleFont = $AxisTitleFont
    XTitleSize = $AxisTitleSize
    YTitleSize = $AxisTitleSize
    TextColor = 1
    LegendLeft = [int]($pageWidth * 0.55)
    LegendTop = [int]($pageHeight * 0.15)
    LegendWidth = [int]($pageWidth * 0.28)
    LegendHeight = [int]($pageHeight * 0.18)
    LegendFont = 71
    LegendSize = 26
    Palette = @()
  }

  if ($xb) {
    try { $style.TextColor = [double]$xb.GetNumProp('color') } catch {}
    try { $style.XTitleFont = [int]$xb.GetNumProp('font') } catch {}
  }
  if ($yl) {
    try { $style.TextColor = [double]$yl.GetNumProp('color') } catch {}
    try { $style.YTitleFont = [int]$yl.GetNumProp('font') } catch {}
  }
  $style.XTitleSize = $AxisTitleSize
  $style.YTitleSize = $AxisTitleSize
  if ($legend) {
    $style.LegendLeft = [int]$legend.Left
    $style.LegendTop = [int]$legend.Top
    $style.LegendWidth = [int]$legend.Width
    $style.LegendHeight = [int]$legend.Height
    try { $style.LegendFont = [int]$legend.GetNumProp('font') } catch {}
    try { $style.LegendSize = [double]$legend.GetNumProp('fsize') } catch {}
    try { $style.TextColor = [double]$legend.GetNumProp('color') } catch {}
  }

  $palette = New-Object System.Collections.Generic.List[double]
  $app.Execute('win -a ' + $PageName + '; layer -s 1;') | Out-Null
  $mainLayer = $app.FindGraphLayer($PageName)
  if (-not $mainLayer) { $mainLayer = $app.FindGraphLayer($PageName + '!1') }
  if ($mainLayer) {
    for ($pi = 0; $pi -lt $mainLayer.DataPlots.Count; $pi++) {
      $plot = $mainLayer.DataPlots.Item($pi)
      $lw = -1
      $color = -1
      try { $lw = [double]$plot.GetNumProp('line.width') } catch {}
      try { $color = [double]$plot.GetNumProp('color') } catch {}
      if ($lw -ge 2 -and $color -gt 0) { $palette.Add($color) }
    }
  }
  if ($palette.Count -gt 0) { $style.Palette = @($palette) }
  $app.Execute('win -a ' + $PageName + '; layer -s 1;') | Out-Null
  return $style
}

function Sanitize-ReferenceGraphForTemplate($app, [string]$PageName) {
  $app.Execute('win -a ' + $PageName + ';') | Out-Null
  $layerCount = [int]$app.Evaluate('page.nlayers')
  while ($layerCount -gt 1) {
    $app.Execute('layer -d ' + $layerCount + ';') | Out-Null
    $layerCount = [int]$app.Evaluate('page.nlayers')
  }

  $app.Execute('layer -s 1;') | Out-Null
  $layer = $app.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $app.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { return }

  for ($i = $layer.GraphObjects.Count - 1; $i -ge 0; $i--) {
    $obj = $layer.GraphObjects.Item($i)
    $name = $obj.Name
    if ($name -in @('Legend', 'XB', 'YL', 'XT', 'YR', '3D', '__BCO2', '__FRAMESRCDATAINFOS')) { continue }
    if ($name -match '^(Text|Line|_.*)$') {
      try { $obj.Destroy() | Out-Null } catch {}
    }
  }
}

function Clear-TemplateResidue($app, [string]$PageName, [array]$CurrentLabels) {
  $app.Execute('win -a ' + $PageName + ';') | Out-Null

  $layerCount = [int]$app.Evaluate('page.nlayers')
  while ($layerCount -gt 1) {
    $app.Execute('layer -d ' + $layerCount + ';') | Out-Null
    $layerCount = [int]$app.Evaluate('page.nlayers')
  }

  $app.Execute('layer -s 1;') | Out-Null
  $layer = $app.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $app.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { return }

  for ($i = $layer.GraphObjects.Count - 1; $i -ge 0; $i--) {
    $obj = $layer.GraphObjects.Item($i)
    $name = $obj.Name

    if ($name -in @('Legend', 'XB', 'YL', 'XT', 'YR', '3D', '__BCO2', '__FRAMESRCDATAINFOS')) {
      continue
    }

    $txt = ''
    try { $txt = $obj.Text } catch {}

    if ($txt) {
      if (-not (Test-CurrentText $txt $CurrentLabels)) {
        try { $obj.Destroy() | Out-Null } catch {}
      }
      continue
    }

    if ($name -match '^(Text|Line|_.*)$') {
      try { $obj.Destroy() | Out-Null } catch {}
    }
  }
}

function Apply-ReferenceStyle($app, [string]$PageName, [array]$Labels, $Style, $Group) {
  $app.Execute('win -a ' + $PageName + '; layer -s 1;') | Out-Null

  $app.Execute('page.kar=0; page.width=' + $Style.PageWidth + '; page.height=' + $Style.PageHeight + '; page.customwidth=1; page.customheight=1;') | Out-Null
  $app.Execute('layer.left=' + $Style.LayerLeft + '; layer.top=' + $Style.LayerTop + '; layer.width=' + $Style.LayerWidth + '; layer.height=' + $Style.LayerHeight + ';') | Out-Null
  $app.Execute('layer.x.thickness=' + $Style.AxisThickness + '; layer.y.thickness=' + $Style.AxisThickness + ';') | Out-Null
  $app.Execute('layer.x.label.font=' + $Style.XLabelFont + '; layer.y.label.font=' + $Style.YLabelFont + '; layer.x.label.bold=1; layer.y.label.bold=1;') | Out-Null
  $app.Execute('layer.x.label.pt=' + $Style.XLabelSize + '; layer.y.label.pt=' + $Style.YLabelSize + ';') | Out-Null
  $app.Execute('layer.x.ticks=' + $Style.XTicks + '; layer.y.ticks=' + $Style.YTicks + ';') | Out-Null

  $yTickDivisor = Get-GroupValue $Group 'YTickDivisor' $null
  if ($null -ne $yTickDivisor) {
    $divisor = [double]$yTickDivisor
    if ($divisor -le 0 -or [double]::IsNaN($divisor) -or [double]::IsInfinity($divisor)) {
      throw 'YTickDivisor must be finite and positive.'
    }
    $app.Execute('layer.y.label.divideBy=' + $divisor.ToString('R', [Globalization.CultureInfo]::InvariantCulture) + ';') | Out-Null
  }
  $axisMode = [string](Get-GroupValue $Group 'AxisMode' 'auto')
  if ($axisMode -eq 'template') {
    $app.Execute('layer.x.from=' + $Style.XFrom + '; layer.x.to=' + $Style.XTo + '; layer.x.inc=' + $Style.XStep + ';') | Out-Null
    $app.Execute('layer.y.from=' + $Style.YFrom + '; layer.y.to=' + $Style.YTo + '; layer.y.inc=' + $Style.YStep + ';') | Out-Null
  }

  foreach ($axis in @('X','Y')) {
    $from = Get-GroupValue $Group ($axis + 'From') $null
    $to = Get-GroupValue $Group ($axis + 'To') $null
    $step = Get-GroupValue $Group ($axis + 'Step') $null
    $prefix = if ($axis -eq 'X') { 'layer.x' } else { 'layer.y' }
    if ($null -ne $from) { $app.Execute($prefix + '.from=' + $from + ';') | Out-Null }
    if ($null -ne $to) { $app.Execute($prefix + '.to=' + $to + ';') | Out-Null }
    if ($null -ne $step) { $app.Execute($prefix + '.inc=' + $step + ';') | Out-Null }
  }

  $layer = $app.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $app.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { return }

  $xb = Get-GraphObjectByName $layer 'XB'
  $yl = Get-GraphObjectByName $layer 'YL'
  if ($xb) {
    $xTitle = Get-GroupValue $Group 'XTitle' $null
    if ($xTitle) { $xb.Text = Format-BoldText ([string]$xTitle) } else { $xb.Text = Format-BoldText $xb.Text }
    Set-GraphObjectFormat $xb $Style.XTitleFont $AxisTitleSize $Style.TextColor
  }
  if ($yl) {
    $yTitle = Get-GroupValue $Group 'YTitle' $null
    if ($yTitle) { $yl.Text = Format-BoldText ([string]$yTitle) } else { $yl.Text = Format-BoldText $yl.Text }
    Set-GraphObjectFormat $yl $Style.YTitleFont $AxisTitleSize $Style.TextColor
    # Keep the fixed Graph4 layer geometry, but prevent the bold 36 pt Y title
    # from falling outside the export page on large negative tick ranges.
    try {
      if ([double]$yl.Left -lt 65) { $yl.Left = 65 }
    } catch {}
  }

  $showLegend = Convert-ToBoolean (Get-GroupValue $Group 'ShowLegend' $true) $true
  $legend = Get-GraphObjectByName $layer 'Legend'
  if (-not $showLegend) {
    if ($legend) {
      try {
        $legend.Destroy() | Out-Null
        $legend = $null
      } catch {
        try { $legend.Show = 0 } catch {}
      }
    }
    $app.Execute('legend.show=0;') | Out-Null
  } else {
    if (-not $legend) {
      $app.Execute('legendupdate dest:=layer update:=reconstruct mode:=lname; page.legendtranslationmode=4;') | Out-Null
      $legend = Get-GraphObjectByName $layer 'Legend'
    }
  }
  if ($showLegend -and $legend) {
    try { $legend.Show = 1 } catch {}
    $legend.Left = [int]$Style.LegendLeft
    $legend.Top = [int]$Style.LegendTop
    $legend.Width = [int]$Style.LegendWidth
    $legend.Height = [int]([Math]::Max($Style.LegendHeight, 220 * [Math]::Max(1, $Labels.Count)))
    Set-GraphObjectFormat $legend $Style.LegendFont $Style.LegendSize $Style.TextColor
    try { $legend.SetNumProp('background', 0) | Out-Null } catch {}
    try { $legend.SetNumProp('border', 0) | Out-Null } catch {}
    try { $legend.SetNumProp('frame', 0) | Out-Null } catch {}
    try { $legend.SetNumProp('fill', 0) | Out-Null } catch {}
    try { $legend.SetNumProp('fillColor', 0) | Out-Null } catch {}
    try { $legend.SetNumProp('borderColor', 0) | Out-Null } catch {}
    try { $legend.SetNumProp('lineWidth', 0) | Out-Null } catch {}
    $app.Execute('legend.show=1; legend.background=0; legend.border=0; legend.frame=0; legend.fill=0; legend.fillColor=0; legend.borderColor=0; legend.lineWidth=0;') | Out-Null
  }

  for ($i = 0; $i -lt $layer.GraphObjects.Count; $i++) {
    $obj = $layer.GraphObjects.Item($i)
    if ($obj.Name -in @('XB','YL','Legend')) { continue }
    $txt = ''
    try { $txt = $obj.Text } catch {}
    if ($txt -and $obj.Name -notin @('XT','YR')) {
      $obj.Text = Format-BoldText $txt
      Set-GraphObjectFormat $obj $Style.LegendFont $Style.LegendSize $Style.TextColor
    }
  }

  for ($i = 0; $i -lt $layer.DataPlots.Count; $i++) {
    $plot = $layer.DataPlots.Item($i)
    try { $plot.SetNumProp('line.width', 3) | Out-Null } catch {}
    $palette = @(Get-GroupValue $Group 'Palette' $Style.Palette)
    if ($palette.Count -gt 0) {
      $color = [double]$palette[$i % $palette.Count]
      try { $plot.SetNumProp('color', $color) | Out-Null } catch {}
    }
  }

  $app.Execute('doc -e DY {set %C -lw 3;};') | Out-Null
}

function Apply-PlotPolicy($app, [string]$PageName, $Group) {
  $app.Execute('win -a ' + $PageName + '; layer -s 1;') | Out-Null
  $showYAxis = Convert-ToBoolean (Get-GroupValue $Group 'ShowYAxis' $true) $true
  $showYTicks = Convert-ToBoolean (Get-GroupValue $Group 'ShowYTicks' $true) $true
  $showYTickValues = Convert-ToBoolean (Get-GroupValue $Group 'ShowYTickValues' $true) $true
  $showXTickValues = Convert-ToBoolean (Get-GroupValue $Group 'ShowXTickValues' $true) $true
  $plotPrimitive = ([string](Get-GroupValue $Group 'PlotPrimitive' 'line')).Trim().ToLowerInvariant()
  $markerMode = ([string](Get-GroupValue $Group 'MarkerMode' 'none')).Trim().ToLowerInvariant()
  $fitOverlayMode = ([string](Get-GroupValue $Group 'FitOverlayMode' 'none')).Trim()

  $showYAxisValue = if ($showYAxis) { '1' } else { '0' }
  $showYTicksValue = if ($showYTicks) { '1' } else { '0' }
  $showYTickValuesValue = if ($showYTickValues) { '1' } else { '0' }
  $showXTickValuesValue = if ($showXTickValues) { '1' } else { '0' }

  $app.Execute('layer.y.show=' + $showYAxisValue + ';') | Out-Null
  $app.Execute('layer.y.ticks=' + $showYTicksValue + ';') | Out-Null
  if ($showYTicks) {
    $app.Execute('layer.y.ticklength=8; layer.y.mticklength=0; layer.y2.ticks=0; layer.y2.ticklength=0; layer.y2.mticklength=0; layer.y2.showLabels=0;') | Out-Null
  } else {
    $app.Execute('layer.y.ticklength=0; layer.y.mticklength=0; layer.y2.ticks=0; layer.y2.ticklength=0; layer.y2.mticklength=0; layer.y2.showLabels=0;') | Out-Null
  }
  $app.Execute('layer.y.label.show=' + $showYTickValuesValue + '; layer.y.showLabels=' + $showYTickValuesValue + ';') | Out-Null
  $app.Execute('layer.x.label.show=' + $showXTickValuesValue + '; layer.x.showLabels=' + $showXTickValuesValue + ';') | Out-Null

  $layer = $app.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $app.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { return }

  if ($markerMode -eq 'direct_labels_preferred') {
    $legend = Get-GraphObjectByName $layer 'Legend'
    if ($legend) {
      try { $legend.Destroy() | Out-Null } catch {}
    }
    $labels = @(Get-GroupValue $Group 'Labels' @())
    $dataFile = [string](Get-GroupValue $Group 'DataFile' '')
    $columnCount = [int](Get-GroupValue $Group 'ColumnCount' 0)
    $xyPairs = Parse-XYPairs ([string](Get-GroupValue $Group 'XYPairs' '')) $columnCount
    Add-DirectCurveLabels $app $PageName $labels (New-CachedGraph4Style) $dataFile $columnCount $xyPairs
  }

  for ($i = 0; $i -lt $layer.DataPlots.Count; $i++) {
    $plot = $layer.DataPlots.Item($i)
    try { $plot.SetNumProp('line.width', 3) | Out-Null } catch {}
    switch ($markerMode) {
      'none' {
        try { $plot.SetNumProp('symbol.kind', 0) | Out-Null } catch {}
      }
      'not_applicable' {
        try { $plot.SetNumProp('symbol.kind', 0) | Out-Null } catch {}
      }
      'markers_required' {
        try { $plot.SetNumProp('symbol.kind', (($i % 6) + 1)) | Out-Null } catch {}
        try { $plot.SetNumProp('symbol.size', 6) | Out-Null } catch {}
      }
      'markers_preferred' {
        try { $plot.SetNumProp('symbol.kind', (($i % 6) + 1)) | Out-Null } catch {}
        try { $plot.SetNumProp('symbol.size', 6) | Out-Null } catch {}
      }
      'markers_optional' {
        try { $plot.SetNumProp('symbol.kind', (($i % 6) + 1)) | Out-Null } catch {}
        try { $plot.SetNumProp('symbol.size', 5) | Out-Null } catch {}
      }
      'markers_optional_for_sparse_points' {
        try { $plot.SetNumProp('symbol.kind', (($i % 6) + 1)) | Out-Null } catch {}
        try { $plot.SetNumProp('symbol.size', 5) | Out-Null } catch {}
      }
      'symbols_required_for_branches' {
        try { $plot.SetNumProp('symbol.kind', (($i % 6) + 1)) | Out-Null } catch {}
        try { $plot.SetNumProp('symbol.size', 6) | Out-Null } catch {}
      }
      'error_bars_when_available' {
        try { $plot.SetNumProp('symbol.kind', (($i % 6) + 1)) | Out-Null } catch {}
        try { $plot.SetNumProp('symbol.size', 6) | Out-Null } catch {}
      }
      'sticks_required' {
        try { $plot.SetNumProp('symbol.kind', 0) | Out-Null } catch {}
        try { $plot.SetNumProp('line.width', 3) | Out-Null } catch {}
      }
      default {
        if ($markerMode -match 'markers|symbols|sticks') {
          try { $plot.SetNumProp('symbol.kind', (($i % 6) + 1)) | Out-Null } catch {}
          try { $plot.SetNumProp('symbol.size', 6) | Out-Null } catch {}
        } else {
          try { $plot.SetNumProp('symbol.kind', 0) | Out-Null } catch {}
        }
      }
    }

    switch ($plotPrimitive) {
      'scatter' {
        try { $plot.SetNumProp('line.width', 0) | Out-Null } catch {}
        try { $plot.SetNumProp('symbol.kind', (($i % 6) + 1)) | Out-Null } catch {}
      }
      'line' {
        if ($markerMode -eq 'none') {
          try { $plot.SetNumProp('symbol.kind', 0) | Out-Null } catch {}
        }
      }
      'fitted_component_overlay' {
        # The processed CSV already decides raw/background/envelope/component columns.
        # This helper consumes the strategy by applying stable overlay styling only.
        if ($i -eq 0) {
          try { $plot.SetNumProp('line.width', 3) | Out-Null } catch {}
        } elseif ($i -eq 1) {
          try { $plot.SetNumProp('line.width', 3) | Out-Null } catch {}
          try { $plot.SetNumProp('line.style', 2) | Out-Null } catch {}
        } else {
          try { $plot.SetNumProp('line.width', 3) | Out-Null } catch {}
        }
      }
      'image_panel' {
        $app.Execute('layer.x.show=0; layer.y.show=0; layer.x.ticks=0; layer.y.ticks=0; layer.x.label.show=0; layer.y.label.show=0; layer.x.showLabels=0; layer.y.showLabels=0;') | Out-Null
      }
      'eds_map' {
        $app.Execute('layer.x.show=0; layer.y.show=0; layer.x.ticks=0; layer.y.ticks=0; layer.x.label.show=0; layer.y.label.show=0; layer.x.showLabels=0; layer.y.showLabels=0;') | Out-Null
      }
      default {
        # PlotPrimitive is intentionally consumed here even when Origin's plotxy
        # primitive already handled the major graph type via PlotType.
      }
    }

    if ($fitOverlayMode -and $fitOverlayMode -ne 'none') {
      try { $plot.SetNumProp('line.width', 3) | Out-Null } catch {}
    }
  }
}

$script:NativeLegendLayoutCompiled = $false
function Invoke-NativeLegendLayoutFinalizer($app, [string]$PageName) {
  if (-not $script:NativeLegendLayoutCompiled) {
    $nativeSource = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'native_legend_layout.c'))
    $app.Execute('__rdop_legend_compile=run.LoadOC("' + (Escape-OriginText $nativeSource) + '",16);') | Out-Null
    $compileResult = [int]$app.LTVar('__rdop_legend_compile')
    if ($compileResult -ne 0) {
      throw "Native legend layout compile failed for $PageName (run.LoadOC result: $compileResult)."
    }
    $script:NativeLegendLayoutCompiled = $true
  }
  $safePageName = Escape-OriginText $PageName
  $app.Execute('win -a "' + $safePageName + '"; __rdop_legend_layout=0; run -oc {__rdop_legend_layout=rdop_place_legends();};') | Out-Null
  $layoutResult = [int]$app.LTVar('__rdop_legend_layout')
  if ($layoutResult -ne 1 -and $layoutResult -ne 2) {
    throw "Native legend layout failed for $PageName (rdop_place_legends result: $layoutResult)."
  }
}

function Assert-ValidOutput([string]$Path) {
  Require-File $Path
  $item = Get-Item -LiteralPath $Path
  if ($item.Length -lt 10000) {
    throw "Output OPJU is suspiciously small: $Path ($($item.Length) bytes)"
  }
}

function Assert-PngOutput([string]$ExportDir, [string]$PageName) {
  $png = Join-Path $ExportDir ($PageName + '.png')
  Require-File $png
  $item = Get-Item -LiteralPath $png
  if ($item.Length -lt 10000) {
    throw "Exported PNG is suspiciously small: $png ($($item.Length) bytes)"
  }
}

function Assert-GraphPageValid($app, [string]$PageName, [int]$ExpectedPlots, [array]$CurrentLabels, $Group) {
  $app.Execute('win -a ' + $PageName + '; layer -s 1;') | Out-Null
  $layer = $app.FindGraphLayer($PageName)
  if (-not $layer) { $layer = $app.FindGraphLayer($PageName + '!1') }
  if (-not $layer) { throw "Generated graph layer not found: $PageName" }

  if ([int]$layer.DataPlots.Count -ne $ExpectedPlots) {
    throw "Generated graph $PageName expected $ExpectedPlots data plots, got $($layer.DataPlots.Count)"
  }

  $showLegend = Convert-ToBoolean (Get-GroupValue $Group 'ShowLegend' $true) $true
  for ($i = 0; $i -lt $layer.GraphObjects.Count; $i++) {
    $obj = $layer.GraphObjects.Item($i)
    $txt = ''
    try { $txt = [string]$obj.Text } catch {}

    if ($obj.Name -eq 'Legend') {
      if (-not $showLegend) {
        $visible = 0
        try { $visible = [double]$obj.GetNumProp('show') } catch {}
        if ($visible -gt 0) {
          throw "Legend must be hidden on ${PageName}."
        }
        continue
      }
      if (-not $txt) {
        throw "Visible legend text is missing on ${PageName}."
      }
      # Native legend substitutions stay linked to the plotted columns.
      if ([regex]::Matches($txt, '%\(\d+\)').Count -ne $ExpectedPlots) {
        throw "Legend is not linked to all $ExpectedPlots plots on ${PageName}: $txt"
      }
      foreach ($property in @('background', 'border', 'frame', 'fill', 'lineWidth')) {
        try {
          $value = [double]$obj.GetNumProp($property)
          if ([Math]::Abs($value) -gt 0.05) {
            throw "Legend property $property must be zero on ${PageName}; got $value."
          }
        } catch {
          if ($_.Exception.Message -match '^Legend property ') { throw }
        }
      }
    }

    if (-not $txt) { continue }

    if ($obj.Name -in @('XB','YL')) {
      $font = -1
      $size = -1
      try { $font = [int]$obj.GetNumProp('font') } catch {}
      try { $size = [double]$obj.GetNumProp('fsize') } catch {}
      if ($font -ne $AxisTitleFont -or [Math]::Abs($size - $AxisTitleSize) -gt 0.05) {
        throw "Axis title $($obj.Name) is not Arial size 36 on ${PageName}: font=$font size=$size"
      }
      if ($txt -notmatch '\\b\(') {
        throw "Axis title $($obj.Name) is not bold-wrapped on ${PageName}: $txt"
      }
    }

    if (($txt -match 'BiCu|CuWO|BiOBr|JCPDS|04-009|card') -and -not (Test-CurrentText $txt $CurrentLabels)) {
      throw "Template residue remains on $PageName object $($obj.Name): $txt"
    }
  }
}

$app = $null
$runClock = [System.Diagnostics.Stopwatch]::StartNew()
$phaseClock = [System.Diagnostics.Stopwatch]::StartNew()
$stageSeconds = [ordered]@{ startup = 0.0; data_import = 0.0; graph_style = 0.0; save = 0.0; image_export = 0.0; shutdown = 0.0; total = 0.0 }

try {
  $AllowedOutputRoot = Get-FullPath $AllowedOutputRoot
  $OutputOpju = Get-FullPath $OutputOpju
  $ExportDir = Get-FullPath $ExportDir
  Assert-NoReparsePointInPath $AllowedOutputRoot 'AllowedOutputRoot'
  Assert-NoReparsePointInPath $ExportDir 'ExportDir'
  if (Test-Path -LiteralPath $ExportDir -PathType Leaf) {
    throw "ExportDir must be a directory, not a file: $ExportDir"
  }
  Assert-SafeOutputPath $OutputOpju $AllowedOutputRoot 'OutputOpju'
  if ([System.IO.Path]::GetExtension($OutputOpju).ToLowerInvariant() -notin @('.opj', '.opju')) {
    throw "OutputOpju must use .opj or .opju."
  }

  $plannedOutputs = New-Object System.Collections.Generic.List[string]
  $plannedOutputs.Add($OutputOpju) | Out-Null
  $plannedKeys = @{}
  $plannedKeys[$OutputOpju.ToLowerInvariant()] = 'OutputOpju'
  foreach ($group in $Groups) {
    $pageName = [string](Get-GroupValue $group 'PageName')
    Assert-SafePageName $pageName
    $dataFile = [string](Get-GroupValue $group 'DataFile')
    Require-File $dataFile
    $pngTarget = Get-FullPath (Join-Path $ExportDir ($pageName + '.png'))
    Assert-SafeOutputPath $pngTarget $AllowedOutputRoot ("PNG output for " + $pageName)
    $key = $pngTarget.ToLowerInvariant()
    if ($plannedKeys.ContainsKey($key)) {
      throw "Planned output collision: $($plannedKeys[$key]) and PNG output for $pageName"
    }
    $plannedKeys[$key] = "PNG output for $pageName"
    $plannedOutputs.Add($pngTarget) | Out-Null
    $dataFull = Get-FullPath $dataFile
    if ($plannedKeys.ContainsKey($dataFull.ToLowerInvariant())) {
      throw "A planned output aliases its DataFile: $dataFile"
    }
  }

  $useReferenceStyle = $RefreshReferenceStyle -or -not [string]::IsNullOrWhiteSpace($ReferenceOpju)
  if ($useReferenceStyle -and [string]::IsNullOrWhiteSpace($ReferenceOpju)) {
    $ReferenceOpju = Find-DefaultReferenceOpju
  }
  if ($useReferenceStyle) {
    Require-File $ReferenceOpju
    $ReferenceOpju = Get-FullPath $ReferenceOpju
    if ($plannedKeys.ContainsKey($ReferenceOpju.ToLowerInvariant())) {
      throw "A planned output aliases ReferenceOpju: $ReferenceOpju"
    }
  }
  if (-not $AllowRunningOrigin) {
    $runningOrigin = @(Get-Process -Name Origin* -ErrorAction SilentlyContinue | Where-Object {
      try {
        $threads = $_.Threads
        if ($null -eq $threads) { $true } else { @($threads).Count -gt 0 }
      } catch {
        $true
      }
    })
    if ($runningOrigin) {
      throw "Origin is already running. Close it or rerun with -AllowRunningOrigin after confirming no unsaved work will be affected."
    }
  }

  $existingOutputs = @($plannedOutputs | Where-Object { Test-Path -LiteralPath $_ })
  if ($existingOutputs.Count -gt 0 -and -not $Force) {
    throw "Planned Origin output already exists; rerun with -Force after review: $($existingOutputs -join ', ')"
  }

  New-Item -ItemType Directory -Path $ExportDir -Force | Out-Null
  $workDir = Split-Path -Parent $OutputOpju
  New-Item -ItemType Directory -Path $workDir -Force | Out-Null
  $templateRoot = Join-Path $workDir 'origin_templates'
  $templateDir = $null
  $templateRootCreatedByThisRun = $false
  $templateDirCreatedByThisRun = $false
  if ($useReferenceStyle) {
    if (-not (Test-Path -LiteralPath $templateRoot)) {
      New-Item -ItemType Directory -Path $templateRoot -Force | Out-Null
      $templateRootCreatedByThisRun = $true
    }
    $templateDir = Join-Path $templateRoot ('run_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '_' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $templateDir -Force | Out-Null
    $templateDirCreatedByThisRun = $true
  }

  $phaseClock.Restart()
  $app = New-Object -ComObject Origin.Application
  $app.Visible = if ($Headless) { 0 } else { 1 }
  $stageSeconds.startup = $phaseClock.Elapsed.TotalSeconds

  $referenceStyle = New-CachedGraph4Style
  $template = $null
  if ($useReferenceStyle) {
    $referenceWorkingCopy = Join-Path $templateDir 'reference_working_copy.opju'
    Copy-Item -LiteralPath $ReferenceOpju -Destination $referenceWorkingCopy -Force

    if (-not $app.Load($referenceWorkingCopy)) {
      throw ("Failed to load reference OPJU working copy: " + (Split-Path -Leaf $referenceWorkingCopy))
    }

    $app.Execute("win -a $ReferenceGraph;") | Out-Null
    $referenceStyle = Get-ReferenceStyle $app $ReferenceGraph
    Sanitize-ReferenceGraphForTemplate $app $ReferenceGraph
    Sanitize-ProjectPages $app
    $templateName = 'reference_graph_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff')
    $template = Join-Path $templateDir ($templateName + '.otpu')
    Remove-Item -LiteralPath $template -Force -ErrorAction SilentlyContinue
    $app.Execute('template_saveas pg:=' + $ReferenceGraph + ' category:="ResearchDataOrigin" template:="' + $templateName + '" filepath:="' + (To-OriginPath $templateDir) + '" emf:=0 bmp:=1 loadsys:=0;') | Out-Null
    if (-not (Test-Path -LiteralPath $template)) {
      Write-Output ("REFERENCE_TEMPLATE_SAVE_FAILED_USING_EXTRACTED_STYLE=" + $template)
      $template = $null
    }
  }

  $app.NewProject() | Out-Null

  foreach ($group in $Groups) {
    Require-File (Get-GroupValue $group 'DataFile')
    $dataFile = [string](Get-GroupValue $group 'DataFile')
    $pageName = [string](Get-GroupValue $group 'PageName')
    $cols = [int](Get-GroupValue $group 'ColumnCount')
    $xyPairs = Parse-XYPairs ([string](Get-GroupValue $group 'XYPairs' '')) $cols
    $plotType = [string]$DefaultPlotType
    $groupPlotType = Get-GroupValue $group 'PlotType' $null
    if ($groupPlotType) { $plotType = [string]$groupPlotType }
    if (-not $pageName) { throw 'Each group needs PageName.' }
    if ($cols -lt 2) { throw "ColumnCount must be >= 2 for $pageName." }

    $currentLabels = @()
    $groupLabels = Get-GroupValue $group 'Labels' $null
    if ($groupLabels) {
      $currentLabels = @($groupLabels)
    } else {
      $currentLabels = Get-HeaderLabels $dataFile $cols
    }
    $expectedPlotCount = if ($xyPairs.Count -gt 0) { $xyPairs.Count } else { $cols - 1 }
    if ($currentLabels.Count -ne $expectedPlotCount) {
      throw "Label count ($($currentLabels.Count)) must match plot count ($expectedPlotCount) for $pageName."
    }

    $phaseClock.Restart()
    $table = Read-DelimitedTable $dataFile
    if ($table.Headers.Count -lt $cols) {
      throw "Data file column count is smaller than requested ColumnCount for $pageName."
    }
    $dataFileName = [System.IO.Path]::GetFileName($dataFile)
    $dataBookName = Convert-ToSafeOriginName ([System.IO.Path]::GetFileNameWithoutExtension($dataFile)) 'Data'
    Initialize-OriginDataWorkbook $app $dataBookName $dataFileName $table.Headers $table.Rows $cols
    Set-OriginSeriesLabels $app $currentLabels $xyPairs
    # Keep an explicit worksheet reference after the first graph becomes active.
    # Later independent X/Y plots must not resolve columns against that graph.
    $worksheetReference = '[' + [string]$app.LTStr('%H') + ']1!'
    $stageSeconds.data_import += $phaseClock.Elapsed.TotalSeconds
    $phaseClock.Restart()
    if ($xyPairs.Count -gt 0) {
      foreach ($pair in $xyPairs) {
        $app.Execute('wks.col' + [int]$pair.X + '.type=4; wks.col' + [int]$pair.Y + '.type=1;') | Out-Null
      }
    }

    if ($xyPairs.Count -gt 0) {
      $first = $xyPairs[0]
      if ($template) {
        $app.Execute('worksheet -s 1 ' + $cols + '; plotxy iy:=' + $worksheetReference + '(' + [int]$first.X + ',' + [int]$first.Y + ') plot:=' + $plotType + ' ogl:=[<new template:="' + (To-OriginPath $template) + '" name:="' + $pageName + '">];') | Out-Null
      } else {
        $app.Execute('worksheet -s 1 ' + $cols + '; plotxy iy:=' + $worksheetReference + '(' + [int]$first.X + ',' + [int]$first.Y + ') plot:=' + $plotType + ' ogl:=[<new name:="' + $pageName + '">];') | Out-Null
      }
      for ($pairIndex = 1; $pairIndex -lt $xyPairs.Count; $pairIndex++) {
        $pair = $xyPairs[$pairIndex]
        $app.Execute('plotxy iy:=' + $worksheetReference + '(' + [int]$pair.X + ',' + [int]$pair.Y + ') plot:=' + $plotType + ' ogl:=[' + $pageName + ']Layer1;') | Out-Null
      }
    } elseif ($template) {
      $app.Execute('worksheet -s 1 ' + $cols + '; plotxy iy:=(1,2:' + $cols + ') plot:=' + $plotType + ' ogl:=[<new template:="' + (To-OriginPath $template) + '" name:="' + $pageName + '">];') | Out-Null
    } else {
      $app.Execute('worksheet -s 1 ' + $cols + '; plotxy iy:=(1,2:' + $cols + ') plot:=' + $plotType + ' ogl:=[<new name:="' + $pageName + '">];') | Out-Null
    }
    if (-not $app.Execute('legendupdate dest:=layer update:=reconstruct mode:=lname; page.legendtranslationmode=4;')) {
      throw "Native legend update failed for $pageName."
    }
    Clear-TemplateResidue $app $pageName $currentLabels
    Apply-ReferenceStyle $app $pageName $currentLabels $referenceStyle $group
    Apply-PlotPolicy $app $pageName $group
    Clear-TemplateResidue $app $pageName $currentLabels
    Apply-ReferenceStyle $app $pageName $currentLabels $referenceStyle $group
    Apply-PlotPolicy $app $pageName $group
    Assert-GraphPageValid $app $pageName $expectedPlotCount $currentLabels $group
    Invoke-NativeLegendLayoutFinalizer $app $pageName
    $stageSeconds.graph_style += $phaseClock.Elapsed.TotalSeconds
  }

  $currentExistingOutputs = @($plannedOutputs | Where-Object { Test-Path -LiteralPath $_ })
  if ($currentExistingOutputs.Count -gt 0 -and -not $Force) {
    throw "A planned Origin output appeared during processing; refusing to overwrite: $($currentExistingOutputs -join ', ')"
  }
  foreach ($target in $currentExistingOutputs) {
    Assert-SafeOutputPath $target $AllowedOutputRoot 'Existing Origin output'
    Remove-Item -LiteralPath $target -Force
  }

  $phaseClock.Restart()
  Sanitize-ProjectPages $app
  $app.Save($OutputOpju) | Out-Null
  Assert-ValidOutput $OutputOpju
  $stageSeconds.save = $phaseClock.Elapsed.TotalSeconds

  $phaseClock.Restart()
  foreach ($group in $Groups) {
    $pageName = [string](Get-GroupValue $group 'PageName')
    $app.Execute('win -a ' + $pageName + '; expGraph type:=png path:="' + (To-OriginPath $ExportDir) + '" filename:="' + $pageName + '" overwrite:=replace;') | Out-Null
    Assert-PngOutput $ExportDir $pageName
  }
  $stageSeconds.image_export = $phaseClock.Elapsed.TotalSeconds

  Write-Output ("SAVED=" + (Split-Path -Leaf $OutputOpju))
  Write-Output ("EXPORT_DIR=" + (Split-Path -Leaf $ExportDir))
  if ($useReferenceStyle) {
    Write-Output ("REFERENCE=" + (Split-Path -Leaf $ReferenceOpju))
  } else {
    Write-Output "REFERENCE=CACHED_GRAPH4_STYLE"
  }

  if (-not $KeepIntermediate -and $templateDirCreatedByThisRun -and $templateDir -and (Test-Path -LiteralPath $templateDir)) {
    Remove-Item -LiteralPath $templateDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Output "CLEANED_INTERMEDIATE=$templateDir"
  }
  if (-not $KeepIntermediate -and $templateRootCreatedByThisRun -and (Test-Path -LiteralPath $templateRoot)) {
    $remainingTemplateFiles = @(Get-ChildItem -LiteralPath $templateRoot -Force -ErrorAction SilentlyContinue)
    if ($remainingTemplateFiles.Count -eq 0) {
      Remove-Item -LiteralPath $templateRoot -Force -ErrorAction SilentlyContinue
      Write-Output "CLEANED_INTERMEDIATE_ROOT=$templateRoot"
    }
  }
}
finally {
  $phaseClock.Restart()
  if ($CloseOrigin -and $app) {
    try { $app.Exit() | Out-Null } catch {}
  }
  $stageSeconds.shutdown = $phaseClock.Elapsed.TotalSeconds
  $stageSeconds.total = $runClock.Elapsed.TotalSeconds
  Write-Output ('ORIGIN_STAGE_TIMINGS=' + ($stageSeconds | ConvertTo-Json -Compress))
}
