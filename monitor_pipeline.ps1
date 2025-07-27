# Monitor Kafka Pipeline Data Flow
# Run this script to see real-time data from producer to consumer

param(
    [string]$Topic = "stock_market_data",
    [string]$BootstrapServer = "localhost:9092",
    [int]$RefreshInterval = 5
)

Write-Host "=== Kafka Pipeline Monitor ===" -ForegroundColor Green
Write-Host "Topic: $Topic" -ForegroundColor Yellow
Write-Host "Bootstrap Server: $BootstrapServer" -ForegroundColor Yellow
Write-Host "Refresh Interval: $RefreshInterval seconds" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop monitoring" -ForegroundColor Red
Write-Host ""

# Function to get message count
function Get-MessageCount {
    try {
        $result = kafka-run-class.bat kafka.tools.GetOffsetShell --bootstrap-server $BootstrapServer --topic $Topic --time -1
        $lines = $result -split "`n" | Where-Object { $_ -match "$Topic" }
        $totalMessages = 0
        foreach ($line in $lines) {
            if ($line -match "partition:0:(\d+)") {
                $totalMessages += [int]$matches[1]
            }
        }
        return $totalMessages
    }
    catch {
        return 0
    }
}

# Function to get latest messages
function Get-LatestMessages {
    try {
        $messages = kafka-console-consumer.bat --bootstrap-server $BootstrapServer --topic $Topic --max-messages 5 --timeout-ms 1000 2>$null
        return $messages
    }
    catch {
        return @()
    }
}

# Function to format JSON for display
function Format-JsonMessage {
    param([string]$JsonString)
    try {
        $obj = $JsonString | ConvertFrom-Json
        $formatted = @"
Symbol: $($obj.symbol)
Price: `$$($obj.current_price)
Time: $($obj.timestamp)
Volume: $($obj.volume)
"@
        return $formatted
    }
    catch {
        return $JsonString
    }
}

# Main monitoring loop
$lastCount = 0
$startTime = Get-Date

while ($true) {
    try {
        Clear-Host
        Write-Host "=== Kafka Pipeline Monitor ===" -ForegroundColor Green
        Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
        Write-Host ""
        
        # Get current message count
        $currentCount = Get-MessageCount
        $newMessages = $currentCount - $lastCount
        $elapsed = (Get-Date) - $startTime
        
        Write-Host "📊 Statistics:" -ForegroundColor Yellow
        Write-Host "   Total Messages: $currentCount" -ForegroundColor White
        Write-Host "   New Messages: $newMessages" -ForegroundColor Green
        Write-Host "   Messages/Second: $([math]::Round($currentCount / $elapsed.TotalSeconds, 2))" -ForegroundColor White
        Write-Host "   Runtime: $($elapsed.ToString('hh\:mm\:ss'))" -ForegroundColor White
        Write-Host ""
        
        # Show latest messages
        Write-Host "📨 Latest Messages:" -ForegroundColor Yellow
        $latestMessages = Get-LatestMessages
        if ($latestMessages.Count -gt 0) {
            foreach ($msg in $latestMessages) {
                if ($msg -match "^{") {
                    Write-Host (Format-JsonMessage $msg) -ForegroundColor Cyan
                    Write-Host "---" -ForegroundColor Gray
                }
            }
        } else {
            Write-Host "   No recent messages" -ForegroundColor Gray
        }
        
        Write-Host ""
        Write-Host "🔄 Refreshing in $RefreshInterval seconds... (Ctrl+C to stop)" -ForegroundColor Red
        
        $lastCount = $currentCount
        Start-Sleep -Seconds $RefreshInterval
        
    }
    catch {
        Write-Host "Error: $_" -ForegroundColor Red
        Start-Sleep -Seconds $RefreshInterval
    }
} 