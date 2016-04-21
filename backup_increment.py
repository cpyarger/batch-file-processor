import shutil
import os
import time


def do_backup(input_file):
    counter = 1
    proposed_backup_folder_path = os.path.join(os.path.dirname(os.path.abspath(input_file)), "backups")
    if os.path.isdir(proposed_backup_folder_path) or not os.path.exists(proposed_backup_folder_path):
        backup_folder_path = proposed_backup_folder_path
    else:
        while os.path.isfile(proposed_backup_folder_path + str(counter)):
            counter += 1
        backup_folder_path = proposed_backup_folder_path + str(counter)
    if not os.path.exists(backup_folder_path):
        os.mkdir(backup_folder_path)
    backup_path = os.path.join(backup_folder_path,
                               os.path.basename(input_file) + '.bak' + "-" + str(time.ctime()).replace(":", "-"))
    print(backup_path)
    shutil.copy(input_file, backup_path)
    return backup_path
