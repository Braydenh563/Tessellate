<#
  Tessellate - launch splash.

  WHY THIS EXISTS
  ---------------
  Reported directly: the pre-launch work (git pull, building .venv, pip
  installing several hundred megabytes of dependencies) "takes a while to
  actually open the window so the user doesn't think the application didn't
  start properly because they didn't have access to the terminal logs".

  That gap is real and it is the worst one in the whole product. `__main__.py`
  already shows a loading window with a progress bar - but that window is
  created by Python, and everything above happens in start.bat *before* Python
  can run at all. On a first run, or any run where requirements.txt changed,
  that is minutes of a machine doing nothing visible. In console-less mode
  (show_console_on_startup = False, and the packaged build) there is not even a
  terminal to watch, so the only feedback is that double-clicking the icon
  appeared to do nothing.

  So: an Adobe-style splash, up within a second of the double-click, showing
  what is happening, handed off to the Python loading window when that appears.

  HOW IT TALKS TO THE LAUNCHER
  ----------------------------
  One status file, polled. The launcher appends a line per phase transition:

      step|total|title|detail|state          state in active, done, failed

  and this reads the whole file, not just the last line, so the window can draw
  every step that has happened with a tick beside it rather than one sentence
  with no context. `src/tessellate/core/launch_status.py` is the same grammar in
  Python, for the loading window that takes over from this one; the two are
  kept in step by tests/test_launcher_scripts.py.

  Deliberately a file rather than a pipe or a named event: start.bat is
  cmd.exe, which can write a file with `echo >` and essentially nothing else,
  and a file also gives us the shutdown signal for free - when the file
  disappears, the launcher is done and this exits.

  Three independent ways to die, because a splash that outlives its launcher is
  worse than no splash at all: the status file says __done__, the status file is
  deleted, or MaxMinutes elapses. The last one is the backstop for a launcher
  killed with Ctrl+C or Task Manager, which deletes nothing on its way out.

  Cancel writes "__cancel__" into "<status file>.cancel", which the launcher
  polls between phases and honours. Between phases and not during one, because
  killing a pip mid-install leaves a half-written venv.

  Everything here is best-effort. It is wrapped in a try/catch that exits
  quietly, and start.bat launches it detached and never checks whether it
  worked: a cosmetic window failing to appear must not stop the app starting.
#>
param(
  [Parameter(Mandatory = $true)][string]$StatusFile,
  [int]$MaxMinutes = 20,
  [string]$IconPath = "",
  [string]$LogPath = "",
  [string]$LauncherPath = "",
  [string]$DataDir = ""
)

# Brief 85: this is a splash, not an installer window. Borderless and rounded,
# the mark centred, one status line with "Step N of M" beside it, one slim
# accent bar, then the steps in a fixed panel (INBOX 1301 D2: the window keeps
# one size, so it never grows down the screen) and Details, Copy diagnostics
# and Cancel as quiet links. Not run on Windows from the build box.
$ErrorActionPreference = "Stop"
try {
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing

  [System.Windows.Forms.Application]::EnableVisualStyles()
  [System.Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false)

  $bg     = [System.Drawing.Color]::FromArgb(18, 20, 28)
  $ink    = [System.Drawing.Color]::FromArgb(231, 233, 238)
  $muted  = [System.Drawing.Color]::FromArgb(154, 161, 173)
  $dim    = [System.Drawing.Color]::FromArgb(93, 100, 114)
  $accent = [System.Drawing.Color]::FromArgb(79, 109, 245)
  $good   = [System.Drawing.Color]::FromArgb(74, 157, 122)
  $warn   = [System.Drawing.Color]::FromArgb(229, 161, 58)
  $bad    = [System.Drawing.Color]::FromArgb(229, 143, 143)
  $panel  = [System.Drawing.Color]::FromArgb(28, 31, 42)
  $track  = [System.Drawing.Color]::FromArgb(38, 43, 58)

  # One size from the first frame to the last (INBOX 1301 D2, the owner: the
  # splash "is still pushing down to the bottom of the screen every step
  # completed"). The window used to be centred at 252px and then grow
  # downwards, a row per finished step and 134px more for Details, so its top
  # stayed where a short window was centred and its bottom walked off the
  # screen (586px tall, its top placed for 252, on a 728px work area: 96px
  # below the taskbar). Now it is centred at
  # the size it keeps: the steps live in a fixed panel with a row for each of
  # MAX_ROWS, and Details swaps the log into that same panel.
  $WIDTH            = 520
  $HEIGHT           = 440
  $PANEL_TOP        = 206
  $PANEL_H          = 148
  $ROW_TOP          = 10
  $ROW_STEP         = 22
  $MAX_ROWS         = 6
  $SHOW_LINKS_AFTER = 0

  # The mark is drawn once into a bitmap here, before the window exists, so the
  # first paint is a DrawImage and the logo is there with the window rather
  # than about a second after it. Same geometry as frontend/favicon.svg
  # (three hexagon cells, the third lifted); tests/test_brand_mark.py holds
  # the points.
  function New-LogoBitmap([int]$size) {
    $bmp = New-Object System.Drawing.Bitmap -ArgumentList $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = "AntiAlias"
    $g.Clear([System.Drawing.Color]::Transparent)
    $s = $size / 100.0
    $rect = New-Object System.Drawing.RectangleF(0, 0, $size, $size)
    $tile = New-Object System.Drawing.Drawing2D.LinearGradientBrush -ArgumentList `
      $rect, ([System.Drawing.Color]::FromArgb(91, 124, 255)), ([System.Drawing.Color]::FromArgb(169, 39, 216)), ([float]45.0)
    $r = 23 * $s
    $tp = New-Object System.Drawing.Drawing2D.GraphicsPath
    $tp.AddArc(0, 0, 2 * $r, 2 * $r, 180, 90)
    $tp.AddArc($size - 2 * $r, 0, 2 * $r, 2 * $r, 270, 90)
    $tp.AddArc($size - 2 * $r, $size - 2 * $r, 2 * $r, 2 * $r, 0, 90)
    $tp.AddArc(0, $size - 2 * $r, 2 * $r, 2 * $r, 90, 90)
    $tp.CloseFigure()
    $g.FillPath($tile, $tp)

    $cells = @(
      @{ pts = @(35.3,48.7, 46.8,55.4, 46.8,68.6, 35.3,75.3, 23.8,68.6, 23.8,55.4); alpha = 242; lift = $false },
      @{ pts = @(64.7,48.7, 76.2,55.4, 76.2,68.6, 64.7,75.3, 53.2,68.6, 53.2,55.4); alpha = 178; lift = $false },
      @{ pts = @(57.3,18.4, 67.5,27.0, 65.2,40.0, 52.7,44.6, 42.5,36.0, 44.8,23.0); alpha = 255; lift = $true }
    )
    foreach ($c in $cells) {
      $points = New-Object 'System.Collections.Generic.List[System.Drawing.PointF]'
      for ($i = 0; $i -lt 12; $i += 2) {
        $points.Add((New-Object System.Drawing.PointF(([float]($c.pts[$i] * $s)), ([float]($c.pts[$i + 1] * $s)))))
      }
      $gp = New-Object System.Drawing.Drawing2D.GraphicsPath
      $gp.AddPolygon($points.ToArray())
      $pen = New-Object System.Drawing.Pen -ArgumentList ([System.Drawing.Color]::White), ([float](7 * $s))
      $pen.LineJoin = "Round"
      $outline = $gp.Clone()
      $outline.Widen($pen)
      $region = New-Object System.Drawing.Region($gp)
      $region.Union($outline)
      if ($c.lift) {
        $shadow = $region.Clone()
        $shadow.Translate(0, [float](3 * $s))
        $sb = New-Object System.Drawing.SolidBrush -ArgumentList ([System.Drawing.Color]::FromArgb(110, 26, 16, 96))
        $g.FillRegion($sb, $shadow)
        $sb.Dispose(); $shadow.Dispose()
        $bounds = New-Object System.Drawing.RectangleF(([float](38 * $s)), ([float](14 * $s)), ([float](34 * $s)), ([float](34 * $s)))
        $fill = New-Object System.Drawing.Drawing2D.LinearGradientBrush -ArgumentList `
          $bounds, ([System.Drawing.Color]::White), ([System.Drawing.Color]::FromArgb(201, 184, 255)), ([float]45.0)
      } else {
        $fill = New-Object System.Drawing.SolidBrush -ArgumentList ([System.Drawing.Color]::FromArgb($c.alpha, 255, 255, 255))
      }
      $g.FillRegion($fill, $region)
      $fill.Dispose(); $region.Dispose(); $outline.Dispose(); $gp.Dispose(); $pen.Dispose()
    }
    $tile.Dispose(); $tp.Dispose(); $g.Dispose()
    return $bmp
  }
  $logoBmp = New-LogoBitmap 192

  function New-RoundRegion([int]$w, [int]$h, [int]$radius) {
    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $radius * 2
    $p.AddArc(0, 0, $d, $d, 180, 90)
    $p.AddArc($w - $d, 0, $d, $d, 270, 90)
    $p.AddArc($w - $d, $h - $d, $d, $d, 0, 90)
    $p.AddArc(0, $h - $d, $d, $d, 90, 90)
    $p.CloseFigure()
    return (New-Object System.Drawing.Region($p))
  }

  $form                 = New-Object System.Windows.Forms.Form
  $form.FormBorderStyle = "None"
  $form.StartPosition   = "CenterScreen"
  $form.Size            = New-Object System.Drawing.Size($WIDTH, $HEIGHT)
  $form.BackColor       = $bg
  $form.TopMost         = $true
  $form.ShowInTaskbar   = $true
  $form.Text            = "Starting Tessellate Notes"
  # Centred in the working area (above the taskbar) at the size it keeps; on
  # a screen shorter than the window its top stays on screen.
  $form.Add_Shown({
    $area = [System.Windows.Forms.Screen]::FromControl($form).WorkingArea
    $left = [int]($area.X + [Math]::Max(0, ($area.Width - $form.Width) / 2))
    $top  = [int]($area.Y + [Math]::Max(0, ($area.Height - $form.Height) / 2))
    $form.Location = New-Object System.Drawing.Point($left, $top)
  })
  $form.Region          = New-RoundRegion $WIDTH $HEIGHT 18
  # Double buffered (C38, the owner: "the splash popup flickers quite a bit").
  # `DoubleBuffered` is a protected property, so it is set through reflection;
  # without it every label change repaints straight onto the screen, a row at
  # a time. Not verified on Windows from this sandbox.
  try {
    [System.Windows.Forms.Form].GetProperty("DoubleBuffered", [System.Reflection.BindingFlags]"NonPublic,Instance").SetValue($form, $true, $null)
  } catch {
  }

  if (-not $IconPath) {
    $IconPath = Join-Path (Split-Path -Parent $PSScriptRoot) "frontend\icon.ico"
  }
  try {
    if (Test-Path -LiteralPath $IconPath) {
      $form.Icon = New-Object System.Drawing.Icon($IconPath)
    }
  } catch {
  }

  $logo = New-Object System.Windows.Forms.Panel
  $logo.Size     = New-Object System.Drawing.Size(64, 64)
  $logo.Location = New-Object System.Drawing.Point(228, 24)
  $logo.BackColor = $bg
  $logo.Add_Paint({
    param($src, $e)
    $e.Graphics.InterpolationMode = "HighQualityBicubic"
    $e.Graphics.DrawImage($logoBmp, 0, 0, 64, 64)
  })

  $centre = [System.Drawing.ContentAlignment]::MiddleCenter

  # The name with a small "notes" beside it (the owner, 2026-10-12: the
  # name alone read like a game), drawn as one lockup: two Labels padded
  # their text differently and sat "notes" off the name's baseline, with a
  # gap wider than a word space (owner, 2026-10-12: "looks awkward").
  # One panel draws both on a shared baseline, a word space apart.
  $titleFont = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]17), ([System.Drawing.FontStyle]::Bold)
  $noteFont  = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]12)
  $title           = New-Object System.Windows.Forms.Panel
  $title.Location  = New-Object System.Drawing.Point(0, 94)
  $title.Size      = New-Object System.Drawing.Size($WIDTH, 34)
  $title.BackColor = [System.Drawing.Color]::Transparent
  $title.Add_Paint({
    param($sender, $e)
    $g = $e.Graphics
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
    $fmt = [System.Drawing.StringFormat]::GenericTypographic
    $nameW = $g.MeasureString("Tessellate", $titleFont, 1000, $fmt).Width
    $noteW = $g.MeasureString("notes", $noteFont, 1000, $fmt).Width
    $gap   = $g.MeasureString(" ", $noteFont).Width * 0.6
    $x = ($WIDTH - $nameW - $gap - $noteW) / 2
    # Baseline: the cell ascent in pixels, per font.
    $asc = { param($f) $f.SizeInPoints * $g.DpiY / 72 * $f.FontFamily.GetCellAscent($f.Style) / $f.FontFamily.GetEmHeight($f.Style) }
    $base = 2 + (& $asc $titleFont)
    $inkBrush  = New-Object System.Drawing.SolidBrush $ink
    $noteBrush = New-Object System.Drawing.SolidBrush $muted
    $g.DrawString("Tessellate", $titleFont, $inkBrush, [float]$x, [float]($base - (& $asc $titleFont)), $fmt)
    $g.DrawString("notes", $noteFont, $noteBrush, [float]($x + $nameW + $gap), [float]($base - (& $asc $noteFont)), $fmt)
    $inkBrush.Dispose(); $noteBrush.Dispose()
  })

  $tag             = New-Object System.Windows.Forms.Label
  $tag.Text        = "Your notes, pieced together"
  $tag.ForeColor   = $muted
  $tag.Font        = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]9)
  $tag.TextAlign   = $centre
  $tag.Location    = New-Object System.Drawing.Point(0, 128)
  $tag.Size        = New-Object System.Drawing.Size($WIDTH, 20)

  # What is running now on the left, "Step 2 of 6" on the right, over the
  # bar: the count says how far along without reading the list.
  $status           = New-Object System.Windows.Forms.Label
  $status.Text      = "Starting"
  $status.ForeColor = $ink
  $status.Font      = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]9)
  $status.TextAlign = [System.Drawing.ContentAlignment]::MiddleLeft
  $status.AutoEllipsis = $true
  $status.Location  = New-Object System.Drawing.Point(40, 164)
  $status.Size      = New-Object System.Drawing.Size(330, 20)

  $count           = New-Object System.Windows.Forms.Label
  $count.Text      = ""
  $count.ForeColor = $muted
  $count.Font      = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]9)
  $count.TextAlign = [System.Drawing.ContentAlignment]::MiddleRight
  $count.Location  = New-Object System.Drawing.Point(370, 164)
  $count.Size      = New-Object System.Drawing.Size(110, 20)

  # One bar, painted by hand from two panels in the app accent. A stock
  # ProgressBar is green (or white) under the system theme and ignores
  # ForeColor once themed, which is how the old window got two bars of two
  # colours.
  $BAR_X = 40
  $BAR_W = 440
  $barTrack          = New-Object System.Windows.Forms.Panel
  $barTrack.BackColor = $track
  $barTrack.Location = New-Object System.Drawing.Point($BAR_X, 190)
  $barTrack.Size     = New-Object System.Drawing.Size($BAR_W, 4)
  $barFill           = New-Object System.Windows.Forms.Panel
  $barFill.BackColor = $accent
  $barFill.Location  = New-Object System.Drawing.Point(0, 0)
  $barFill.Size      = New-Object System.Drawing.Size(8, 4)
  $barTrack.Controls.Add($barFill)

  $tips = @(
    "Your notes never leave this machine.",
    "Ctrl+K opens the command palette.",
    "The capture box files a thought for you, in the right place.",
    "The first run installs about 300 MB once. Later starts take seconds."
  )
  if ($DataDir) {
    $tips += "Your notes live in $DataDir, as plain files you can copy."
  } else {
    $tips += "Your notes live in your own data folder, as plain files you can copy."
  }

  $tip             = New-Object System.Windows.Forms.Label
  $tip.ForeColor   = $dim
  $tip.Font        = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]8)
  $tip.TextAlign   = $centre
  $tip.Location    = New-Object System.Drawing.Point(40, 384)
  $tip.Size        = New-Object System.Drawing.Size(440, 18)
  $tip.Text        = $tips[0]

  # Quiet links, hidden at rest.
  function New-FooterLink([string]$text, [int]$x, [int]$width) {
    $b               = New-Object System.Windows.Forms.Label
    $b.Text          = $text
    $b.Location      = New-Object System.Drawing.Point($x, 410)
    $b.Size          = New-Object System.Drawing.Size($width, 20)
    $b.ForeColor     = $muted
    $b.Font          = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]8.5), ([System.Drawing.FontStyle]::Underline)
    $b.TextAlign     = $centre
    $b.Cursor        = [System.Windows.Forms.Cursors]::Hand
    $b.Visible       = $false
    return $b
  }

  $btnDetails = New-FooterLink "Details" 0 90
  $btnCopy    = New-FooterLink "Copy diagnostics" 0 130
  $btnRetry   = New-FooterLink "Try again" 0 80
  $btnCancel  = New-FooterLink "Cancel" 0 70

  # The visible links, centred as a row: fixed slots left a hole where a
  # hidden one sat and the row read off-centre (owner, 2026-10-12).
  function Set-LinkRow {
    $shown = @($btnDetails, $btnCopy, $btnRetry, $btnCancel) | Where-Object { $_.Visible }
    if (-not $shown) { return }
    $gap = 28
    $widths = @($shown | ForEach-Object { [System.Windows.Forms.TextRenderer]::MeasureText($_.Text, $_.Font).Width + 6 })
    $total = ($widths | Measure-Object -Sum).Sum + $gap * ($shown.Count - 1)
    $x = [int](($WIDTH - $total) / 2)
    for ($i = 0; $i -lt $shown.Count; $i++) {
      $shown[$i].Width = $widths[$i]
      $shown[$i].Left = $x
      $x += $widths[$i] + $gap
    }
  }

  $hint             = New-Object System.Windows.Forms.Label
  $hint.Text        = ""
  $hint.ForeColor   = $warn
  $hint.Font        = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]8)
  $hint.TextAlign   = $centre
  $hint.Location    = New-Object System.Drawing.Point(40, 362)
  $hint.Size        = New-Object System.Drawing.Size(440, 18)

  # The steps' panel: a fixed box under the bar, MAX_ROWS rows tall, so a
  # finished step changes a row's words and never the window's height.
  $list           = New-Object System.Windows.Forms.Panel
  $list.BackColor = $panel
  $list.Location  = New-Object System.Drawing.Point($BAR_X, $PANEL_TOP)
  $list.Size      = New-Object System.Drawing.Size($BAR_W, $PANEL_H)
  $list.Region    = New-RoundRegion $BAR_W $PANEL_H 10

  $BAR_DROP   = 18
  $BAR_HEIGHT = 3
  $rowMark   = @()
  $rowName   = @()
  $rowDetail = @()
  for ($i = 0; $i -lt $MAX_ROWS; $i++) {
    $mark            = New-Object System.Windows.Forms.Label
    $mark.Font       = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]10)
    $mark.ForeColor  = $dim
    $mark.BackColor  = $panel
    $mark.Location   = New-Object System.Drawing.Point(12, ($ROW_TOP + $i * $ROW_STEP))
    $mark.Size       = New-Object System.Drawing.Size(18, 20)
    $mark.Text       = ""

    $name            = New-Object System.Windows.Forms.Label
    $name.Font       = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]10)
    $name.ForeColor  = $dim
    $name.BackColor  = $panel
    $name.Location   = New-Object System.Drawing.Point(32, ($ROW_TOP + $i * $ROW_STEP))
    $name.Size       = New-Object System.Drawing.Size(130, 20)
    $name.Text       = ""

    $detail           = New-Object System.Windows.Forms.Label
    $detail.Font      = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]9)
    $detail.ForeColor = $dim
    $detail.BackColor = $panel
    $detail.AutoEllipsis = $true
    $detail.Location  = New-Object System.Drawing.Point(166, ($ROW_TOP + 2 + $i * $ROW_STEP))
    $detail.Size      = New-Object System.Drawing.Size(262, 16)
    $detail.Text      = ""

    $rowMark   += $mark
    $rowName   += $name
    $rowDetail += $detail
  }

  $details              = New-Object System.Windows.Forms.TextBox
  $details.Multiline    = $true
  $details.ReadOnly     = $true
  $details.ScrollBars   = "Vertical"
  $details.BackColor    = $panel
  $details.ForeColor    = $muted
  $details.BorderStyle  = "None"
  $details.Font         = New-Object System.Drawing.Font -ArgumentList "Consolas", ([float]8)
  $details.Location     = New-Object System.Drawing.Point(10, 8)
  $details.Size         = New-Object System.Drawing.Size(($BAR_W - 20), ($PANEL_H - 16))
  $details.Visible      = $false

  # Before the launcher's first line, the panel says what it is waiting for
  # rather than standing empty.
  $rowName[0].Text = "Starting"
  $rowName[0].Size = New-Object System.Drawing.Size(400, 20)

  # Minimise and close in the top right corner (INBOX 1320, the owner: "I
  # want a minimise and close x button in the top right corner to cancel or
  # minimise the launch"). The window has no title bar, so they are its own.
  function New-CornerButton([string]$glyph, [int]$x, [string]$name) {
    $b             = New-Object System.Windows.Forms.Label
    $b.Text        = $glyph
    $b.Location    = New-Object System.Drawing.Point($x, 10)
    $b.Size        = New-Object System.Drawing.Size(32, 28)
    $b.ForeColor   = $muted
    $b.Font        = New-Object System.Drawing.Font -ArgumentList "Segoe UI", ([float]12)
    $b.TextAlign   = $centre
    $b.Cursor      = [System.Windows.Forms.Cursors]::Hand
    $b.AccessibleName = $name
    $b.Add_MouseEnter({ $this.ForeColor = $ink })
    $b.Add_MouseLeave({ $this.ForeColor = $muted })
    return $b
  }
  $btnMin   = New-CornerButton ([string][char]0x2013) ($WIDTH - 76) "Minimise"
  $btnClose = New-CornerButton ([string][char]0x00D7) ($WIDTH - 42) "Cancel the launch and close"
  $btnMin.Add_Click({ $form.WindowState = "Minimized" })
  # Close cancels the launch (the Cancel link's own request) and closes the
  # window; after a failure it only closes.
  $btnClose.Add_Click({
    if (-not $st.failed -and -not $st.cancelled) {
      try { Set-Content -LiteralPath ($StatusFile + ".cancel") -Value "__cancel__" -ErrorAction Stop } catch { }
      $st.cancelled = $true
    }
    $form.Close()
  })

  $form.Controls.AddRange(@($logo, $title, $tag, $status, $count, $barTrack, $list, $hint, $tip,
                            $btnDetails, $btnCopy, $btnRetry, $btnCancel, $btnMin, $btnClose))
  $list.Controls.Add($details)
  foreach ($i in 0..($MAX_ROWS - 1)) {
    $list.Controls.AddRange(@($rowMark[$i], $rowName[$i], $rowDetail[$i]))
  }

  $st = @{
    rows        = @()      # one entry per step, last state each reached
    activeTitle = ""
    activeSince = (Get-Date)
    tipAt       = 0
    tipSince    = (Get-Date)
    started     = (Get-Date)
    cancelled   = $false
    failed      = $false
    showLinks   = $false
    target      = 0.04
    shown       = 0.04
  }

  # The layout only changes when one of these does, and the timer calls
  # Set-Layout every 250 ms: re-assigning Location, Size and Visible each tick
  # made the window relayout four times a second (C38).
  $st.layoutKey = ""

  function Set-Layout {
    $key = "$($st.showLinks)|$($st.failed)|$($details.Visible)"
    if ($key -eq $st.layoutKey) { return }
    $st.layoutKey = $key
    $form.SuspendLayout()
    # Visibility only: the window's size and every position are fixed above
    # (INBOX 1301 D2). Details swaps the log in for the rows, in the panel.
    $visibleLinks = ($st.showLinks -or $st.failed)
    $btnDetails.Visible = $visibleLinks
    $btnCopy.Visible    = $visibleLinks
    $btnCancel.Visible  = $visibleLinks
    Set-LinkRow
    foreach ($i in 0..($MAX_ROWS - 1)) {
      $on = -not $details.Visible
      $rowMark[$i].Visible = $on; $rowName[$i].Visible = $on; $rowDetail[$i].Visible = $on
    }
    $form.ResumeLayout($true)
  }
  Set-Layout

  function Read-Steps {
    $rows = @{}
    $order = @()
    $lines = Get-Content -LiteralPath $StatusFile -ErrorAction SilentlyContinue
    foreach ($line in $lines) {
      if ($null -eq $line) { continue }
      $parts = $line -split '\|'
      if ($parts.Count -lt 5) { continue }
      $state = $parts[$parts.Count - 1].Trim()
      if ($state -ne "active" -and $state -ne "done" -and $state -ne "failed") { continue }
      $step = 0
      $total = 0
      if (-not [int]::TryParse($parts[0].Trim(), [ref]$step)) { continue }
      if (-not [int]::TryParse($parts[1].Trim(), [ref]$total)) { continue }
      if ($total -lt 1 -or $total -gt 20) { continue }
      if ($step -lt 1 -or $step -gt $total) { continue }
      $rowTitle = $parts[2].Trim()
      if (-not $rowTitle) { continue }
      $rowDetailText = ($parts[3..($parts.Count - 2)] -join '|').Trim()
      if (-not $rows.ContainsKey($step)) { $order += $step }
      $rows[$step] = [pscustomobject]@{
        Step = $step; Total = $total; Title = $rowTitle
        Detail = $rowDetailText; State = $state
      }
    }
    return ($order | Sort-Object | ForEach-Object { $rows[$_] })
  }

  # A label is only written when its value differs: WinForms repaints on a
  # write even when the text is the same colour or text it already had for
  # some properties, and four writes a row a quarter second is the flicker.
  function Set-Label($label, [string]$text, $color) {
    if ($label.Text -ne $text) { $label.Text = $text }
    if ($null -ne $color -and $label.ForeColor -ne $color) { $label.ForeColor = $color }
  }

  function Update-Rows($steps) {
    $all = @($steps)
    if ($rowName[0].Width -ne 130) { $rowName[0].Size = New-Object System.Drawing.Size(130, 20) }
    # The most recent MAX_ROWS steps: the running one is always the last, so
    # it stays on screen however many have finished (C02).
    $first = [Math]::Max(0, $all.Count - $MAX_ROWS)
    $form.SuspendLayout()
    for ($i = 0; $i -lt $MAX_ROWS; $i++) {
      if (($first + $i) -ge $all.Count) {
        Set-Label $rowMark[$i] "" $null; Set-Label $rowName[$i] "" $null; Set-Label $rowDetail[$i] "" $null
        continue
      }
      $s = $all[$first + $i]
      if ($s.State -eq "done") {
        Set-Label $rowMark[$i] ([string][char]0x2713) $good
        Set-Label $rowName[$i] $s.Title $muted
        Set-Label $rowDetail[$i] $s.Detail $dim
      } elseif ($s.State -eq "failed") {
        Set-Label $rowMark[$i] ([string][char]0x00D7) $bad
        Set-Label $rowName[$i] $s.Title $bad
        Set-Label $rowDetail[$i] $s.Detail $bad
      } else {
        $secs = [int]((Get-Date) - $st.activeSince).TotalSeconds
        Set-Label $rowMark[$i] ([string][char]0x25CF) $accent
        Set-Label $rowName[$i] $s.Title $ink
        Set-Label $rowDetail[$i] "$($s.Detail)  $($secs)s" $muted
      }
    }
    $form.ResumeLayout($true)
  }

  function Update-Hint($steps) {
    $text = ""
    foreach ($s in @($steps)) {
      if ($s.State -ne "active") { continue }
      $secs = ((Get-Date) - $st.activeSince).TotalSeconds
      if ($s.Title -eq "Dependencies" -and $secs -gt 300) {
        $text = "Dependencies usually finish inside five minutes. A slow connection can take longer."
      } elseif ($s.Title -eq "Update" -and $secs -gt 30) {
        $text = "The update check gives up on its own, and the app starts either way."
      }
    }
    if ($hint.Text -ne $text) { $hint.Text = $text }
  }

  function Read-LogTail([int]$count) {
    if (-not $LogPath) { return "No launcher log for this run yet." }
    if (-not (Test-Path -LiteralPath $LogPath)) { return "No launcher log at $LogPath yet." }
    try {
      $tail = Get-Content -LiteralPath $LogPath -Tail $count -ErrorAction Stop
      if (-not $tail) { return "The launcher log is empty so far." }
      return ($tail -join "`r`n")
    } catch {
      return "Could not read $LogPath."
    }
  }

  $btnDetails.Add_Click({
    if ($st.failed) {
      if ($LogPath -and (Test-Path -LiteralPath $LogPath)) {
        try { Start-Process -FilePath $LogPath } catch { }
      }
      return
    }
    if ($details.Visible) {
      $details.Visible = $false
      $btnDetails.Text = "Details"
    } else {
      $details.Text = Read-LogTail 9
      $details.Visible = $true
      $btnDetails.Text = "Hide details"
    }
    Set-Layout
  })

  $btnCopy.Add_Click({
    # What a person is asked for when they report "it will not start": the
    # steps that ran, how long the current one has been going, the tail of the
    # log, and the launcher's own `--doctor` table. The doctor is run with
    # TESSELLATE_DOCTOR_OFFLINE=1 and a 20 second limit: a live one probes the
    # port the app is about to bind and asks the git remote and the model
    # server, which in the middle of an install makes the thing being
    # diagnosed worse; the offline mode skips exactly those three rows
    # (start.bat, `:doctor_port`, `:doctor_updates`, `:doctor_ollama`).
    try {
      $lines = @("Tessellate launch diagnostics", (Get-Date).ToString("u"), "")
      foreach ($s in @($st.rows)) {
        $lines += ("[{0}] {1}/{2} {3}: {4}" -f $s.State, $s.Step, $s.Total, $s.Title, $s.Detail)
      }
      $lines += ""
      $lines += ("Windows: " + [System.Environment]::OSVersion.VersionString)
      $lines += ("PowerShell: " + $PSVersionTable.PSVersion.ToString())
      if ($LogPath) { $lines += ("Log: " + $LogPath) }
      if ($LauncherPath -and (Test-Path -LiteralPath $LauncherPath)) {
        try {
          $psi = New-Object System.Diagnostics.ProcessStartInfo
          $psi.FileName = $env:ComSpec
          $psi.Arguments = '/c ""' + $LauncherPath + '" --doctor"'
          $psi.UseShellExecute = $false
          $psi.CreateNoWindow = $true
          $psi.RedirectStandardOutput = $true
          $psi.EnvironmentVariables["TESSELLATE_DOCTOR_OFFLINE"] = "1"
          $doc = [System.Diagnostics.Process]::Start($psi)
          if ($doc.WaitForExit(20000)) {
            $lines += ""
            $lines += "Launcher doctor (offline):"
            $lines += $doc.StandardOutput.ReadToEnd()
          } else {
            try { $doc.Kill() } catch { }
            $lines += ""
            $lines += "Launcher doctor (offline): did not finish in 20 seconds"
          }
        } catch {
          $lines += ""
          $lines += "Launcher doctor (offline): could not be run"
        }
      }
      $lines += ""
      $lines += "Last log lines:"
      $lines += (Read-LogTail 20)
      [System.Windows.Forms.Clipboard]::SetText(($lines -join "`r`n"))
      $btnCopy.Text = "Copied"; Set-LinkRow
    } catch {
      $btnCopy.Text = "Could not copy"; Set-LinkRow
    }
  })

  $form.Add_Resize({
    if ($form.WindowState -eq "Normal") { $form.TopMost = $true }
  })

  $btnCancel.Add_Click({
    if ($st.failed) { $form.Close(); return }
    try {
      Set-Content -LiteralPath ($StatusFile + ".cancel") -Value "__cancel__" -ErrorAction Stop
      $st.cancelled = $true
      $btnCancel.Visible = $false
      $status.Text = "Cancelling after this step finishes."
    } catch {
      $status.Text = "Could not cancel. Close the launcher window instead."
    }
  })

  $btnRetry.Add_Click({
    if ($LauncherPath -and (Test-Path -LiteralPath $LauncherPath)) {
      try { Start-Process -FilePath $LauncherPath } catch { }
    }
    $form.Close()
  })

  $drag = @{ on = $false; x = 0; y = 0 }
  $down = { param($s, $e) $drag.on = $true; $drag.x = $e.X; $drag.y = $e.Y }
  $move = {
    param($s, $e)
    if ($drag.on) {
      $form.Location = New-Object System.Drawing.Point(
        ($form.Location.X + $e.X - $drag.x), ($form.Location.Y + $e.Y - $drag.y))
    }
  }
  $up = { param($s, $e) $drag.on = $false }
  foreach ($c in @($form, $logo, $title, $tag, $status, $count, $hint, $tip)) {
    $c.Add_MouseDown($down); $c.Add_MouseMove($move); $c.Add_MouseUp($up)
  }

  function Show-ErrorCard($step) {
    $st.failed = $true
    $barTrack.Visible = $false
    $count.Text = "Stopped at step $($step.Step) of $($step.Total)"
    $status.ForeColor = $bad
    $status.Text = "$($step.Title) failed: $($step.Detail)"
    if ($LogPath) {
      $hint.ForeColor = $muted
      $hint.Text = "Log: $LogPath"
    }
    $tip.Text = "Nothing was lost. Your notes are untouched."
    $btnCancel.Text = "Close"
    $btnCopy.Text = "Copy diagnostics"
    $btnDetails.Text = "Open log"
    $btnRetry.Visible = [bool]($LauncherPath)
    Set-Layout
  }

  $deadline = (Get-Date).AddMinutes($MaxMinutes)

  $timer          = New-Object System.Windows.Forms.Timer
  $timer.Interval = 250
  $timer.Add_Tick({
    try {
      if ((Get-Date) -gt $deadline) { $form.Close(); return }
      if (-not (Test-Path -LiteralPath $StatusFile)) {
        if (-not $st.failed) { $form.Close() }
        return
      }

      if (((Get-Date) - $st.tipSince).TotalSeconds -ge 6) {
        $st.tipAt = ($st.tipAt + 1) % $tips.Count
        $st.tipSince = (Get-Date)
        if (-not $st.failed) { $tip.Text = $tips[$st.tipAt] }
      }

      if ($st.failed) { return }

      $raw = (Get-Content -LiteralPath $StatusFile -Raw -ErrorAction SilentlyContinue)
      if ($null -eq $raw) { return }
      if ($raw -match "__done__") { $form.Close(); return }

      $steps = @(Read-Steps)
      if ($steps.Count -eq 0) { return }
      $st.rows = $steps

      $current = $steps[$steps.Count - 1]
      if ($current.Title -ne $st.activeTitle) {
        $st.activeTitle = $current.Title
        $st.activeSince = (Get-Date)
      }

      $done = @($steps | Where-Object { $_.State -eq "done" }).Count
      $total = $current.Total
      if ($total -lt 1) { $total = 1 }
      $pct = [int](($done * 100) / $total)
      if ($pct -lt 0) { $pct = 0 }
      if ($pct -gt 100) { $pct = 100 }
      # Half a step for the one running, so the bar is never parked at a step
      # boundary while real work happens; the app accent fill eases to this.
      $frac = ($done + 0.5) / $total
      if ($done -ge $total) { $frac = 1.0 }
      $st.target = [Math]::Max(0.04, [Math]::Min(1.0, $frac))

      Update-Rows $steps
      Update-Hint $steps

      $elapsed = [int]((Get-Date) - $st.started).TotalSeconds
      $st.showLinks = ($elapsed -ge $SHOW_LINKS_AFTER)
      $counted = "Step $([Math]::Min($total, $done + 1)) of $total"
      if ($done -ge $total) { $counted = "Done" }
      if ($count.Text -ne $counted) { $count.Text = $counted }

      # One status line: what is running now, in plain words.
      $line = "$($current.Title)"
      if ($current.Detail) { $line = "$($current.Title): $($current.Detail)" }
      if ($st.cancelled) { $line = "Cancelling after this step finishes." }
      if ($status.Text -ne $line) { $status.Text = $line }

      $failedStep = @($steps | Where-Object { $_.State -eq "failed" })
      if ($failedStep.Count -gt 0) { Show-ErrorCard $failedStep[0] } else { Set-Layout }
    } catch {
    }
  })
  $timer.Start()

  $easeTimer          = New-Object System.Windows.Forms.Timer
  $easeTimer.Interval = 33
  $easeTimer.Add_Tick({
    $gap = $st.target - $st.shown
    if ([Math]::Abs($gap) -gt 0.001) {
      $st.shown = $st.shown + $gap * 0.12
      $barFill.Width = [int]([Math]::Max(4, $BAR_W * $st.shown))
    }
  })
  $easeTimer.Start()

  [void]$form.ShowDialog()
  $timer.Stop()
  $easeTimer.Stop()
  $form.Dispose()
  $logoBmp.Dispose()
} catch {
  exit 0
}
