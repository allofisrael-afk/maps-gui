# build_apk.ps1 - Install Flutter + Android SDK and build APK
# Run from: d:\PY-IS\maps-gui\
# Output:   d:\PY-IS\maps-gui\maps-gui-android\build\app\outputs\flutter-apk\app-release.apk
$ErrorActionPreference = 'Stop'

$DEV          = "C:\dev"
$FLUTTER_DIR  = "$DEV\flutter"
$ANDROID_DIR  = "$DEV\android-sdk"
$CMDTOOLS_DIR = "$ANDROID_DIR\cmdline-tools\latest"
$PROJECT_SRC  = "$PSScriptRoot\maps-gui-android-src"
$PROJECT_DIR  = "$PSScriptRoot\maps-gui-android"

$FLUTTER_URL  = "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.41.9-stable.zip"
$CMDTOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-14742923_latest.zip"

function Log($msg) { Write-Host "[BUILD] $msg" -ForegroundColor Cyan }
function Ok($msg)  { Write-Host "[  OK ] $msg" -ForegroundColor Green }
function Err($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Force $DEV         | Out-Null
New-Item -ItemType Directory -Force $ANDROID_DIR | Out-Null

# --- Step 1: Java 17 ---
Log "Checking Java..."
$javaOk = $false
try {
    $jv = java -version 2>&1 | Select-Object -First 1
    if ($jv -match "17\.|21\.") { $javaOk = $true }
} catch {}

if (-not $javaOk) {
    Log "Installing Java 17 via winget..."
    winget install --id Microsoft.OpenJDK.17 --accept-source-agreements --accept-package-agreements --silent
}

# Locate java.exe regardless of PATH (winget may not update current session PATH)
$javaExe = $null
$searchRoots = @(
    "C:\Program Files\Microsoft",
    "C:\Program Files\Eclipse Adoptium",
    "C:\Program Files\Java",
    "C:\Program Files\OpenJDK"
)
foreach ($root in $searchRoots) {
    if (Test-Path $root) {
        $found = Get-ChildItem $root -Filter "java.exe" -Recurse -ErrorAction SilentlyContinue |
                 Where-Object { $_.FullName -notmatch "jre" } |
                 Select-Object -First 1
        if ($found) { $javaExe = $found.FullName; break }
    }
}
if (-not $javaExe) {
    # Refresh PATH and try again
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
    $javaExe = (Get-Command java -ErrorAction SilentlyContinue).Source
}
if (-not $javaExe) { Err "Java not found. Run the script again from a new terminal." }

$env:JAVA_HOME = Split-Path (Split-Path $javaExe)
$env:PATH      = "$env:JAVA_HOME\bin;$env:PATH"
Ok "Java: $javaExe"

# --- Step 2: Flutter SDK ---
if (-not (Test-Path "$FLUTTER_DIR\bin\flutter.bat")) {
    $zipFlutter = "$DEV\flutter.zip"
    Log "Downloading Flutter SDK (~700MB)..."
    Invoke-WebRequest -Uri $FLUTTER_URL -OutFile $zipFlutter -UseBasicParsing
    Log "Extracting Flutter..."
    Expand-Archive -Path $zipFlutter -DestinationPath $DEV -Force
    Remove-Item $zipFlutter
    Ok "Flutter extracted to $FLUTTER_DIR"
} else {
    Ok "Flutter already present"
}
$env:PATH = "$FLUTTER_DIR\bin;$env:PATH"

# --- Step 3: Android cmdline-tools ---
if (-not (Test-Path "$CMDTOOLS_DIR\bin\sdkmanager.bat")) {
    $zipTools = "$DEV\cmdtools.zip"
    Log "Downloading Android cmdline-tools (~150MB)..."
    Invoke-WebRequest -Uri $CMDTOOLS_URL -OutFile $zipTools -UseBasicParsing
    Log "Extracting cmdline-tools..."
    $tmpDir = "$DEV\cmdtools-tmp"
    Expand-Archive -Path $zipTools -DestinationPath $tmpDir -Force
    New-Item -ItemType Directory -Force $CMDTOOLS_DIR | Out-Null
    Copy-Item "$tmpDir\cmdline-tools\*" "$CMDTOOLS_DIR\" -Recurse -Force
    Remove-Item $zipTools, $tmpDir -Recurse -Force
    Ok "Android cmdline-tools extracted"
} else {
    Ok "Android cmdline-tools already present"
}
$env:ANDROID_HOME = $ANDROID_DIR
$env:PATH = "$CMDTOOLS_DIR\bin;$ANDROID_DIR\platform-tools;$env:PATH"

# --- Step 4: SDK packages ---
if (-not (Test-Path "$ANDROID_DIR\build-tools\35.0.0")) {
    Log "Installing Android SDK packages..."
    "y`ny`ny`ny`ny`ny`ny`n" | & "$CMDTOOLS_DIR\bin\sdkmanager.bat" `
        --sdk_root=$ANDROID_DIR `
        "platform-tools" "build-tools;35.0.0" "platforms;android-35"
    Ok "Android SDK packages installed"
} else {
    Ok "Android SDK packages already present"
}

Log "Accepting Android licenses..."
"y`ny`ny`ny`ny`ny`ny`ny`ny`n" | & "$CMDTOOLS_DIR\bin\sdkmanager.bat" --sdk_root=$ANDROID_DIR --licenses 2>&1 | Out-Null
Ok "Licenses accepted"

# --- Step 5: Flutter project scaffold ---
if (-not (Test-Path "$PROJECT_DIR\android\build.gradle")) {
    Log "Creating Flutter project scaffold..."
    Set-Location $PSScriptRoot
    & "$FLUTTER_DIR\bin\flutter.bat" create `
        --org com.mapsapp `
        --project-name maps_gui_android `
        --no-pub `
        $PROJECT_DIR
    if ($LASTEXITCODE -ne 0) { Err "flutter create failed" }
    Ok "Flutter scaffold created"
} else {
    Ok "Flutter scaffold already exists"
}

# --- Step 6: Copy source files ---
Log "Copying source files..."
Copy-Item "$PROJECT_SRC\pubspec.yaml" "$PROJECT_DIR\pubspec.yaml" -Force
# Use robocopy to merge lib/ contents without creating lib/lib/ duplication
# (PowerShell 5.1 Copy-Item with trailing backslash copies the dir *into* the dest)
robocopy "$PROJECT_SRC\lib" "$PROJECT_DIR\lib" /E /IS /IT | Out-Null
Copy-Item "$PROJECT_SRC\android_manifest.xml" `
    "$PROJECT_DIR\android\app\src\main\AndroidManifest.xml" -Force
Ok "Source files copied"

# --- Step 7: flutter pub get ---
Set-Location $PROJECT_DIR
Log "Running flutter pub get..."
& "$FLUTTER_DIR\bin\flutter.bat" pub get
if ($LASTEXITCODE -ne 0) { Err "flutter pub get failed" }
Ok "pub get succeeded"

# --- Step 8: Build APK ---
Log "Building release APK..."
& "$FLUTTER_DIR\bin\flutter.bat" build apk --release
if ($LASTEXITCODE -ne 0) { Err "flutter build apk failed" }

$APK = "$PROJECT_DIR\build\app\outputs\flutter-apk\app-release.apk"
if (Test-Path $APK) {
    $sizeMB = [math]::Round((Get-Item $APK).Length / 1MB, 1)
    Ok "===== APK built successfully ($sizeMB MB) ====="
    Write-Host $APK -ForegroundColor Yellow
    explorer (Split-Path $APK)
} else {
    Err "APK file not found - check errors above"
}
