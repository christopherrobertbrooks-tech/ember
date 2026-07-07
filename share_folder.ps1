# This script creates a hidden dedicated sync account and shares the folder with it.
# It requires Administrator privileges.

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Administrator privileges required. Prompting for elevation..."
    Start-Process PowerShell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$SyncUser = "embersync"
$SyncPass = "EmberSync2026!"
$ShareName = "Project_Ember"
$FolderPath = "F:\Project_Ember"

# 1. Create the local user account
Write-Host "Creating dedicated sync account '$SyncUser'..."
$Password = ConvertTo-SecureString $SyncPass -AsPlainText -Force
try {
    New-LocalUser -Name $SyncUser -Password $Password -FullName "Ember Sync Account" -Description "Used for syncing Project Ember over network" -PasswordNeverExpires -ErrorAction Stop
} catch {
    Write-Host "User '$SyncUser' already exists or could not be created."
}

# 2. Hide the user from the Windows login screen
Write-Host "Hiding '$SyncUser' from login screen..."
$RegPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\SpecialAccounts\UserList"
if (-not (Test-Path $RegPath)) {
    New-Item -Path $RegPath -Force | Out-Null
}
New-ItemProperty -Path $RegPath -Name $SyncUser -Value 0 -PropertyType DWord -Force | Out-Null

# 3. Create the SMB Share and grant full access to the sync user
Write-Host "Configuring SMB Share '$ShareName'..."
Remove-SmbShare -Name $ShareName -Force -ErrorAction SilentlyContinue
New-SmbShare -Name $ShareName -Path $FolderPath -FullAccess $SyncUser -ErrorAction SilentlyContinue

# 4. Set NTFS permissions for the sync user
Write-Host "Setting Folder Permissions..."
$Acl = Get-Acl $FolderPath
$AccessRule = New-Object System.Security.AccessControl.FileSystemAccessRule($SyncUser, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
$Acl.SetAccessRule($AccessRule)
Set-Acl $FolderPath $Acl

Write-Host ""
Write-Host "==================================================="
Write-Host "Setup Complete!"
Write-Host "Sync Account: $SyncUser"
Write-Host "Sync Pass: $SyncPass"
Write-Host "Folder $FolderPath is now securely shared over the network."
Write-Host "==================================================="
Write-Host ""
pause
