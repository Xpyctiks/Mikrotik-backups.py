#!/usr/bin/env python3

import os
import sys
import json
import logging
import logging.handlers
import requests
from datetime import datetime
import paramiko
import time

CONFIG_FILE = os.path.expanduser(os.path.splitext(os.path.basename(__file__))[0]+".json")
SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]
PID_FILE = os.path.splitext(os.path.basename(__file__))[0]+".pid"
BCKP_LIST = []
TELEGRAM_TOKEN = TELEGRAM_CHATID = LOG_FILE = BCKP_FOLDER = BCKP_ENCR_PASS = ""

def generate_default_config():
    config =  {
        "telegramToken": "",
        "telegramChat": "",
        "logFile": f"{SCRIPT_NAME}.log",
        "backupFolder": "/media/Backup",
        "backupEncryptPass": "123Passw0rd123",
        "BackupList": [
            {
                "Name": "Name1",
                "Host": "router1.lan",
                "User": "admin",
                "Password": "",
                "Port": "22",
                "keyFile": "",
                "cloudBackup": False,
                "UserManager": False,
                "cleanUMsessions": False
            },
            {
                "Name": "Name2",
                "Host": "router2.lan",
                "User": "admin",
                "Password": "",
                "Port": "22",
                "keyFile": "",
                "cloudBackup": False,
                "UserManager": False,
                "cleanUMsessions": False
            }
        ]
    }
    with open(CONFIG_FILE, 'w',encoding='utf8') as file:
        json.dump(config, file, indent=4)
    os.chmod(CONFIG_FILE, 0o600)
    print(f"First launch. New config file {CONFIG_FILE} generated and needs to be configured.")
    quit()

def send_to_telegram(subject,message):
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        "chat_id": f"{TELEGRAM_CHATID}",
        "text": f"[{os.uname().nodename}] {SCRIPT_NAME}:\n{subject}\n{message}",
    }
    if not any(important in [None, "", "None"] for important in [f"{TELEGRAM_CHATID}", f"{TELEGRAM_TOKEN}"]):
        response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",headers=headers,json=data)
        if response.status_code != 200:
            err = response.json()
            logging.error(f"Error while sending message to Telegram: {err}")

def load_config():
    #main initialization phase starts here
    error = 0
    global TELEGRAM_TOKEN, TELEGRAM_CHATID, LOG_FILE, BCKP_LIST, BCKP_FOLDER, BCKP_ENCR_PASS
    #Check if config file exists. If not - generate the new one.
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r',encoding='utf8') as file:
            config = json.load(file)
        #Check if all parameters are set. If not - shows the error message
        for id,key in enumerate(config.keys()):
            if not (key in ["telegramToken", "telegramChat", "logFile", "backupFolder", "BackupList", "backupEncryptPass"]):
                print(f"Important key {key} is absent in config file! Can't proceed")
                interrupt_job()
            elif config.get(key) in [None, "", "None"]:
                print(f"Important parameter {key} is not defined! Can't proceed")
                error+=1
        if error != 0:
            print(f"Some variables are not set in config file. Please fix it then run the program again.")
            interrupt_job()
        TELEGRAM_TOKEN = config.get('telegramToken').strip()
        TELEGRAM_CHATID = config.get('telegramChat').strip()
        LOG_FILE = config.get('logFile').strip()
        BCKP_FOLDER = config.get('backupFolder').strip()
        BCKP_ENCR_PASS = config.get('backupEncryptPass').strip()
        BCKP_LIST = config.get('BackupList', [])
        logging.basicConfig(filename=LOG_FILE,level=logging.INFO,format='%(asctime)s - Mikrotik-backups - %(levelname)s - %(message)s',datefmt='%d-%m-%Y %H:%M:%S')
    else:
        generate_default_config()

def check_pid():
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            old_pid = int(f.read().strip())        
        if os.path.exists(f"/proc/{old_pid}"):
            print(f"Another copy is running. Can't proceed.")
            logging.error("Previous copy is running. Can't proceed.")
            send_to_telegram("🚫Error!","Previous copy is running. Can't proceed.")
            interrupt_job()
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
        return True

def del_pid():    
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

def finish_job():
    time=datetime.now().strftime('%H:%M:%S %d.%m.%Y')
    text = f"----------------------------------------{time} Finished all backup job-------------------------------------"
    print(text)
    logging.info(text)
    send_to_telegram("✅All jobs done.","")
    del_pid()
    sys.exit(0)

def interrupt_job():
    time=datetime.now().strftime('%H:%M:%S %d.%m.%Y')
    text = f"----------------------------------------{time} Interruption of all backup job-------------------------------------"
    print(text)
    logging.info(text)
    send_to_telegram("❌All jobs have been interrupted!","")
    del_pid()
    sys.exit(1)

def step1_mkdir():
    folderName = datetime.now().strftime('%d.%m.%Y')
    fullBackupPath = os.path.join(BCKP_FOLDER,folderName)
    if not os.path.exists(fullBackupPath):
        try:
            os.mkdir(fullBackupPath,mode=0o770)
            print(f"Backup directory created {fullBackupPath}")
            logging.info(f"Backup directory created {fullBackupPath}")
            return True
        except Exception as msg:
            text =f"Error creating directory {fullBackupPath}. Error: {msg}"
            logging.error(text)
            send_to_telegram("🚒Error:",text)
            print(text)
            return False
    return True

def step2_main_job(name,host,port,user,auth_item,usermanager,cloudbackup,cleanUMsesions,type):
    client = paramiko.SSHClient()
    currDate = datetime.now().strftime('%d.%m.%Y')
    #make folder for backups. if any error - skip this host
    result = step1_mkdir()
    if not result:
        return
    text = f"General task: create backup files"
    if cloudbackup:
        text += f" + create backup in Mikrotik cloud"
    if usermanager:
        text += f" + create UserManager backup"
    if cleanUMsesions:
        text += f" + clear UM sessions"
    logging.info(text)
    print(text)
    try:
        #Heading into the device and creating backup files
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if type == "Password":
            text = f"Auth type: password"
            logging.info(text)
            print(text)
            client.connect(hostname=host, username=user, port=port, password=auth_item, look_for_keys=False)
        elif type == "keyFile":
            text = f"Auth type: key file"
            logging.info(text)
            print(text)
            private_key = paramiko.RSAKey(filename=auth_item)
            client.connect(hostname=host, username=user, port=port, pkey=private_key)
        text = f"Creating backup files..."
        logging.info(text)
        print(text)
        commands = f"/export file={name}-{currDate} show-sensitive; delay 1; "
        commands += f"/log/warning \"{SCRIPT_NAME}: Created plain text backup\"; delay 1; "
        commands += f"/system/backup save name={name}-{currDate} password={BCKP_ENCR_PASS}; delay 1; "
        commands += f"/log/warning \"{SCRIPT_NAME}: Created encrypted full backup\"; delay 1;"
        if cloudbackup:
            text = f"Creating backup in Mikrotik cloud..."
            logging.info(text)
            print(text)
            commands += f"/system/backup/cloud/upload-file replace=[find] password={BCKP_ENCR_PASS} action=create-and-upload; delay 3; "
            commands += f"/log/warning \"{SCRIPT_NAME}: Cloud backup created\"; delay 1; "
        client.exec_command(commands)
        time.sleep(5)
        #Now downloading newly created files from the device
        folderName = datetime.now().strftime('%d.%m.%Y')
        fullBackupPath = os.path.join(BCKP_FOLDER,folderName)
        sftp = client.open_sftp()
        text = f"Downloading {name}-{currDate}.rsc file..."
        print(text)
        logging.info(text)
        file = os.path.join(fullBackupPath,f"{name}-{currDate}.rsc")
        sftp.get(f"/{name}-{currDate}.rsc", file)
        text = f"Downloading {name}-{currDate}.backup file..."
        print(text)
        logging.info(text)
        file = os.path.join(fullBackupPath,f"{name}-{currDate}.backup")
        sftp.get(f"/{name}-{currDate}.backup", file)
        text = f"Removing {name}-{currDate}.rsc and {name}-{currDate}.backup files..."
        print(text)
        logging.info(text)
        commands = f"/file/remove {name}-{currDate}.rsc; delay 1; "
        commands += f"/log/warning \"{SCRIPT_NAME}: {name}-{currDate}.rsc deleted\"; delay 1; "
        commands += f"/file/remove {name}-{currDate}.backup; delay 1; "
        commands += f"/log/warning \"{SCRIPT_NAME}: {name}-{currDate}.backup deleted\"; delay 1; "
        client.exec_command(commands)
        time.sleep(5)
        #check is UserManager downloading is enabled.
        if usermanager:
            text = f"Processing UserManager backups..."
            print(text)
            logging.info(text)
            commands = f"/user-manager/database/save name=userman.db overwrite=yes; delay 1;"
            client.exec_command(commands)
            sftp = client.open_sftp()
            text = f"Downloading userman.db file..."
            print(text)
            logging.info(text)
            file = os.path.join(fullBackupPath,"userman.db")
            sftp.get(f"/userman.db", file)
            text = f"Downloading um5 raw files..."
            print(text)
            logging.info(text)
            file = os.path.join(fullBackupPath,"um5.sqlite")
            sftp.get(f"user-manager5/um5.sqlite", file)
            file = os.path.join(fullBackupPath,"um5.sqlite-wal")
            sftp.get(f"user-manager5/um5.sqlite-wal", file)
        if cleanUMsesions:
            text = f"Clearing UM sessions..."
            print(text)
            logging.info(text)
            commands = f"/user-manager/session/remove [find]"
            client.exec_command(commands)
        sftp.close()
        return
    except Exception as msg:
        text = f"Error while SSH connection to Name={name}, Host={host}, Port={port}, User={user}, Password={auth_item}, UserManager={usermanager}. Error: {msg}"
        if str(msg) == "Private key file is encrypted":
            text += " P.S.Probably wrong keyfile or wrong username is set.Check auth settings in both sides.Or your keyfile is really need the key to decrypt before use."
        if str(msg) == "private key file is encrypted":
            text += " P.S.Your keyfile seems really needs the key to decrypt before usage."
        logging.error(text)
        send_to_telegram("🚒Error:",text)
        print(text)
        return
    finally:
        client.close()

def main():
    load_config()
    time=datetime.now().strftime('%H:%M:%S %d.%m.%Y')
    text = f"----------------------------------------{time} Starting backup jobs----------------------------------------"
    print(text)
    logging.info(text)
    send_to_telegram("☕Backup job started","")
    check_pid()
    #check is the root backup folder accessable.
    if not os.path.exists(BCKP_FOLDER):
        text = f"Root folder for backups {BCKP_FOLDER} is not accessable! Interrupting!"
        print(text)
        logging.info(text)
        send_to_telegram("🚒Error:",text)
        interrupt_job()
    #start of main function - fetching list and makeing backups
    for device in BCKP_LIST:
        #check all necessary fileds are present and have their values
        if any(device.get(field) in [None, "", "None"] for field in ["Name", "Host", "User", "Port"]) or (not device.get('Password') and not device.get('keyFile')):
            text = f"Skipped wrong block: Name={device.get('Name')}, Host={device.get('Host')}, User={device.get('User')}, UserManager={device.get('UserManager')}, CloudBackup={device.get('cloudBackup')}, cleanUMsessions={device.get('cleanUMsessions')} and neither Password={device.get('Password')} nor keyFile={device.get('keyFile')} is defined. "
            print(text)
            logging.info(text)
            continue
        #check if keyFile is set - perfer use if keyfile auth, even if password is defined
        if not device.get('keyFile') in [None, "", "None"]:
            text = f">>>Processing Name={device.get('Name')}, Host={device.get('Host')}, Port={device.get('Port')}, User={device.get('User')}, KeyFile={device.get('keyFile')}, UserManager={device.get('UserManager')}, CloudBackup={device.get('cloudBackup')}, cleanUMsessions={device.get('cleanUMsessions')}"
            if not device.get('Password') in [None, "", "None"]:
                text = f">>>Processing Name={device.get('Name')}, Host={device.get('Host')}, Port={device.get('Port')}, User={device.get('User')}, KeyFile={device.get('keyFile')} (Password is also set,but keyFile is preferable in this case), UserManager={device.get('UserManager')}, CloudBackup={device.get('cloudBackup')}, cleanUMsessions={device.get('cleanUMsessions')}"
            print(text)
            logging.info(text)
            step2_main_job(device.get('Name'), device.get('Host'), device.get('Port'), device.get('User'), device.get('keyFile'), device.get('UserManager'),device.get('cloudBackup'), device.get('cleanUMsessions'),"keyFile")
        #if keyFile is not set - check for password and proceed with password auth.
        elif not device.get('Password') in [None, "", "None"]:
            text = f">>>Processing Name={device.get('Name')}, Host={device.get('Host')}, Port={device.get('Port')}, User={device.get('User')}, Password={device.get('Password')[:4]}**********, UserManager={device.get('UserManager')}, CloudBackup={device.get('cloudBackup')}, cleanUMsessions={device.get('cleanUMsessions')}"
            print(text)
            logging.info(text)
            step2_main_job(device.get('Name'), device.get('Host'), device.get('Port'), device.get('User'), device.get('Password'), device.get('UserManager'), device.get('cloudBackup'), device.get('cleanUMsessions'),"Password")
    finish_job()

if __name__ == "__main__":
    main()