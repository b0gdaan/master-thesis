param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPdf
)

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($InputPath, $false, $true)
    $document.ExportAsFixedFormat($OutputPdf, 17)
}
finally {
    if ($document) { $document.Close($false) }
    if ($word) { $word.Quit() }
}
