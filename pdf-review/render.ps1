Add-Type -AssemblyName System.Runtime.WindowsRuntime
$ErrorActionPreference = 'Stop'
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Foundation.IAsyncAction, Windows.Foundation, ContentType=WindowsRuntime]
$taskMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Await-Result($operation, $resultType) {
    $task = $taskMethod.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait()
    return $task.Result
}
Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.pdf' | ForEach-Object {
    $source = $_
    $file = Await-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($source.FullName)) ([Windows.Storage.StorageFile])
    $pdf = Await-Result ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
    for ($index = 0; $index -lt $pdf.PageCount; $index++) {
        $page = $pdf.GetPage($index)
        $memory = [Windows.Storage.Streams.InMemoryRandomAccessStream]::new()
        $actionMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
            $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1
        } | Select-Object -First 1
        $task = $actionMethod.Invoke($null, @($page.RenderToStreamAsync($memory)))
        $task.Wait()
        $stream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($memory)
        $outputPath = Join-Path $PSScriptRoot ($source.BaseName + '-' + ($index + 1) + '.png')
        $output = [System.IO.File]::Create($outputPath)
        $stream.CopyTo($output)
        $output.Dispose()
        $stream.Dispose()
        $page.Dispose()
        Write-Output $outputPath
    }
}
