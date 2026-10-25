#requires -Version 5.1
<#
  dsh-ctl.ps1 - desktop eyes & hands for the DSH agent (Windows)
  Pure ASCII source on purpose: Windows PowerShell 5.1 misreads non-BOM UTF-8.
  Every action prints a short machine-readable result on stdout.
#>
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('shot', 'windows', 'tree', 'text', 'click', 'type', 'keys', 'focus', 'launch', 'clip', 'cursor', 'rect', 'find', 'ocr')]
  [string]$Action,

  [int]$X = 0, [int]$Y = 0, [int]$W = 0, [int]$H = 0,
  [string]$Text = '',
  [string]$Title = '',
  [int]$ProcId = 0,
  [string]$Out = '',
  [int]$Limit = 80,
  [switch]$Double,
  [switch]$Virtual,
  [switch]$Set,
  [string]$App = '',
  [string]$AppArgs = ''
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

# Resolve paths relative to THIS script so the skill folder is self-contained
# and movable. ocr.py lives in the sibling screen-ocr skill.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)   # ...\skills

# Find a usable Python: prefer PATH, then a couple of common install roots.
# Hardcoding one version breaks on any other machine.
function Resolve-Python {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -notlike '*WindowsApps*') { return $cmd.Source }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    try {
      $real = & $py.Source -c "import sys;print(sys.executable)" 2>$null
      if ($real -and (Test-Path $real)) { return $real }
    } catch {}
  }
  foreach ($cand in @(
    'C:\Python314\python.exe', 'C:\Python313\python.exe', 'C:\Python312\python.exe',
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
  )) {
    if ($cand -and (Test-Path $cand)) { return $cand }
  }
  return $null
}
$PY_EXE = Resolve-Python

$OCR_CANDIDATES = @(
  (Join-Path $skillRoot 'screen-ocr\scripts\ocr.py'),
  (Join-Path $env:USERPROFILE '.dsh\tools\ocr.py')
)
$OCR_PY = $OCR_CANDIDATES | Where-Object { Test-Path $_ } | Select-Object -First 1

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

if (-not ('DshGui' -as [type])) {
  Add-Type -ReferencedAssemblies System.Drawing, System.Windows.Forms -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

public class DshGui {
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] static extern void mouse_event(uint f, int dx, int dy, uint d, UIntPtr e);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet = CharSet.Auto)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet = CharSet.Auto)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint c);
  [DllImport("user32.dll")] static extern uint MapVirtualKey(uint c, uint m);
  [DllImport("user32.dll")] static extern IntPtr GetWindowDC(IntPtr h);
  [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr h, IntPtr dc);
  [DllImport("gdi32.dll")] static extern bool BitBlt(IntPtr d, int x, int y, int w, int h, IntPtr s, int sx, int sy, uint rop);

  public struct RECT { public int L, T, R, B; }
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);

  public class WinInfo { public IntPtr Hwnd; public uint Pid; public string Title; public string Cls; public int Rx, Ry, Rw, Rh; public bool Fg; }

  public static List<WinInfo> Windows() {
    var list = new List<WinInfo>();
    IntPtr fg = GetForegroundWindow();
    EnumWindows(delegate(IntPtr h, IntPtr p) {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(512); GetWindowText(h, sb, 512);
      string t = sb.ToString();
      if (t.Length == 0) return true;
      var cb = new StringBuilder(256); GetClassName(h, cb, 256);
      RECT r; GetWindowRect(h, out r);
      uint pid; GetWindowThreadProcessId(h, out pid);
      list.Add(new WinInfo { Hwnd = h, Pid = pid, Title = t, Cls = cb.ToString(),
        Rx = r.L, Ry = r.T, Rw = r.R - r.L, Rh = r.B - r.T, Fg = (h == fg) });
      return true;
    }, IntPtr.Zero);
    return list;
  }

  public static IntPtr Find(string pattern, int pid) {
    var re = new System.Text.RegularExpressions.Regex(pattern, System.Text.RegularExpressions.RegexOptions.IgnoreCase);
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr p) {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(512); GetWindowText(h, sb, 512);
      string t = sb.ToString();
      if (t.Length == 0) return true;
      uint wpid; GetWindowThreadProcessId(h, out wpid);
      bool ok = (pid > 0) ? (wpid == (uint)pid) : re.IsMatch(t);
      if (ok) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }

  // ALT tap unlocks the foreground lock so a background process may activate a window.
  public static bool Focus(IntPtr h) {
    if (h == IntPtr.Zero) return false;
    if (GetForegroundWindow() == h) return true;
    for (int i = 0; i < 3; i++) {
      keybd_event(0x12, 0, 0, UIntPtr.Zero);
      keybd_event(0x12, 0, 2, UIntPtr.Zero);
      System.Threading.Thread.Sleep(60);
      if (IsIconic(h)) ShowWindow(h, 9); else ShowWindow(h, 5);
      SetForegroundWindow(h);
      System.Threading.Thread.Sleep(120);
      if (GetForegroundWindow() == h) return true;
    }
    return GetForegroundWindow() == h;
  }

  public static void ClickAt(int x, int y, bool dbl) {
    SetCursorPos(x, y);
    System.Threading.Thread.Sleep(40);
    mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero);
    mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero);
    if (dbl) { System.Threading.Thread.Sleep(60); mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero); mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero); }
  }

  // Unicode-safe typing: works for Chinese/emoji, independent of keyboard layout.
  public static void TypeText(string s) {
    foreach (char c in s) {
      if (c == '\n') { PressVk(0x0D); continue; }
      if (c == '\t') { PressVk(0x09); continue; }
      SendUnicode(c);
      System.Threading.Thread.Sleep(8);
    }
  }
  static void SendUnicode(char c) {
    INPUT[] inp = new INPUT[2];
    inp[0].type = 1; inp[0].u.ki.wVk = 0; inp[0].u.ki.wScan = c; inp[0].u.ki.dwFlags = 0x0004;
    inp[1].type = 1; inp[1].u.ki.wVk = 0; inp[1].u.ki.wScan = c; inp[1].u.ki.dwFlags = 0x0004 | 0x0002;
    SendInput(2, inp, Marshal.SizeOf(typeof(INPUT)));
  }
  public static void PressVk(byte vk) {
    byte sc = (byte)MapVirtualKey(vk, 0);
    keybd_event(vk, sc, 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(30);
    keybd_event(vk, sc, 2, UIntPtr.Zero);
  }
  // combo like "ctrl+s", "alt+f4", "win+r", "shift+tab"
  public static void Combo(string combo) {
    var parts = combo.ToLower().Split('+');
    var mods = new List<byte>();
    byte main = 0;
    foreach (var raw in parts) {
      var p = raw.Trim();
      if (p == "ctrl" || p == "control") mods.Add(0x11);
      else if (p == "alt") mods.Add(0x12);
      else if (p == "shift") mods.Add(0x10);
      else if (p == "win") mods.Add(0x5B);
      else if (p.Length == 1) main = (byte)char.ToUpper(p[0]);
      else if (p.Length > 1 && p[0] == 'f') { int fn; if (int.TryParse(p.Substring(1), out fn)) main = (byte)(0x6F + fn); }
      else if (p == "enter" || p == "return") main = 0x0D;
      else if (p == "tab") main = 0x09;
      else if (p == "esc" || p == "escape") main = 0x1B;
      else if (p == "space") main = 0x20;
      else if (p == "backspace") main = 0x08;
      else if (p == "delete" || p == "del") main = 0x2E;
      else if (p == "home") main = 0x24;
      else if (p == "end") main = 0x23;
      else if (p == "left") main = 0x25;
      else if (p == "up") main = 0x26;
      else if (p == "right") main = 0x27;
      else if (p == "down") main = 0x28;
      else if (p == "pgup") main = 0x21;
      else if (p == "pgdn") main = 0x22;
    }
    foreach (var m in mods) keybd_event(m, (byte)MapVirtualKey(m, 0), 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(30);
    if (main != 0) PressVk(main);
    for (int i = mods.Count - 1; i >= 0; i--) keybd_event(mods[i], (byte)MapVirtualKey(mods[i], 0), 2, UIntPtr.Zero);
  }

  public static Rectangle Virtual() { return SystemInformation.VirtualScreen; }

  public static void SaveShot(int x, int y, int w, int h, string path) {
    using (var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb))
    using (var g = Graphics.FromImage(bmp)) {
      g.CopyFromScreen(x, y, 0, 0, new Size(w, h), CopyPixelOperation.SourceCopy);
      bmp.Save(path, ImageFormat.Png);
    }
  }

  // GDI capture of one window, works even when it is partially covered.
  public static bool ShotWindow(IntPtr h, string path) {
    RECT r; if (!GetWindowRect(h, out r)) return false;
    int w = r.R - r.L, ht = r.B - r.T;
    if (w <= 0 || ht <= 0) return false;
    using (var bmp = new Bitmap(w, ht, PixelFormat.Format32bppArgb))
    using (var g = Graphics.FromImage(bmp)) {
      IntPtr src = GetWindowDC(h);
      IntPtr dst = g.GetHdc();
      bool ok = BitBlt(dst, 0, 0, w, ht, src, 0, 0, 0x00CC0020);
      g.ReleaseHdc(dst); ReleaseDC(h, src);
      bmp.Save(path, ImageFormat.Png);
      return ok;
    }
  }

  [StructLayout(LayoutKind.Sequential)]
  struct INPUT { public int type; public InputUnion u; }
  [StructLayout(LayoutKind.Explicit)]
  struct InputUnion { [FieldOffset(0)] public KEYBDINPUT ki; [FieldOffset(0)] public MOUSEINPUT mi; }
  [StructLayout(LayoutKind.Sequential)]
  struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }
  [StructLayout(LayoutKind.Sequential)]
  struct MOUSEINPUT { public int dx; public int dy; public uint mouseData; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }
  [DllImport("user32.dll", SetLastError = true)]
  static extern uint SendInput(uint n, INPUT[] inputs, int size);
}
'@
}

# ---------------- actions ----------------

function Get-TargetWindow {
  if ($ProcId -gt 0) { return [DshGui]::Find('', $ProcId) }
  if ($Title) { return [DshGui]::Find($Title, 0) }
  return [IntPtr]::Zero
}

switch ($Action) {

  'windows' {
    [DshGui]::Windows() | ForEach-Object {
      [pscustomobject]@{ hwnd = $_.Hwnd; pid = $_.Pid; title = $_.Title; cls = $_.Cls
        rect = "$($_.Rx),$($_.Ry),$($_.Rw),$($_.Rh)"; fg = $_.Fg }
    } | Sort-Object fg -Descending | Format-Table -AutoSize | Out-String -Width 200
  }

  'shot' {
    if (-not $Out) { $Out = Join-Path $env:TEMP ("dsh_shot_" + (Get-Date -Format 'HHmmss') + ".png") }
    $win = Get-TargetWindow
    if ($win -ne [IntPtr]::Zero) {
      [void][DshGui]::ShotWindow($win, $Out)
    } else {
      $v = [DshGui]::Virtual()
      if ($W -le 0) { $x = $v.X; $y = $v.Y; $w = $v.Width; $h = $v.Height }
      else { $x = $X; $y = $Y; $w = $W; $h = $H }
      [DshGui]::SaveShot($x, $y, $w, $h, $Out)
    }
    $f = Get-Item $Out
    $img = [System.Drawing.Image]::FromFile($Out)
    "{0} {1}x{2} {3} bytes" -f $f.FullName, $img.Width, $img.Height, $f.Length
    $img.Dispose()
  }

  'cursor' { [DshGui]::Virtual() | ForEach-Object { "virtual screen: $($_.X),$($_.Y) $($_.Width)x$($_.Height)" } }

  'focus' {
    $win = Get-TargetWindow
    if ($win -eq [IntPtr]::Zero) { "ERR window not found"; exit 1 }
    $ok = [DshGui]::Focus($win)
    "focus=$ok hwnd=$win"
  }

  'click' {
    $win = Get-TargetWindow
    if ($win -ne [IntPtr]::Zero) { [void][DshGui]::Focus($win); Start-Sleep -Milliseconds 150 }
    [DshGui]::ClickAt($X, $Y, [bool]$Double)
    "clicked $X,$Y double=$([bool]$Double)"
  }

  'type' {
    $win = Get-TargetWindow
    if ($win -ne [IntPtr]::Zero) {
      if (-not [DshGui]::Focus($win)) { "ERR could not focus window"; exit 1 }
      Start-Sleep -Milliseconds 150
    }
    [DshGui]::TypeText($Text)
    "typed {0} chars" -f $Text.Length
  }

  'keys' {
    $win = Get-TargetWindow
    if ($win -ne [IntPtr]::Zero) { [void][DshGui]::Focus($win); Start-Sleep -Milliseconds 120 }
    foreach ($c in ($Text -split ',')) { if ($c.Trim()) { [DshGui]::Combo($c.Trim()); Start-Sleep -Milliseconds 120 } }
    "sent keys: $Text"
  }

  'launch' {
    if (-not $App) { 'ERR -App required'; exit 1 }
    $p = if ($AppArgs) { Start-Process -FilePath $App -ArgumentList $AppArgs -PassThru } else { Start-Process -FilePath $App -PassThru }
    Start-Sleep -Milliseconds 700
    "started pid=$($p.Id) path=$App"
  }

  'clip' {
    if ($Set) { Set-Clipboard -Value $Text; "clipboard set ($($Text.Length) chars)" }
    else { $v = Get-Clipboard -Raw; "--- clipboard ($($v.Length) chars) ---"; $v }
  }

  'find' {
    # Locate text on screen and print its centre coordinates.
    # Strategy: UIA first (exact), then OCR (canvas/custom-drawn UIs).
    #
    # Two traps this code defends against, both hit for real:
    #  1. Searching the whole desktop matches the agent's own chat transcript
    #     (the DSH window contains every word ever discussed). Always scope to
    #     -ProcId / -Title when you know the target app.
    #  2. UIA happily reports coordinates off the virtual screen (y = -969).
    #     Any hit outside the virtual screen bounds is discarded.
    if (-not $Text) { "ERR: -Text required"; exit 1 }

    # virtual screen bounds
    Add-Type -AssemblyName System.Windows.Forms
    $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $minX = $vs.Left; $minY = $vs.Top
    $maxX = $vs.Left + $vs.Width; $maxY = $vs.Top + $vs.Height

    $win = Get-TargetWindow
    $root = if ($win -ne [IntPtr]::Zero) { [System.Windows.Automation.AutomationElement]::FromHandle($win) }
            else { [System.Windows.Automation.AutomationElement]::RootElement }

    $found = $null
    $all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($e in $all) {
      $nm = $e.Current.Name
      if (-not $nm) { continue }
      if ($nm -notlike "*$Text*") { continue }
      $r = $e.Current.BoundingRectangle
      if ([double]::IsInfinity($r.X) -or $r.Width -lt 1 -or $r.Height -lt 1) { continue }
      $cx = [int]($r.X + $r.Width / 2)
      $cy = [int]($r.Y + $r.Height / 2)
      # discard anything that is not on a real screen
      if ($cx -lt $minX -or $cx -gt $maxX -or $cy -lt $minY -or $cy -gt $maxY) { continue }
      $cand = [pscustomobject]@{
        Source = 'UIA'; X = $cx; Y = $cy
        W = [int]$r.Width; H = [int]$r.Height
        Name = $nm; Cls = $e.Current.ClassName
      }
      # exact match beats substring; smaller beats larger
      $candExact = ($nm.Trim() -eq $Text)
      if ($null -eq $found) { $found = $cand; $foundExact = $candExact; continue }
      if ($candExact -and -not $foundExact) { $found = $cand; $foundExact = $true; continue }
      if ($candExact -eq $foundExact -and ($cand.W * $cand.H) -lt ($found.W * $found.H)) { $found = $cand }
    }

    if ($found) {
      "{0},{1}  <{2}>  {3}x{4}  `"{5}`"" -f $found.X, $found.Y, $found.Cls, $found.W, $found.H, $found.Name
      "  source: UIA (exact)"
      exit 0
    }

    # ---- OCR fallback ----
    # PowerShell 5.1 passes non-ASCII argv to native exes using the ANSI
    # codepage, garbling Chinese ("番剧" arrives as mojibake). Pass the query
    # base64-encoded (pure ASCII on the wire) and let Python decode it.
    if (-not $OCR_PY -or -not (Test-Path $PY_EXE)) {
      "NOT FOUND: $Text  (no UIA match; OCR tool unavailable)"
      exit 2
    }
    $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Text))
    $ocrArgs = @($OCR_PY, 'find-b64', $b64)
    if ($W -gt 0 -and $H -gt 0) {
      $ocrArgs += @('--region', "$X,$Y,$W,$H")
    }
    $out = & $PY_EXE @ocrArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
      "NOT FOUND: $Text  (UIA and OCR both failed)"
      $out | ForEach-Object { "  $_" }
      exit 2
    }
    $out
    "  source: OCR (approx)"
  }

  'ocr' {
    # Dump all on-screen text with coordinates.
    if (-not $OCR_PY) { "ERR: ocr.py not found (expected in screen-ocr\scripts)"; exit 1 }
    & $PY_EXE $OCR_PY dump
  }

  'tree' {
    $win = Get-TargetWindow
    $root = if ($win -ne [IntPtr]::Zero) { [System.Windows.Automation.AutomationElement]::FromHandle($win) }
            else { [System.Windows.Automation.AutomationElement]::RootElement }
    $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
    $script:n = 0
    function Walk($el, $depth) {
      if ($script:n -ge $Limit -or $depth -gt 12) { return }
      $c = $el.Current
      $r = $c.BoundingRectangle
      $label = $c.Name
      if ($label.Length -gt 70) { $label = $label.Substring(0, 70) }
      $script:n++
      ('{0}{1} | {2} | name="{3}" | id="{4}" | {5},{6} {7}x{8}' -f ('  ' * $depth), $c.ControlType.ProgrammaticName.Replace('ControlType.', ''), $c.ClassName, $label, $c.AutomationId, [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height)
      $child = $walker.GetFirstChild($el)
      while ($child -ne $null -and $script:n -lt $Limit) {
        Walk $child ($depth + 1)
        $child = $walker.GetNextSibling($child)
      }
    }
    Walk $root 0
    "(elements shown: $script:n, limit $Limit)"
  }

  'text' {
    $win = Get-TargetWindow
    $root = if ($win -ne [IntPtr]::Zero) { [System.Windows.Automation.AutomationElement]::FromHandle($win) }
            else { [System.Windows.Automation.AutomationElement]::RootElement }
    $all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    $seen = New-Object System.Collections.Generic.HashSet[string]
    $i = 0
    foreach ($e in $all) {
      if ($i -ge $Limit) { break }
      $t = $null
      try { $tp = $e.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern); if ($tp) { $t = $tp.DocumentRange.GetText(4000) } } catch {}
      if (-not $t) { try { $vp = $e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern); if ($vp) { $t = $vp.Current.Value } } catch {} }
      if ($t) {
        $t = $t.Trim()
        if ($t -and $seen.Add($t)) {
          $nm = $e.Current.Name; if ($nm.Length -gt 60) { $nm = $nm.Substring(0, 60) }
          "### {0} [{1}]" -f $nm, $e.Current.ControlType.ProgrammaticName.Replace('ControlType.', '')
          $t
          ''
          $i++
        }
      }
    }
    "(text blocks: $i)"
  }
}
