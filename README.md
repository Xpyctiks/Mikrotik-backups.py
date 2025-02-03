# Mikrotik-Backups.py
This is a new version of my old bash script written in python, which makes backups of Mikrotik devices and downloads them to any local folder.  
Allows creation of:
- plaintext + full encrypted backups.  
- cloud backup in Mikortik cloud.  
- backup of UserManager database.  
- Flush of UM sessions after backup.  
Also the script sends all important alerts and information to Telegram bot + full logging into local file.  

Requires additionally two python packages:  
- paramiko  
- requests 

Installation:  
- Just download the script to any folder. For example, on Debian-based OS it could be /usr/local/bin/ folder.  
- Launch the script from CLI for the first time. It will generate a default configuration file.  
- Modify the config. file:  
    "telegramToken" and "telegramChat" - fill in to get Telegram notifications work  
    "logFile" - Path and name of the log file. Default right in the script's folder with script's name.  
    "backupFolder" - Root backup folder, inside of which all other folder will be made. Every folder with backups has a name as current date.
    "backupEncryptPass" - the password you want to set for cloud backup and file backups for Mikrotik.  
    "BackupList" - General branch where all devices for backup are described:  
      "Name" - Name of the device as you want to see it.Used to easy identificate your device.You can set anything you want.  
      "Host" - FQDN or IP of the device.
      "Password", "Port","keyFile" - general options. If both Password and KeyFile are set - keyFile auth will be choosen as the higher priority.  
                                     You can set only Password variable if need password auth, or keyfile - if key file auth.  
      "cloudBackup" - if True - also create a backup in Mikrotik cloud.  
      "UserManager" - if True - also create a backup of UserManager database files.  
      "cleanUMsessions" - if True - clear all current sessions in UM.  
