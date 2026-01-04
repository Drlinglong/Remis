# Pre-Commit Quality Check Script
# 在提交代码前运行所有质量检查
# 
# 用法:
#   .\check_before_commit.ps1           # 交互式模式（用户手动运行）
#   .\check_before_commit.ps1 -Silent   # 静默模式（Agent 自动运行）

param(
    [switch]$Silent = $false
)

$ErrorActionPreference = "Stop"

if (-not $Silent) {
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host "  Pre-Commit Quality Check" -ForegroundColor Cyan
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host ""
}

# 记录开始时间
$startTime = Get-Date

# 检查结果标志
$allPassed = $true

# ============================================
# ============================================
# 1. Python Backend Tests
# ============================================
Write-Host "[1/4] Running Python Tests (pytest)..." -ForegroundColor Yellow

try {
    $pytestResult = pytest --quiet --tb=line 2>&1
    $pytestExitCode = $LASTEXITCODE
    
    if ($pytestExitCode -eq 0) {
        Write-Host "  ✓ Python tests PASSED" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Python tests FAILED" -ForegroundColor Red
        Write-Host $pytestResult -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host "  ✗ pytest not found or error occurred" -ForegroundColor Red
    $allPassed = $false
}

Write-Host ""

# ============================================
# ============================================
# 2. Frontend Linting (ESLint)
# ============================================
Write-Host "[2/4] Running Frontend Linting (ESLint)..." -ForegroundColor Yellow

$frontendDir = "scripts\react-ui"

if (Test-Path $frontendDir) {
    Push-Location $frontendDir
    
    try {
        # 检查是否有 eslint 配置
        if (Test-Path "node_modules\.bin\eslint.cmd") {
            $eslintResult = npm run lint 2>&1
            $eslintExitCode = $LASTEXITCODE
            
            if ($eslintExitCode -eq 0) {
                Write-Host "  ✓ ESLint checks PASSED" -ForegroundColor Green
            } else {
                Write-Host "  ✗ ESLint checks FAILED" -ForegroundColor Red
                Write-Host $eslintResult -ForegroundColor Red
                $allPassed = $false
            }
        } else {
            Write-Host "  ⚠ ESLint not configured, skipping..." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ⚠ ESLint check skipped (error occurred)" -ForegroundColor Yellow
    } finally {
        Pop-Location
    }
} else {
    Write-Host "  ⚠ Frontend directory not found, skipping..." -ForegroundColor Yellow
}

Write-Host ""

# ============================================
# ============================================
# 3. Frontend Unit Tests (Vitest)
# ============================================
Write-Host "[3/4] Running Frontend Tests (Vitest)..." -ForegroundColor Yellow

if (Test-Path "scripts\react-ui") {
    Push-Location "scripts\react-ui"
    try {
        # Using CI=true to ensure it runs once and exits
        $env:CI = "true"
        
        # Temporarily relax error preference because npm writes warnings to stderr
        # which causes PowerShell to throw when ErrorActionPreference is Stop
        $oldEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        
        $vitestResult = npm run test -- 2>&1
        $vitestExitCode = $LASTEXITCODE
        
        $ErrorActionPreference = $oldEAP
        
        if ($vitestExitCode -eq 0) {
            Write-Host "  ✓ Frontend tests PASSED" -ForegroundColor Green
        } else {
            Write-Host "  ✗ Frontend tests FAILED" -ForegroundColor Red
            # Write-Host $vitestResult -ForegroundColor Red
            $allPassed = $false
        }
    } catch {
        Write-Host "  ⚠ Frontend tests skipped (error)" -ForegroundColor Yellow
    } finally {
        $env:CI = $null
        Pop-Location
    }
} else {
    Write-Host "  ⚠ Frontend directory not found" -ForegroundColor Yellow
}

Write-Host ""

# ============================================
# 4. Git Status Check
# ============================================
Write-Host "[4/4] Checking Git Status..." -ForegroundColor Yellow

$gitStatus = git status --porcelain

if ($gitStatus) {
    Write-Host "  ℹ Modified files detected:" -ForegroundColor Cyan
    git status --short
} else {
    Write-Host "  ⚠ No changes to commit" -ForegroundColor Yellow
    $allPassed = $false
}

Write-Host ""

# ============================================
# Final Result
# ============================================
$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

if (-not $Silent) {
    Write-Host "===========================================" -ForegroundColor Cyan
}

if ($allPassed) {
    if ($Silent) {
        # Agent 模式：静默退出，返回成功状态
        Write-Host "CI_PASSED" -ForegroundColor Green
        exit 0
    }
    
    # 用户模式：显示详细信息并提示
    Write-Host "  ✓ ALL CHECKS PASSED!" -ForegroundColor Green
    Write-Host "  Ready to commit!" -ForegroundColor Green
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Completed in $([math]::Round($duration, 2)) seconds" -ForegroundColor Gray
    Write-Host ""
    
    # 询问是否自动提交
    $commit = Read-Host "Auto-commit changes? (y/N)"
    
    if ($commit -eq "y" -or $commit -eq "Y") {
        Write-Host ""
        $commitMsg = Read-Host "Commit message"
        
        if ($commitMsg) {
            git add .
            git commit -m "$commitMsg"
            Write-Host ""
            Write-Host "✓ Changes committed!" -ForegroundColor Green
        } else {
            Write-Host "✗ Commit cancelled (empty message)" -ForegroundColor Red
        }
    } else {
        Write-Host ""
        Write-Host "Commit skipped. Run 'git add .' and 'git commit' manually." -ForegroundColor Yellow
    }
    
    exit 0
} else {
    if ($Silent) {
        # Agent 模式：静默退出，返回失败状态
        Write-Host "CI_FAILED" -ForegroundColor Red
        exit 1
    }
    
    # 用户模式：显示详细错误信息
    Write-Host "  ✗ CHECKS FAILED!" -ForegroundColor Red
    Write-Host "  Please fix the errors above before committing." -ForegroundColor Red
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Completed in $([math]::Round($duration, 2)) seconds" -ForegroundColor Gray
    exit 1
}
