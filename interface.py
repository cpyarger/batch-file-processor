#!/usr/bin/env python3
import fuzzywuzzy.process
import ftplib
from tkinter import *
from tkinter.ttk import *
import platform
from tkinter.filedialog import askdirectory
from tkinter.messagebox import showerror, askyesno, showinfo, askokcancel
import tkinter
from validate_email import validate_email
import rclick_menu
import hashlib
import scrollbuttons
import dataset
import dialog
import dispatch
import os
import create_database
import time
import datetime
import batch_log_sender
import print_run_log
import argparse
from io import StringIO
import doingstuffoverlay
import folders_database_migrator
import resend_interface
import database_import
import backup_increment
import appdirs
import clear_old_files
import smtplib
import multiprocessing
from operator import itemgetter
import zipfile
import copy
import pyodbc

if __name__ == '__main__':
    multiprocessing.freeze_support()
    appname = "Batch File Sender"
    version = "(Git Branch: Master)"
    database_version = "18"
    print(appname + " Version " + version)
    running_platform = platform.system()
    print("Running on " + running_platform)
    root = Tk()  # create root window
    root.title(appname + " " + version)
    folder = NONE
    options_frame = Frame(root)  # initialize left frame
    feedback_text = Label(root, text="Loading...")
    feedback_text.pack(side=BOTTOM)
    root.update()

    config_folder = appdirs.user_data_dir(appname)
    database_path = os.path.join(config_folder, 'folders.db')

    try:
        os.makedirs(config_folder)
    except FileExistsError:
        pass

    if not os.path.isfile(database_path):  # if the database file is missing
        try:
            print("creating initial database file...")
            creating_database_popup = Tk()
            Label(creating_database_popup, text="Creating initial database file...").pack()
            creating_database_popup.update()
            create_database.do(database_version, database_path, config_folder, running_platform)  # make a new one
            print("done")
            creating_database_popup.destroy()
        except Exception as error:  # if that doesn't work for some reason, log and quit
            try:
                print(str(error))
                critical_log = open("critical_error.log", 'a')
                critical_log.write("program version is " + version)
                critical_log.write(str(datetime.datetime.now()) + str(error) + "\r\n")
                critical_log.close()
                raise SystemExit
            except Exception as big_error:  # if logging doesn't work, at least complain
                print("error writing critical error log for error: " + str(error) + "\n" +
                      "operation failed with error: " + str(big_error))
                raise SystemExit


    def connect_to_databases():
        global database_connection
        global session_database
        try:  # try to connect to database
            database_connection = dataset.connect('sqlite:///' + database_path)  # connect to database
            session_database = dataset.connect("sqlite:///")
        except Exception as connect_error:  # if that doesn't work for some reason, log and quit
            try:
                print(str(connect_error))
                connect_critical_log = open("critical_error.log", 'a')
                connect_critical_log.write("program version is " + version)
                connect_critical_log.write(str(datetime.datetime.now()) + str(connect_error) + "\r\n")
                connect_critical_log.close()
                raise SystemExit
            except Exception as connect_big_error:  # if logging doesn't work, at least complain
                print("error writing critical error log for error: " + str(connect_error)
                      + "\n" + "operation failed with error: " +
                      str(connect_big_error))
                raise SystemExit


    connect_to_databases()

    # open table required for database check in database
    db_version = database_connection['version']
    db_version_dict = db_version.find_one(id=1)
    if int(db_version_dict['version']) < int(database_version):
        print("updating database file")
        updating_database_popup = Tk()
        Label(updating_database_popup, text="Updating database file...").pack()
        updating_database_popup.update()
        backup_increment.do_backup(database_path)
        folders_database_migrator.upgrade_database(database_connection, config_folder, running_platform)
        updating_database_popup.destroy()
        print("done")
    if int(db_version_dict['version']) > int(database_version):
        Tk().withdraw()
        showerror("Error", "Program version too old for database version,\r\n please install a more recent release.")
        raise SystemExit

    connect_to_databases()
    db_version = database_connection['version']
    db_version_dict = db_version.find_one(id=1)
    if db_version_dict['os'] != running_platform:
        Tk().withdraw()
        showerror("Error", "The operating system detected is: " + '"' + running_platform + '",' +
                  " this does not match the configuration creator, which is stored as: " + '"' +
                  db_version_dict['os'] + '".' + "\r\n"
                                                 "Folder paths are not portable between operating systems. Exiting")
        raise SystemExit


    # open required tables in database


    def open_tables():
        global folders_table
        global emails_table
        global emails_table_batch
        global sent_emails_removal_queue
        global oversight_and_defaults
        global processed_files
        global settings
        global database_connection
        folders_table = database_connection['folders']
        emails_table = database_connection['emails_to_send']
        emails_table_batch = database_connection['working_batch_emails_to_send']
        sent_emails_removal_queue = database_connection['sent_emails_removal_queue']
        oversight_and_defaults = database_connection['administrative']
        processed_files = database_connection['processed_files']
        settings = database_connection['settings']


    open_tables()

    launch_options = argparse.ArgumentParser()
    logs_directory = oversight_and_defaults.find_one(id=1)
    errors_directory = oversight_and_defaults.find_one(id=1)
    edi_converter_scratch_folder = oversight_and_defaults.find_one(id=1)
    folder_filter = ""


    def check_logs_directory():
        try:
            # check to see if log directory is writable
            test_log_file = open(os.path.join(logs_directory['logs_directory'], 'test_log_file'), 'w')
            test_log_file.close()
            os.remove(os.path.join(logs_directory['logs_directory'], 'test_log_file'))
        except IOError as log_directory_error:
            print(str(log_directory_error))
            return False


    def add_folder_entry(proposed_folder):  # add folder to database, copying configuration from template
        defaults = oversight_and_defaults.find_one(id=1)
        folder_alias_constructor = os.path.basename(proposed_folder)

        def folder_alias_checker(check):
            # check database to see if the folder alias exists, and return false if it does
            if not folders_table.count() == 0:
                add_folder_entry_proposed_folder = folders_table.find_one(alias=check)
                if add_folder_entry_proposed_folder != None:
                    return False

        if folder_alias_checker(folder_alias_constructor) ==False:
            # auto generate a number to add to automatic aliases
            folder_alias_end_suffix = 0
            folder_alias_deduplicate_constructor = folder_alias_constructor
            while folder_alias_checker(folder_alias_deduplicate_constructor) ==False:
                folder_alias_end_suffix += folder_alias_end_suffix + 1
                print(str(folder_alias_end_suffix))
                folder_alias_deduplicate_constructor = folder_alias_constructor + " " + str(folder_alias_end_suffix)
            folder_alias_constructor = folder_alias_deduplicate_constructor

        print("adding folder: " + proposed_folder + " with settings from template")
        # create folder entry using the selected folder, the generated alias, and values copied from template
        folders_table.insert(dict(folder_name=proposed_folder,
                                  copy_to_directory=defaults['copy_to_directory'],
                                  folder_is_active=defaults['folder_is_active'],
                                  alias=folder_alias_constructor,
                                  process_backend_copy=defaults['process_backend_copy'],
                                  process_backend_ftp=defaults['process_backend_ftp'],
                                  process_backend_email=defaults['process_backend_email'],
                                  ftp_server=defaults['ftp_server'],
                                  ftp_folder=defaults['ftp_folder'],
                                  ftp_username=defaults['ftp_username'],
                                  ftp_password=defaults['ftp_password'],
                                  email_to=defaults['email_to'],
                                  process_edi=defaults['process_edi'],
                                  convert_to_format=defaults['convert_to_format'],
                                  calculate_upc_check_digit=defaults['calculate_upc_check_digit'],
                                  include_a_records=defaults['include_a_records'],
                                  include_c_records=defaults['include_c_records'],
                                  include_headers=defaults['include_headers'],
                                  filter_ampersand=defaults['filter_ampersand'],
                                  tweak_edi=defaults['tweak_edi'],
                                  split_edi=defaults['split_edi'],
                                  pad_a_records=defaults['pad_a_records'],
                                  a_record_padding=defaults['a_record_padding'],
                                  ftp_port=defaults['ftp_port'],
                                  email_subject_line=defaults['email_subject_line'],
                                  force_edi_validation=defaults['force_edi_validation'],
                                  append_a_records=defaults['append_a_records'],
                                  a_record_append_text=defaults['a_record_append_text'],
                                  force_txt_file_ext=defaults['force_txt_file_ext'],
                                  invoice_date_offset=defaults['invoice_date_offset']
                                  ))
        print("done")


    def check_folder_exists(check_folder):
        folder_list = folders_table.all()
        for possible_folder in folder_list:
            possible_folder_string = possible_folder['folder_name']
            if os.path.normpath(possible_folder_string) == os.path.normpath(check_folder):
                return {"truefalse": True, "matched_folder": possible_folder}
        return {"truefalse": False, "matched_folder": None}


    def select_folder():
        global folder
        global column_entry_value
        prior_folder = oversight_and_defaults.find_one(id=1)
        if os.path.exists(prior_folder['single_add_folder_prior']):
            initial_directory = prior_folder['single_add_folder_prior']
        else:
            initial_directory = os.path.expanduser('~')
        folder = askdirectory(initialdir=initial_directory)
        if os.path.exists(folder):
            update_last_folder = dict(id=1, single_add_folder_prior=folder)
            oversight_and_defaults.update(update_last_folder, ['id'])
            proposed_folder = check_folder_exists(folder)

            if proposed_folder['truefalse'] ==False:
                doingstuffoverlay.make_overlay(root, "Adding Folder...")
                column_entry_value = folder
                add_folder_entry(folder)
                if askyesno(message="Do you want to mark files in folder as processed?"):
                    folder_dict = folders_table.find_one(folder_name=folder)
                    mark_active_as_processed(root, folder_dict['id'])
                doingstuffoverlay.destroy_overlay()
                refresh_users_list()  # recreate list
            else:
                #  offer to edit the folder if it is already known
                proposed_folder_dict = proposed_folder['matched_folder']
                if askokcancel("Query:", "Folder already known, would you like to edit?"):
                    EditDialog(root, proposed_folder_dict)


    def batch_add_folders():
        added = 0
        skipped = 0
        prior_folder = oversight_and_defaults.find_one(id=1)
        if os.path.exists(prior_folder['batch_add_folder_prior']):
            initial_directory = prior_folder['batch_add_folder_prior']
        else:
            initial_directory = os.path.expanduser('~')
        containing_folder = askdirectory(initialdir=initial_directory)
        starting_directory = os.getcwd()
        if os.path.exists(containing_folder):
            update_last_folder = dict(id=1, batch_add_folder_prior=containing_folder)
            oversight_and_defaults.update(update_last_folder, ['id'])
            os.chdir(str(containing_folder))
            folders_list = [f for f in os.listdir('.') if os.path.isdir(f)]  # build list of folders in target directory
            print("adding " + str(len(folders_list)) + " folders")
            if askokcancel(message="This will add " + str(len(folders_list)) + " directories, are you sure?"):
                doingstuffoverlay.make_overlay(parent=root, overlay_text="adding folders...")
                folder_count = 0
                # loop over all folders in target directory, skipping them if they are already known
                for batch_folder_add_proposed_folder in folders_list:
                    folder_count += 1
                    doingstuffoverlay.update_overlay(parent=root, overlay_text="adding folders... " + str(folder_count) +
                                                                               " of " + str(len(folders_list)))
                    batch_folder_add_proposed_folder = os.path.join(containing_folder, batch_folder_add_proposed_folder)
                    proposed_folder = check_folder_exists(batch_folder_add_proposed_folder)
                    if proposed_folder['truefalse'] ==False:
                        add_folder_entry(batch_folder_add_proposed_folder)
                        added += 1
                    else:
                        print("skipping existing folder: " + batch_folder_add_proposed_folder)
                        skipped += 1
                print("done adding folders")
                doingstuffoverlay.destroy_overlay()
                refresh_users_list()
                showinfo(parent=root, message=str(added) + " folders added, " + str(skipped) + " folders skipped.")
        os.chdir(starting_directory)


    def edit_folder_selector(folder_to_be_edited):
        # feed the EditDialog class the the dict for the selected folder from the folders list buttons
        # note: would prefer to be able to do this inline,
        # but variables appear to need to be pushed out of instanced objects
        edit_folder = folders_table.find_one(id=[folder_to_be_edited])
        EditDialog(root, edit_folder)


    def send_single(folder_id):
        doingstuffoverlay.make_overlay(root, "Working...")
        try:
            single_table = session_database['single_table']
            single_table.drop()
        finally:
            single_table = session_database['single_table']
            table_dict = folders_table.find_one(id=folder_id)
            table_dict['old_id'] = table_dict.pop('id')
            single_table.insert(table_dict)
            doingstuffoverlay.destroy_overlay()
            graphical_process_directories(single_table)
            single_table.drop()


    def disable_folder(folder_id):
        folder_dict = folders_table.find_one(id=folder_id)
        folder_dict['folder_is_active'] = "False"
        folders_table.update(folder_dict, ['id'])
        refresh_users_list()


    def set_folders_filter(filter_field_contents):
        global folder_filter
        folder_filter = filter_field_contents
        refresh_users_list()


    def make_users_list():
        global search_field

        def search_field_callback(_=None):
            if folder_filter != search_field.get():
                try:
                    root.unbind(0, "<Escape>")
                except TclError:
                    pass
                filter_field = search_field.get()
                set_folders_filter(filter_field)
                if not filter_field == "":
                    root.bind("<Escape>", clear_search_field)

        def clear_search_field(_=None):
            search_field.delete(0, "end")
            search_field_callback()

        global users_list_frame
        global active_users_list_frame
        global inactive_users_list_frame
        users_list_frame = Frame(root)
        scrollable_lists_frame = Frame(users_list_frame)
        search_frame = Frame(users_list_frame)
        active_users_list_container = Frame(scrollable_lists_frame)
        inactive_users_list_container = Frame(scrollable_lists_frame)
        active_users_list_frame = scrollbuttons.VerticalScrolledFrame(active_users_list_container)
        inactive_users_list_frame = scrollbuttons.VerticalScrolledFrame(inactive_users_list_container)
        active_users_list_label = Label(active_users_list_container, text="Active Folders")  # active users title
        inactive_users_list_label = Label(inactive_users_list_container, text="Inactive Folders")  # inactive users title
        search_field = Entry(search_frame)
        search_field.insert(0, folder_filter)
        right_click_search_field = rclick_menu.RightClickMenu(search_field)
        search_field.bind("<3>", right_click_search_field)
        search_field.bind("<Return>", search_field_callback)
        search_button = Button(master=search_frame, text="Update Filter", command=search_field_callback)
        active_folder_dict_list = folders_table.find(folder_is_active="True")
        inactive_folder_dict_list = folders_table.find(folder_is_active="False")
        folders_dict_list = folders_table.find(order_by="alias")
        if folders_table.count() == 0:
            for child in search_frame.winfo_children():
                child.configure(state=DISABLED)
        if folder_filter != "":
            folder_alias_list = []
            fuzzy_filtered_alias = []
            for folder_alias in folders_dict_list:
                folder_alias_list.append(folder_alias['alias'])
            fuzzy_filter = list(fuzzywuzzy.process.extractWithoutOrder(folder_filter, folder_alias_list, score_cutoff=80))
            fuzzy_filter.sort(key=itemgetter(1), reverse=True)
            for fuzzy_alias, score in fuzzy_filter:
                fuzzy_filtered_alias.append(fuzzy_alias)
            filtered_folder_dict_list = []
            filtered_active_folder_dict_list = []
            filtered_inactive_folder_dict_list = []
            pre_filtered_folder_dict_list = []
            pre_filtered_active_folder_dict_list = []
            pre_filtered_inactive_folder_dict_list = []

            def copyf(dictlist, key, valuelist):
                return [dictio for dictio in dictlist if dictio[key] in valuelist]

            for entry in fuzzy_filtered_alias:
                pre_filtered_folder_dict_list.append(copyf(
                    folders_table.find(order_by="alias"), 'alias', entry))
                pre_filtered_active_folder_dict_list.append(copyf(
                    folders_table.find(folder_is_active="True"), 'alias', entry))
                pre_filtered_inactive_folder_dict_list.append(copyf(
                    folders_table.find(folder_is_active="False"), 'alias', entry))
                filtered_folder_dict_list = [i[0] for i in pre_filtered_folder_dict_list]
                filtered_active_folder_dict_list = [i[0] for i in pre_filtered_folder_dict_list]
                filtered_inactive_folder_dict_list = [i[0] for i in pre_filtered_folder_dict_list]

        else:
            filtered_folder_dict_list = [d for d in folders_dict_list]
            filtered_active_folder_dict_list = [d for d in active_folder_dict_list]
            filtered_inactive_folder_dict_list = [d for d in inactive_folder_dict_list]

        # make labels for empty lists
        if len(list(filtered_folder_dict_list)) == 0:
            no_active_label = Label(active_users_list_frame, text="No Active Folders")
            no_active_label.pack(fill=BOTH, expand=1, padx=10)
            no_inactive_label = Label(inactive_users_list_frame, text="No Inactive Folders")
            no_inactive_label.pack(fill=BOTH, expand=1, padx=10)
        else:
            if len(list(filtered_active_folder_dict_list)) == 0:
                no_active_label = Label(active_users_list_frame, text="No Active Folders")
                no_active_label.pack(fill=BOTH, expand=1, padx=10)
            if len(list(filtered_inactive_folder_dict_list)) == 0:
                no_inactive_label = Label(inactive_users_list_frame, text="No Inactive Folders")
                no_inactive_label.pack(fill=BOTH, expand=1, padx=10)

        # this finds the length of the longest folder aliases for both active and inactive lists
        active_folder_edit_length = 0
        inactive_folder_edit_length = 0
        active_folder_alias_list = []
        inactive_folder_alias_list = []
        if not folders_table.count(folder_is_active="True") == 0:
            for entry in filtered_active_folder_dict_list:
                alias = entry['alias']
                if alias ==None:
                    pass
                else:
                    active_folder_alias_list.append(alias)
            if not len(list(active_folder_alias_list)) == 0:
                active_folder_edit_length = len(max(list(active_folder_alias_list), key=len))

        if not folders_table.count(folder_is_active="False") == 0:
            for entry in filtered_inactive_folder_dict_list:
                alias = entry['alias']
                if alias ==None:
                    pass
                else:
                    inactive_folder_alias_list.append(alias)
            if not len(list(inactive_folder_alias_list)) == 0:
                inactive_folder_edit_length = len(max(list(inactive_folder_alias_list), key=len))

        # iterate over list of known folders, sorting into lists of active and inactive
        for folders_name in filtered_folder_dict_list:
            if str(folders_name['folder_is_active']) != "False":
                active_folder_button_frame = Frame(active_users_list_frame.interior)
                Button(active_folder_button_frame, text="Send",
                       command=lambda name=folders_name['id']: send_single(name)).grid(column=2, row=0, padx=(0, 10))
                Button(active_folder_button_frame, text="<-",
                       command=lambda name=folders_name['id']: disable_folder(name)).grid(column=0, row=0)
                Button(active_folder_button_frame, text="Edit: " + folders_name['alias'] + "...",
                       command=lambda name=folders_name['id']: edit_folder_selector(name),
                       width=active_folder_edit_length + 6).grid(column=1, row=0, sticky=E + W)
                active_folder_button_frame.pack(anchor='e', pady=1)
            else:
                inactive_folder_button_frame = Frame(inactive_users_list_frame.interior)
                Button(inactive_folder_button_frame, text="Delete",
                       command=lambda name=folders_name['id'], alias=folders_name['alias']:
                       delete_folder_entry_wrapper(name, alias)).grid(column=1, row=0, sticky=E, padx=(0, 10))
                Button(inactive_folder_button_frame, text="Edit: " + folders_name['alias'] + "...",
                       command=lambda name=folders_name['id']: edit_folder_selector(name),
                       width=inactive_folder_edit_length + 6).grid(column=0, row=0, sticky=E + W, padx=(10, 0))
                inactive_folder_button_frame.pack(anchor='e', pady=1)
        # pack widgets in correct order
        if len(list(filtered_folder_dict_list)) != folders_table.count():
            folders_count_label = Label(search_frame, text=(
                    str(len(list(filtered_folder_dict_list))) + " of " + str(folders_table.count()) + " shown"))
            folders_count_label.pack(side=RIGHT)
        active_users_list_label.pack(pady=5)
        Separator(active_users_list_container, orient=HORIZONTAL).pack(fill=X)
        inactive_users_list_label.pack(pady=5)
        Separator(inactive_users_list_container, orient=HORIZONTAL).pack(fill=X)
        active_users_list_frame.pack(fill=BOTH, expand=TRUE, anchor=E, padx=3, pady=3)
        inactive_users_list_frame.pack(fill=BOTH, expand=TRUE, anchor=E, padx=3, pady=3)
        active_users_list_container.pack(side=RIGHT, expand=TRUE, fill=Y)
        inactive_users_list_container.pack(side=LEFT, expand=TRUE, fill=Y)
        search_field.pack(side=LEFT)
        search_button.pack(side=RIGHT)
        search_frame.pack(side=BOTTOM, ipady=5)
        Separator(users_list_frame, orient=HORIZONTAL).pack(side=BOTTOM, fill=X)
        scrollable_lists_frame.pack(side=BOTTOM, expand=TRUE, fill=Y)
        users_list_frame.pack(side=RIGHT, fill=BOTH, expand=TRUE)


    class EditSettingsDialog(dialog.Dialog):  # modal dialog for folder configuration.

        def body(self, master):

            self.settings = settings.find_one(id=1)
            self.resizable(width=FALSE, height=FALSE)
            self.logs_directory = self.foldersnameinput['logs_directory']
            self.title("Edit Settings")
            self.enable_email_checkbutton_variable = BooleanVar(master)
            self.enable_interval_backup_variable = BooleanVar(master)
            self.enable_reporting_checkbutton_variable = StringVar(master)
            self.enable_report_printing_checkbutton_variable = StringVar(master)
            self.report_edi_validator_warnings_checkbutton_variable = BooleanVar(master)
            self.odbc_drivers_var = StringVar(master)

            as400_db_connection_frame = Frame(master=master)
            report_sending_options_frame = Frame(master)
            email_options_frame = Frame(master)
            interval_backups_frame = Frame(master)

            # Label(master, text='Test').grid(row=0, column=0)
            as400_db_connection_frame.grid(row=0, column=0, sticky=(W,E), columnspan=2)

            Label(as400_db_connection_frame, text="ODBC Driver:").grid(row=1, column=0, sticky=E)
            Label(as400_db_connection_frame, text="AS400 Address:").grid(row=2, column=0, sticky=E)
            Label(as400_db_connection_frame, text="AS400 Username:").grid(row=3, column=0, sticky=E)
            Label(as400_db_connection_frame, text="AS400 Password:").grid(row=4, column=0, sticky=E)

            Label(email_options_frame, text="Email Address:").grid(row=1, sticky=E)
            Label(email_options_frame, text="Email Username:").grid(row=2, sticky=E)
            Label(email_options_frame, text="Email Password:").grid(row=3, sticky=E)
            Label(email_options_frame, text="Email SMTP Server:").grid(row=4, sticky=E)
            Label(email_options_frame, text="Email SMTP Port").grid(row=5, sticky=E)
            Label(report_sending_options_frame, text="Email Destination:").grid(row=7, sticky=E)

            def reporting_options_fields_state_set():
                if self.enable_reporting_checkbutton_variable.get() == "False":
                    state = DISABLED
                else:
                    state = NORMAL
                for child in report_sending_options_frame.winfo_children():
                    child.configure(state=state)

            def email_options_fields_state_set():
                if self.enable_email_checkbutton_variable.get() ==False:
                    self.enable_reporting_checkbutton_variable.set("False")
                    state = DISABLED
                else:
                    state = NORMAL
                for child in email_options_frame.winfo_children():
                    child.configure(state=state)
                reporting_options_fields_state_set()
                self.run_reporting_checkbutton.configure(state=state)

            def interval_backup_options_set():
                if self.enable_interval_backup_variable.get():
                    self.interval_backup_spinbox.configure(state=NORMAL)
                    self.interval_backup_interval_label.configure(state=NORMAL)
                else:
                    self.interval_backup_spinbox.configure(state=DISABLED)
                    self.interval_backup_interval_label.configure(state=DISABLED)

            self.enable_email_checkbutton = Checkbutton(master, variable=self.enable_email_checkbutton_variable,
                                                        onvalue=True, offvalue=False,
                                                        command=email_options_fields_state_set, text="Enable Email")
            self.run_reporting_checkbutton = Checkbutton(master, variable=self.enable_reporting_checkbutton_variable,
                                                         onvalue="True", offvalue="False",
                                                         command=reporting_options_fields_state_set,
                                                         text="Enable Report Sending")
            self.report_edi_validator_warnings_checkbutton = \
                Checkbutton(master, variable=self.report_edi_validator_warnings_checkbutton_variable,
                            onvalue=True, offvalue=False, text="Report EDI Validator Warnings")
            self.enable_interval_backup_checkbutton = Checkbutton(interval_backups_frame,
                                                                  variable=self.enable_interval_backup_variable,
                                                                  onvalue=True, offvalue=False,
                                                                  command=interval_backup_options_set,
                                                                  text="Enable interval backup")
            self.interval_backup_interval_label = Label(interval_backups_frame, text="Backup interval: ")
            self.interval_backup_spinbox = Spinbox(interval_backups_frame, from_=1, to=5000, width=4, justify=RIGHT)
            self.odbc_driver_selector_menu = OptionMenu(as400_db_connection_frame, self.odbc_drivers_var,
                                            self.settings['odbc_driver'], *[i for i in pyodbc.drivers()])

            self.as400_address_field = Entry(as400_db_connection_frame, width=40)
            self.as400_username_field = Entry(as400_db_connection_frame, width=40)
            self.as400_password_field = Entry(as400_db_connection_frame, width=40)
            self.email_address_field = Entry(email_options_frame, width=40)
            self.email_username_field = Entry(email_options_frame, width=40)
            self.email_password_field = Entry(email_options_frame, show="*", width=40)
            self.email_smtp_server_field = Entry(email_options_frame, width=40)
            self.smtp_port_field = Entry(email_options_frame, width=40)
            self.report_email_destination_field = Entry(report_sending_options_frame, width=40)
            self.log_printing_fallback_checkbutton = \
                Checkbutton(report_sending_options_frame, variable=self.enable_report_printing_checkbutton_variable,
                            onvalue="True", offvalue="False", text="Enable Report Printing Fallback:")
            rclick_as400_address_field = rclick_menu.RightClickMenu(self.as400_address_field)
            rclick_as400_username_field = rclick_menu.RightClickMenu(self.as400_username_field)
            rclick_as400_password_field = rclick_menu.RightClickMenu(self.as400_password_field)
            rclick_report_email_address_field = rclick_menu.RightClickMenu(self.email_address_field)
            rclick_report_email_username_field = rclick_menu.RightClickMenu(self.email_username_field)
            rclick_report_email_smtp_server_field = rclick_menu.RightClickMenu(self.email_smtp_server_field)
            rclick_reporting_smtp_port_field = rclick_menu.RightClickMenu(self.smtp_port_field)
            rclick_report_email_destination_field = rclick_menu.RightClickMenu(self.report_email_destination_field)
            self.as400_address_field.bind("<3>", rclick_as400_address_field)
            self.as400_username_field.bind("<3>", rclick_as400_username_field)
            self.as400_password_field.bind("<3>", rclick_as400_password_field)
            self.email_address_field.bind("<3>", rclick_report_email_address_field)
            self.email_username_field.bind("<3>", rclick_report_email_username_field)
            self.email_smtp_server_field.bind("<3>", rclick_report_email_smtp_server_field)
            self.smtp_port_field.bind("<3>", rclick_reporting_smtp_port_field)
            self.report_email_destination_field.bind("<3>", rclick_report_email_destination_field)
            self.select_log_folder_button = Button(master, text="Select Log Folder...",
                                                   command=lambda: select_log_directory())

            def select_log_directory():
                try:
                    if os.path.exists(self.logs_directory):
                        initial_directory = self.logs_directory
                    else:
                        initial_directory = os.getcwd()
                except Exception as folder_select_error:
                    print(folder_select_error)
                    initial_directory = os.getcwd()
                logs_directory_edit_proposed = str(askdirectory(parent=master, initialdir=initial_directory))
                if len(logs_directory_edit_proposed) > 0:
                    self.logs_directory = logs_directory_edit_proposed

            self.enable_email_checkbutton_variable.set(self.settings['enable_email'])
            self.enable_reporting_checkbutton_variable.set(self.foldersnameinput['enable_reporting'])
            self.as400_address_field.insert(0, self.settings['as400_address'])
            self.as400_username_field.insert(0, self.settings['as400_username'])
            self.as400_password_field.insert(0, self.settings['as400_password'])
            self.email_address_field.insert(0, self.settings['email_address'])
            self.email_username_field.insert(0, self.settings['email_username'])
            self.email_password_field.insert(0, self.settings['email_password'])
            self.email_smtp_server_field.insert(0, self.settings['email_smtp_server'])
            self.smtp_port_field.insert(0, self.settings['smtp_port'])
            self.report_email_destination_field.insert(0, self.foldersnameinput['report_email_destination'])
            self.enable_interval_backup_variable.set(self.settings['enable_interval_backups'])
            self.enable_report_printing_checkbutton_variable.set(self.foldersnameinput['report_printing_fallback'])
            self.report_edi_validator_warnings_checkbutton_variable.set(self.foldersnameinput['report_edi_errors'])
            self.interval_backup_spinbox.delete(0, "end")
            self.interval_backup_spinbox.insert(0, self.settings['backup_counter_maximum'])

            email_options_fields_state_set()
            reporting_options_fields_state_set()

            self.enable_email_checkbutton.grid(row=1, columnspan=3, sticky=W)
            email_options_frame.grid(row=2, columnspan=3)
            report_sending_options_frame.grid(row=5, columnspan=3)
            interval_backups_frame.grid(row=9, column=0, columnspan=3, sticky=W + E)
            interval_backups_frame.columnconfigure(0, weight=1)
            self.run_reporting_checkbutton.grid(row=3, column=0, padx=2, pady=2, sticky=W)
            self.report_edi_validator_warnings_checkbutton.grid(row=4, column=0, padx=2, pady=2, sticky=W)
            self.odbc_driver_selector_menu.grid(row=1, column=1)
            self.as400_address_field.grid(row=2, column=1, padx=2, pady=2)
            self.as400_username_field.grid(row=3, column=1, padx=2, pady=2)
            self.as400_password_field.grid(row=4, column=1, padx=2, pady=2)
            self.email_address_field.grid(row=1, column=1, padx=2, pady=2)
            self.email_username_field.grid(row=2, column=1, padx=2, pady=2)
            self.email_password_field.grid(row=3, column=1, padx=2, pady=2)
            self.email_smtp_server_field.grid(row=4, column=1, padx=2, pady=2)
            self.smtp_port_field.grid(row=5, column=1, padx=2, pady=2)
            self.report_email_destination_field.grid(row=7, column=1, padx=2, pady=2)
            self.select_log_folder_button.grid(row=3, column=1, padx=2, pady=2, sticky=E, rowspan=2)
            self.log_printing_fallback_checkbutton.grid(row=8, column=1, padx=2, pady=2, sticky=W)
            self.enable_interval_backup_checkbutton.grid(row=0, column=0, sticky=W, padx=2, pady=2)
            self.interval_backup_interval_label.grid(row=0, column=1, sticky=E, padx=2, pady=2)
            self.interval_backup_interval_label.columnconfigure(0, weight=1)
            self.interval_backup_spinbox.grid(row=0, column=2, sticky=E, padx=2, pady=2)

            return self.email_address_field  # initial focus

        @property
        def validate(self):

            doingstuffoverlay.make_overlay(self, "Testing Changes...")
            error_list = []
            errors = False

            if self.enable_email_checkbutton_variable.get():
                if self.email_address_field.get() == '':
                    error_list.append("Email Address is A Required Field\r")
                    errors = True
                else:
                    if (validate_email(str(self.email_address_field.get()), verify=True)) ==False:
                        error_list.append("Invalid Email Origin Address\r")
                        errors = True

                try:
                    server = smtplib.SMTP(str(self.email_smtp_server_field.get()), str(self.smtp_port_field.get()))
                    server.ehlo()
                    server.starttls()
                    if self.email_username_field.get() != "" and self.email_password_field.get() != "":
                        server.login(str(self.email_username_field.get()), str(self.email_password_field.get()))
                    server.quit()
                except Exception as email_test_login_result_string:
                    print(email_test_login_result_string)
                    error_list.append("Test Login Failed With Error\r" + str(email_test_login_result_string))
                    errors = True

                if self.email_username_field.get() == '' and self.email_password_field.get() != '':
                    error_list.append("Email Username Required If Password is Set\r")
                    errors = True

                if self.email_password_field.get() == '' and self.email_username_field.get() != '':
                    error_list.append("Email Username Without Password != Supported\r")
                    errors = True

                if self.email_smtp_server_field.get() == '':
                    error_list.append("SMTP Server Address is A Required Field\r")
                    errors = True

                if self.smtp_port_field.get() == '':
                    error_list.append("SMTP Port is A Required Field\r")
                    errors = True

            if self.enable_reporting_checkbutton_variable.get() == "True":
                if self.report_email_destination_field.get() == '':
                    error_list.append("Reporting Email Destination is A Required Field\r")
                    errors = True
                else:
                    email_recipients = str(self.report_email_destination_field.get()).split(", ")
                    for email_recipient in email_recipients:
                        print(email_recipient)
                        if (validate_email(str(email_recipient), verify=True)) ==False:
                            error_list.append("Invalid Email Destination Address\r\n")
                            errors = True

            if self.enable_interval_backup_variable.get():
                try:
                    backup_interval = int(self.interval_backup_spinbox.get())
                    if backup_interval < 1 or backup_interval > 5000:
                        raise ValueError
                except ValueError:
                    error_list.append("Backup Interval Needs To Be A Number Between 1 and 5000")
                    errors = True

            if errors ==True:
                error_report = ''.join(error_list)  # combine error messages into single string
                showerror(parent=self, message=error_report)  # display generated error string in error dialog
                doingstuffoverlay.destroy_overlay()
                return False
            doingstuffoverlay.destroy_overlay()

            if not self.enable_email_checkbutton_variable.get():
                number_of_disabled_email_backends = folders_table.count(process_backend_email=True)
                number_of_disabled_folders = folders_table.count(process_backend_email=True, process_backend_ftp=False,
                                                                 process_backend_copy=False, folder_is_active="True")
                if number_of_disabled_folders != 0:
                    if not askokcancel(message="This will disable the email backend in " +
                                               str(number_of_disabled_email_backends) + " folders.\nAs a result, " +
                                               str(number_of_disabled_folders) + " folders will be disabled"):
                        return False
            return 1

        def ok(self, event=None):

            if not self.validate:
                self.initial_focus.focus_set()  # put focus back
                return

            self.withdraw()
            self.update_idletasks()

            self.apply(self.foldersnameinput)
            self.cancel()

        def apply(self, folders_name_apply):

            doingstuffoverlay.make_overlay(root, "Applying Changes...")
            root.update()
            folders_name_apply['enable_reporting'] = str(self.enable_reporting_checkbutton_variable.get())
            folders_name_apply['logs_directory'] = self.logs_directory
            self.settings['odbc_driver'] = self.odbc_drivers_var.get()
            self.settings['as400_username'] = self.as400_username_field.get()
            self.settings['as400_password'] = self.as400_password_field.get()
            self.settings['as400_address'] = self.as400_address_field.get()
            self.settings['enable_email'] = self.enable_email_checkbutton_variable.get()
            self.settings['email_address'] = str(self.email_address_field.get())
            self.settings['email_username'] = str(self.email_username_field.get())
            self.settings['email_password'] = str(self.email_password_field.get())
            self.settings['email_smtp_server'] = str(self.email_smtp_server_field.get())
            self.settings['smtp_port'] = str(self.smtp_port_field.get())
            self.settings['enable_interval_backups'] = self.enable_interval_backup_variable.get()
            self.settings['backup_counter_maximum'] = int(self.interval_backup_spinbox.get())
            folders_name_apply['report_email_destination'] = str(self.report_email_destination_field.get())
            folders_name_apply['report_edi_errors'] = self.report_edi_validator_warnings_checkbutton_variable.get()
            if not self.enable_email_checkbutton_variable.get():
                for email_backend_to_disable in folders_table.find(process_backend_email=True):
                    email_backend_to_disable['process_backend_email'] = False
                    folders_table.update(email_backend_to_disable, ['id'])
                for folder_to_disable in folders_table.find(process_backend_email=False, process_backend_ftp=False,
                                                            process_backend_copy=False, folder_is_active="True"):
                    folder_to_disable['folder_is_active'] = "False"
                    folders_table.update(folder_to_disable, ['id'])
                folders_name_apply['folder_is_active'] = 'False'
                folders_name_apply['process_backend_email'] = False

            settings.update(self.settings, ['id'])
            update_reporting(folders_name_apply)
            doingstuffoverlay.destroy_overlay()
            refresh_users_list()


    class EditDialog(dialog.Dialog):  # modal dialog for folder configuration.

        def body(self, master):

            self.settings = settings.find_one(id=1)
            self.resizable(width=FALSE, height=FALSE)
            global copy_to_directory
            copy_to_directory = self.foldersnameinput['copy_to_directory']
            self.convert_formats_var = StringVar(master)
            self.title("Folder Settings")
            self.bodyframe = Frame(master)
            self.othersframe = Frame(self.bodyframe)
            self.folderframe = Frame(self.bodyframe)
            self.prefsframe = Frame(self.bodyframe)
            self.ediframe = Frame(self.bodyframe)
            self.convert_options_frame = Frame(self.ediframe)
            self.separatorv0 = Separator(self.bodyframe, orient=VERTICAL)
            self.separatorv1 = Separator(self.bodyframe, orient=VERTICAL)
            self.separatorv2 = Separator(self.bodyframe, orient=VERTICAL)
            self.backendvariable = StringVar(master)
            self.active_checkbutton = StringVar(master)
            self.split_edi = BooleanVar(master)
            self.ediconvert_options = StringVar(master)
            self.process_edi = StringVar(master)
            self.upc_var_check = StringVar(master)  # define  "UPC calculation" checkbox state variable
            self.a_rec_var_check = StringVar(master)  # define "A record checkbox state variable
            self.c_rec_var_check = StringVar(master)  # define "C record" checkbox state variable
            self.headers_check = StringVar(master)  # define "Column Headers" checkbox state variable
            self.ampersand_check = StringVar(master)  # define "Filter Ampersand" checkbox state variable
            self.tweak_edi = BooleanVar(master)
            self.pad_arec_check = StringVar(master)
            self.append_arec_check = StringVar(master)
            self.force_txt_file_ext_check = StringVar(master)
            self.process_backend_copy_check = BooleanVar(master)
            self.process_backend_ftp_check = BooleanVar(master)
            self.process_backend_email_check = BooleanVar(master)
            self.force_edi_check_var = BooleanVar(master)
            self.header_frame_frame = Frame(master)
            self.invoice_date_offset = IntVar(master)
            self.otherslistboxframe = Frame(master=self.othersframe)
            self.otherslistbox = Listbox(master=self.otherslistboxframe)
            self.otherslistboxscrollbar = Scrollbar(master=self.otherslistboxframe, orient=VERTICAL)
            self.otherslistboxscrollbar.config(command=self.otherslistbox.yview)
            self.otherslistbox.config(yscrollcommand=self.otherslistboxscrollbar.set)
            self.copyconfigbutton = Button(master=self.othersframe, text="Copy Config")
            Label(self.folderframe, text="Backends:").grid(row=2, sticky=W)
            Label(self.prefsframe, text="Copy Backend Settings:").grid(row=3, columnspan=2, pady=3)
            Separator(self.prefsframe, orient=HORIZONTAL).grid(row=5, columnspan=2, sticky=E + W, pady=2)
            Label(self.prefsframe, text="Ftp Backend Settings:").grid(row=6, columnspan=2, pady=3)
            Label(self.prefsframe, text="FTP Server:").grid(row=7, sticky=E)
            Label(self.prefsframe, text="FTP Port:").grid(row=8, sticky=E)
            Label(self.prefsframe, text="FTP Folder:").grid(row=9, sticky=E)
            Label(self.prefsframe, text="FTP Username:").grid(row=10, sticky=E)
            Label(self.prefsframe, text="FTP Password:").grid(row=11, sticky=E)
            Separator(self.prefsframe, orient=HORIZONTAL).grid(row=12, columnspan=2, sticky=E + W, pady=2)
            Label(self.prefsframe, text="Email Backend Settings:").grid(row=13, columnspan=2, pady=3)
            Label(self.prefsframe, text="Recipient Address:").grid(row=14, sticky=E)
            Label(self.prefsframe, text="Email Subject:").grid(row=18, sticky=E)
            Label(self.ediframe, text="EDI Convert Settings:").grid(row=0, column=0, columnspan=2, pady=3)
            Separator(self.ediframe, orient=HORIZONTAL).grid(row=4, columnspan=2, sticky=E + W, pady=1)
            self.convert_options_frame.grid(column=0, row=5, columnspan=2, sticky=W)
            self.convert_to_selector_frame = Frame(self.convert_options_frame)
            self.convert_to_selector_label = Label(self.convert_to_selector_frame, text="Convert To: ")

            def make_convert_to_options(_=None):
                for frameentry in [self.upc_variable_process_checkbutton,
                    self.a_record_checkbutton,
                    self.c_record_checkbutton,
                    self.headers_checkbutton,
                    self.ampersand_checkbutton,
                    self.pad_a_records_checkbutton,
                    self.a_record_padding_field]:
                    frameentry.grid_forget()
                if self.convert_formats_var.get() == 'csv':
                    self.upc_variable_process_checkbutton.grid(row=2, column=0, sticky=W, padx=3)
                    self.a_record_checkbutton.grid(row=4, column=0, sticky=W, padx=3)
                    self.c_record_checkbutton.grid(row=5, column=0, sticky=W, padx=3)
                    self.headers_checkbutton.grid(row=6, column=0, sticky=W, padx=3)
                    self.ampersand_checkbutton.grid(row=7, column=0, sticky=W, padx=3)
                    self.pad_a_records_checkbutton.grid(row=9, column=0, sticky=W, padx=3)
                    self.a_record_padding_field.grid(row=9, column=2)
                if self.convert_formats_var.get() == 'ScannerWare':
                    self.pad_a_records_checkbutton.grid(row=2, column=0, sticky=W, padx=3)
                    self.a_record_padding_field.grid(row=2, column=2)
                    self.append_a_records_checkbutton.grid(row=3, column=0, sticky=W, padx=3)
                    self.a_record_append_field.grid(row=3, column=2)

            self.convert_to_selector_menu = OptionMenu(self.convert_to_selector_frame, self.convert_formats_var,
                                                       self.foldersnameinput['convert_to_format'], 'csv', 'ScannerWare', 'scansheet-type-a', command=make_convert_to_options)

            def show_folder_path():
                showinfo(parent=master, title="Folder Path", message=self.foldersnameinput['folder_name'])

            def select_copy_to_directory():
                global copy_to_directory
                try:
                    if os.path.exists(copy_to_directory):
                        initial_directory = copy_to_directory
                    else:
                        initial_directory = os.getcwd()
                except Exception as select_copy_directory_error:
                    print(select_copy_directory_error)
                    initial_directory = os.getcwd()
                proposed_copy_to_directory = str(askdirectory(parent=self.prefsframe, initialdir=initial_directory))
                if os.path.isdir(proposed_copy_to_directory):
                    copy_to_directory = proposed_copy_to_directory

            def set_send_options_fields_state():
                if not self.settings['enable_email']:
                    self.email_backend_checkbutton.configure(state=DISABLED)
                if self.process_backend_copy_check.get() ==False and self.process_backend_ftp_check.get() ==False and \
                        self.process_backend_email_check.get() ==False:
                    self.split_edi_checkbutton.configure(state=DISABLED)
                    self.edi_options_menu.configure(state=DISABLED)
                    for child in self.convert_options_frame.winfo_children():
                        try:
                            child.configure(state=DISABLED)
                        except TclError:
                            pass
                    for child in self.convert_to_selector_frame.winfo_children():
                        try:
                            child.configure(state=DISABLED)
                        except TclError:
                            pass
                else:
                    self.split_edi_checkbutton.configure(state=NORMAL)
                    self.edi_options_menu.configure(state=NORMAL)
                    for child in self.convert_options_frame.winfo_children():
                        try:
                            child.configure(state=NORMAL)
                        except TclError:
                            pass
                    for child in self.convert_to_selector_frame.winfo_children():
                        try:
                            child.configure(state=NORMAL)
                        except TclError:
                            pass
                if self.process_backend_copy_check.get() ==False:
                    copy_state = DISABLED
                else:
                    copy_state = NORMAL
                if self.process_backend_email_check.get() ==False or self.settings['enable_email'] ==False:
                    email_state = DISABLED
                else:
                    email_state = NORMAL
                if self.process_backend_ftp_check.get() ==False:
                    ftp_state = DISABLED
                else:
                    ftp_state = NORMAL
                self.copy_backend_folder_selection_button.configure(state=copy_state)
                self.email_recepient_field.configure(state=email_state)
                self.email_sender_subject_field.configure(state=email_state)
                self.ftp_server_field.configure(state=ftp_state)
                self.ftp_port_field.configure(state=ftp_state)
                self.ftp_folder_field.configure(state=ftp_state)
                self.ftp_username_field.configure(state=ftp_state)
                self.ftp_password_field.configure(state=ftp_state)

            def set_header_state():
                if self.active_checkbutton.get() == "False":
                    self.active_checkbutton_object.configure(text="Folder ==Disabled", activebackground="green")
                    self.copy_backend_checkbutton.configure(state=DISABLED)
                    self.ftp_backend_checkbutton.configure(state=DISABLED)
                    self.email_backend_checkbutton.configure(state=DISABLED)
                else:
                    self.active_checkbutton_object.configure(text="Folder ==Enabled", activebackground="red")
                    self.copy_backend_checkbutton.configure(state=NORMAL)
                    self.ftp_backend_checkbutton.configure(state=NORMAL)
                    if self.settings['enable_email']:
                        self.email_backend_checkbutton.configure(state=NORMAL)

            self.active_checkbutton_object = tkinter.Checkbutton(self.header_frame_frame, text="Active",
                                                                 variable=self.active_checkbutton,
                                                                 onvalue="True", offvalue="False", command=set_header_state,
                                                                 indicatoron=FALSE, selectcolor="green",
                                                                 background="red")
            self.copy_backend_checkbutton = Checkbutton(self.folderframe, text="Copy Backend",
                                                        variable=self.process_backend_copy_check,
                                                        onvalue=True, offvalue=False, command=set_send_options_fields_state)
            self.ftp_backend_checkbutton = Checkbutton(self.folderframe, text="FTP Backend",
                                                       variable=self.process_backend_ftp_check,
                                                       onvalue=True, offvalue=False, command=set_send_options_fields_state)
            self.email_backend_checkbutton = Checkbutton(self.folderframe, text="Email Backend",
                                                         variable=self.process_backend_email_check,
                                                         onvalue=True, offvalue=False,
                                                         command=set_send_options_fields_state)
            if self.foldersnameinput['folder_name'] != 'template':
                self.folder_alias_frame = Frame(self.folderframe)
                Label(self.folder_alias_frame, text="Folder Alias:").grid(row=0, sticky=W)
                self.folder_alias_field = Entry(self.folder_alias_frame, width=30)
                rclick_folder_alias_field = rclick_menu.RightClickMenu(self.folder_alias_field)
                self.folder_alias_field.bind("<3>", rclick_folder_alias_field)
                self.folder_alias_field.grid(row=0, column=1)
                Button(master=self.folder_alias_frame, text="Show Folder Path",
                       command=show_folder_path).grid(row=1, columnspan=2, sticky=W, pady=5)
            self.copy_backend_folder_selection_button = Button(self.prefsframe,
                                                               text="Select Copy Backend Destination Folder...",
                                                               command=lambda: select_copy_to_directory())
            self.ftp_server_field = Entry(self.prefsframe, width=30)
            rclick_ftp_server_field = rclick_menu.RightClickMenu(self.ftp_server_field)
            self.ftp_server_field.bind("<3>", rclick_ftp_server_field)
            self.ftp_port_field = Entry(self.prefsframe, width=30)
            rclick_ftp_port_field = rclick_menu.RightClickMenu(self.ftp_port_field)
            self.ftp_port_field.bind("<3>", rclick_ftp_port_field)
            self.ftp_folder_field = Entry(self.prefsframe, width=30)
            rclick_ftp_folder_field = rclick_menu.RightClickMenu(self.ftp_folder_field)
            self.ftp_folder_field.bind("<3>", rclick_ftp_folder_field)
            self.ftp_username_field = Entry(self.prefsframe, width=30)
            rclick_ftp_username_field = rclick_menu.RightClickMenu(self.ftp_username_field)
            self.ftp_username_field.bind("<3>", rclick_ftp_username_field)
            self.ftp_password_field = Entry(self.prefsframe, show="*", width=30)
            self.email_recepient_field = Entry(self.prefsframe, width=30)
            rclick_email_recepient_field = rclick_menu.RightClickMenu(self.email_recepient_field)
            self.email_recepient_field.bind("<3>", rclick_email_recepient_field)
            self.email_sender_subject_field = Entry(self.prefsframe, width=30)
            rclick_email_sender_subject_field = rclick_menu.RightClickMenu(self.email_sender_subject_field)
            self.email_sender_subject_field.bind("<3>", rclick_email_sender_subject_field)

            self.force_edi_check_checkbutton = Checkbutton(self.ediframe, variable=self.force_edi_check_var,
                                                           text="Force EDI Validation",
                                                           onvalue=True, offvalue=False)

            self.split_edi_checkbutton = Checkbutton(self.ediframe, variable=self.split_edi,
                                                     text="Split EDI",
                                                     onvalue=True, offvalue=False)
            self.process_edi_checkbutton = Checkbutton(self.convert_options_frame, variable=self.process_edi,
                                                       text="Process EDI",
                                                       onvalue="True", offvalue="False")
            self.upc_variable_process_checkbutton = Checkbutton(self.convert_options_frame, variable=self.upc_var_check,
                                                                text="Calculate UPC Check Digit",
                                                                onvalue="True", offvalue="False")
            self.a_record_checkbutton = Checkbutton(self.convert_options_frame, variable=self.a_rec_var_check,
                                                    text="Include " + "A " + "Records",
                                                    onvalue="True", offvalue="False")
            self.c_record_checkbutton = Checkbutton(self.convert_options_frame, variable=self.c_rec_var_check,
                                                    text="Include " + "C " + "Records",
                                                    onvalue="True", offvalue="False")
            self.headers_checkbutton = Checkbutton(self.convert_options_frame, variable=self.headers_check,
                                                   text="Include Headings",
                                                   onvalue="True", offvalue="False")
            self.ampersand_checkbutton = Checkbutton(self.convert_options_frame, variable=self.ampersand_check,
                                                     text="Filter Ampersand:",
                                                     onvalue="True", offvalue="False")
            self.tweak_edi_checkbutton = Checkbutton(self.convert_options_frame, variable=self.tweak_edi,
                                                     text="Apply Edi Tweaks",
                                                     onvalue=True, offvalue=False)
            self.pad_a_records_checkbutton = Checkbutton(self.convert_options_frame, variable=self.pad_arec_check,
                                                         text="Pad \"A\" Records (6 Characters)",
                                                         onvalue="True", offvalue="False")

            self.a_record_padding_field = Entry(self.convert_options_frame, width=10)

            self.append_a_records_checkbutton = Checkbutton(self.convert_options_frame, variable=self.append_arec_check,
                                                            text="Append to \"A\" Records (6 Characters)\n(Series2K)",
                                                            onvalue="True", offvalue="False")
            self.a_record_append_field = Entry(self.convert_options_frame, width=10)
            self.force_txt_file_ext_checkbutton = Checkbutton(self.convert_options_frame,
                                                              variable=self.force_txt_file_ext_check,
                                                              text="Force .txt file extension",
                                                              onvalue="True", offvalue="False")
            self.invoice_date_offset_spinbox_label = Label(self.convert_options_frame, text="Invoice Offset (Days)")
            self.invoice_date_offset_spinbox = Spinbox(self.convert_options_frame, textvariable=self.invoice_date_offset,
                                                       from_=-14, to=14, width=3)

            def set_dialog_variables(config_dict, copied):
                if copied:
                    for child in self.bodyframe.winfo_children():
                        try:
                            child.configure(state=NORMAL)
                        except Exception:
                            pass
                self.active_checkbutton.set(config_dict['folder_is_active'])
                if config_dict['folder_name'] != 'template' and not copied:
                    self.folder_alias_field.insert(0, config_dict['alias'])
                self.process_backend_copy_check.set(config_dict['process_backend_copy'])
                self.process_backend_ftp_check.set(config_dict['process_backend_ftp'])
                self.process_backend_email_check.set(config_dict['process_backend_email'])

                self.ftp_server_field.delete(0, END)
                self.ftp_port_field.delete(0, END)
                self.ftp_folder_field.delete(0, END)
                self.ftp_username_field.delete(0, END)
                self.ftp_password_field.delete(0, END)
                self.email_recepient_field.delete(0, END)
                self.email_sender_subject_field.delete(0, END)
                
                self.ftp_server_field.insert(0, config_dict['ftp_server'])
                self.ftp_port_field.insert(0, config_dict['ftp_port'])
                self.ftp_folder_field.insert(0, config_dict['ftp_folder'])
                self.ftp_username_field.insert(0, config_dict['ftp_username'])
                self.ftp_password_field.insert(0, config_dict['ftp_password'])
                self.email_recepient_field.insert(0, config_dict['email_to'])
                self.email_sender_subject_field.insert(0, config_dict['email_subject_line'])

                self.force_edi_check_var.set(config_dict['force_edi_validation'])
                self.process_edi.set(config_dict['process_edi'])
                self.upc_var_check.set(config_dict['calculate_upc_check_digit'])
                self.a_rec_var_check.set(config_dict['include_a_records'])
                self.c_rec_var_check.set(config_dict['include_c_records'])
                self.headers_check.set(config_dict['include_headers'])
                self.ampersand_check.set(config_dict['filter_ampersand'])
                self.pad_arec_check.set(config_dict['pad_a_records'])
                self.tweak_edi.set(config_dict['tweak_edi'])
                self.split_edi.set(config_dict['split_edi'])
                self.a_record_padding_field.delete(0, END)
                self.a_record_padding_field.insert(0, config_dict['a_record_padding'])
                self.append_arec_check.set(config_dict['append_a_records'])
                self.a_record_append_field.delete(0, END)
                self.a_record_append_field.insert(0, config_dict['a_record_append_text'])
                self.force_txt_file_ext_check.set(config_dict['force_txt_file_ext'])
                self.invoice_date_offset.set(config_dict['invoice_date_offset'])

                if copied:
                    if config_dict['process_edi'] == 'True':
                        self.ediconvert_options.set("Convert EDI")
                        reset_ediconvert_options('Convert EDI')
                    elif config_dict['tweak_edi'] ==True:
                        self.ediconvert_options.set("Tweak EDI")
                        reset_ediconvert_options('Tweak EDI')
                    else:
                        self.ediconvert_options.set("Do Nothing")
                        reset_ediconvert_options('Do Nothing')
            
            set_dialog_variables(self.foldersnameinput, False)

            def reset_ediconvert_options(argument):
                for child in self.convert_options_frame.winfo_children():
                    child.grid_forget()
                make_ediconvert_options(argument)

            self.split_edi_checkbutton.grid(row=2, column=0, columnspan=2, sticky=W)

            def make_ediconvert_options(argument):
                if argument == 'Do Nothing':
                    self.tweak_edi.set(False)
                    self.process_edi.set('False')
                    Label(self.convert_options_frame, text="Send As Is").grid()
                if argument == 'Convert EDI':
                    self.process_edi.set('True')
                    self.tweak_edi.set(False)
                    self.convert_to_selector_frame.grid(row=0, column=0, columnspan=2)
                    self.convert_to_selector_label.grid(row=0, column=0, sticky=W)
                    self.convert_to_selector_menu.grid(row=0, column=1, sticky=W)
                    make_convert_to_options()
                if argument == 'Tweak EDI':
                    self.tweak_edi.set(True)
                    self.process_edi.set('False')
                    self.upc_variable_process_checkbutton.grid(row=2, column=0, sticky=W, padx=3)
                    self.pad_a_records_checkbutton.grid(row=9, column=0, sticky=W, padx=3)
                    self.a_record_padding_field.grid(row=9, column=2)
                    self.append_a_records_checkbutton.grid(row=10, column=0, sticky=W, padx=3)
                    self.a_record_append_field.grid(row=10, column=2)
                    self.force_txt_file_ext_checkbutton.grid(row=11, column=0, sticky=W, padx=3)
                    self.invoice_date_offset_spinbox_label.grid(row=12, column=0, sticky=W, padx=3)
                    self.invoice_date_offset_spinbox.grid(row=12, column=2, sticky=W, padx=3)

            if self.foldersnameinput['process_edi'] == 'True':
                self.ediconvert_options.set("Convert EDI")
                make_ediconvert_options('Convert EDI')
            elif self.foldersnameinput['tweak_edi'] ==True:
                self.ediconvert_options.set("Tweak EDI")
                make_ediconvert_options('Tweak EDI')
            else:
                self.ediconvert_options.set("Do Nothing")
                make_ediconvert_options('Do Nothing')

            self.edi_options_menu = OptionMenu(self.ediframe, self.ediconvert_options, self.ediconvert_options.get(),
                                               'Do Nothing', 'Convert EDI', 'Tweak EDI', command=reset_ediconvert_options)

            def config_from_others():
                def recurse_set_default(parent):
                    for child in parent.winfo_children():
                        try:
                            child.configure(state=NORMAL)
                        except Exception:
                            pass
                        recurse_set_default(child)
                recurse_set_default(master)
                settings_table = folders_table.find_one(alias=self.otherslistbox.get(ACTIVE))
                set_dialog_variables(settings_table, True)
                set_header_state()
                set_send_options_fields_state()

            self.copyconfigbutton.configure(command=config_from_others)

            set_header_state()
            set_send_options_fields_state()

            self.force_edi_check_checkbutton.grid(row=1, column=0, columnspan=2, sticky=W)
            self.edi_options_menu.grid(row=3)
            self.active_checkbutton_object.pack(fill=X)
            self.copy_backend_checkbutton.grid(row=3, column=0, sticky=W)
            self.ftp_backend_checkbutton.grid(row=4, column=0, sticky=W)
            self.email_backend_checkbutton.grid(row=5, column=0, sticky=W)
            if self.foldersnameinput['folder_name'] != 'template':
                self.folder_alias_frame.grid(row=6, column=0, columnspan=2)
            self.copy_backend_folder_selection_button.grid(row=4, column=0, columnspan=2)
            self.ftp_server_field.grid(row=7, column=1)
            self.ftp_port_field.grid(row=8, column=1)
            self.ftp_folder_field.grid(row=9, column=1)
            self.ftp_username_field.grid(row=10, column=1)
            self.ftp_password_field.grid(row=11, column=1)
            self.email_recepient_field.grid(row=14, column=1)
            self.email_sender_subject_field.grid(row=18, column=1)
            self.otherslistbox.pack(side=LEFT, fill=Y)
            self.otherslistboxscrollbar.pack(side=RIGHT, fill=Y)
            self.copyconfigbutton.pack()

            for entry in folders_table.all():
                self.otherslistbox.insert(END, entry['alias'])
            self.otherslistbox.config(width=0, height=10)

            self.header_frame_frame.pack(fill=X)
            self.bodyframe.pack()

            self.othersframe.pack(side=LEFT, fill=Y)
            self.otherslistboxframe.pack(side=LEFT, fill=Y)
            self.separatorv0.pack(side=LEFT, fill=Y, padx=2)
            self.folderframe.pack(side=LEFT, anchor='n')
            self.separatorv1.pack(side=LEFT, fill=Y, padx=2)
            self.prefsframe.pack(side=LEFT, anchor='n')
            self.separatorv2.pack(side=LEFT, fill=Y, padx=2)
            self.ediframe.pack(side=LEFT, anchor='n')

            return self.active_checkbutton_object  # initial focus

        def ok(self, event=None):

            if not self.validate():
                self.initial_focus.focus_set()  # put focus back
                return

            self.withdraw()
            self.update_idletasks()

            self.apply(self.foldersnameinput)

            self.cancel()

        def apply(self, apply_to_folder):
            doingstuffoverlay.make_overlay(self, "Applying Changes...")
            global copy_to_directory
            global destination_directory_is_altered
            apply_to_folder['folder_is_active'] = str(self.active_checkbutton.get())
            if self.foldersnameinput['folder_name'] != 'template':
                if str(self.folder_alias_field.get()) == '':
                    apply_to_folder['alias'] = os.path.basename(self.foldersnameinput['folder_name'])
                else:
                    apply_to_folder['alias'] = str(self.folder_alias_field.get())
            apply_to_folder['copy_to_directory'] = copy_to_directory
            apply_to_folder['process_backend_copy'] = self.process_backend_copy_check.get()
            apply_to_folder['process_backend_ftp'] = self.process_backend_ftp_check.get()
            apply_to_folder['process_backend_email'] = self.process_backend_email_check.get()
            apply_to_folder['ftp_server'] = str(self.ftp_server_field.get())
            apply_to_folder['ftp_port'] = int(self.ftp_port_field.get())
            apply_to_folder['ftp_folder'] = str(self.ftp_folder_field.get())
            apply_to_folder['ftp_username'] = str(self.ftp_username_field.get())
            apply_to_folder['ftp_password'] = str(self.ftp_password_field.get())
            apply_to_folder['email_to'] = str(self.email_recepient_field.get())
            apply_to_folder['email_subject_line'] = str(self.email_sender_subject_field.get())
            apply_to_folder['process_edi'] = str(self.process_edi.get())
            apply_to_folder['convert_to_format'] = str(self.convert_formats_var.get())
            apply_to_folder['calculate_upc_check_digit'] = str(self.upc_var_check.get())
            apply_to_folder['include_a_records'] = str(self.a_rec_var_check.get())
            apply_to_folder['include_c_records'] = str(self.c_rec_var_check.get())
            apply_to_folder['include_headers'] = str(self.headers_check.get())
            apply_to_folder['filter_ampersand'] = str(self.ampersand_check.get())
            apply_to_folder['force_edi_validation'] = self.force_edi_check_var.get()
            apply_to_folder['tweak_edi'] = self.tweak_edi.get()
            apply_to_folder['split_edi'] = self.split_edi.get()
            apply_to_folder['pad_a_records'] = str(self.pad_arec_check.get())
            apply_to_folder['a_record_padding'] = str(self.a_record_padding_field.get())
            apply_to_folder['append_a_records'] = str(self.append_arec_check.get())
            apply_to_folder['a_record_append_text'] = str(self.a_record_append_field.get())
            apply_to_folder['force_txt_file_ext'] = str(self.force_txt_file_ext_check.get())
            apply_to_folder['invoice_date_offset'] = int(self.invoice_date_offset.get())

            if self.foldersnameinput['folder_name'] != 'template':
                update_folder_alias(apply_to_folder)
            else:
                update_reporting(apply_to_folder)
            set_main_button_states()
            doingstuffoverlay.destroy_overlay()

        def validate(self):

            error_string_constructor_list = []
            errors = False

            doingstuffoverlay.make_overlay(self, "Testing Changes...")
            backend_count = 0
            if self.process_backend_ftp_check.get() ==True:

                backend_count += 1

                ftp_errors = False

                if self.ftp_server_field.get() == "":
                    error_string_constructor_list.append("FTP Server Field is Required\r\n")
                    errors = True
                    ftp_errors = True

                if self.ftp_port_field.get() == "":
                    error_string_constructor_list.append("FTP Port Field is Required\r\n")
                    errors = True
                    ftp_errors = True

                if self.ftp_folder_field.get() == "":
                    error_string_constructor_list.append("FTP Folder Field is Required\r\n")
                    errors = True
                    ftp_errors = True
                else:
                    if self.ftp_folder_field.get()[-1] != "/":
                        error_string_constructor_list.append("FTP Folder Path Needs To End In /\r\n")
                        errors = True
                        ftp_errors = True

                if self.ftp_username_field.get() == "":
                    error_string_constructor_list.append("FTP Username Field is Required\r\n")
                    errors = True
                    ftp_errors = True

                if self.ftp_password_field.get() == "":
                    error_string_constructor_list.append("FTP Password Field is Required\r\n")
                    errors = True
                    ftp_errors = True

                try:
                    _ = int(self.ftp_port_field.get())
                except ValueError:
                    error_string_constructor_list.append("FTP Port Field Needs To Be A Number\r\n")
                    errors = True
                    ftp_errors = True

                if not ftp_errors:
                    ftp = ftplib.FTP()

                    try:
                        ftp.connect(str(self.ftp_server_field.get()), int(self.ftp_port_field.get()))
                        try:
                            ftp.login(self.ftp_username_field.get(), self.ftp_password_field.get())
                            try:
                                ftp.cwd(self.ftp_folder_field.get())
                            except Exception as ftp_error:
                                print("cwd")
                                print(ftp_error)
                                error_string_constructor_list.append("FTP Folder Field Incorrect\r\n")
                                errors = True
                        except Exception as ftp_error:
                            print("username/password")
                            print(ftp_error)
                            error_string_constructor_list.append("FTP Username or Password Incorrect\r\n")
                            errors = True
                        ftp.close()
                    except Exception as ftp_error:
                        print("server/port")
                        print(ftp_error)
                        error_string_constructor_list.append("FTP Server or Port Field Incorrect\r\n")
                        errors = True

            if self.process_backend_email_check.get() ==True:

                backend_count += 1

                if self.email_recepient_field.get() == "":
                    error_string_constructor_list.append("Email Destination Address Field is Required\r\n")
                    errors = True
                else:
                    email_recepients = str(self.email_recepient_field.get()).split(", ")
                    for email_recepient in email_recepients:
                        if (validate_email(str(email_recepient), verify=True)) ==False:
                            error_string_constructor_list.append("Invalid Email Destination Address\r\n")
                            errors = True

            if self.process_backend_copy_check.get() ==True:

                backend_count += 1

                if copy_to_directory ==None or copy_to_directory == "":
                    error_string_constructor_list.append("Copy Backend Destination is currently Unset,"
                                                         " Please Select One\r\n")
                    errors = True

            if backend_count ==0 and self.active_checkbutton.get() == "True":
                error_string_constructor_list.append("No Backend is Selected")
                errors = True

            if not str(self.pad_arec_check.get()) == "True" and self.convert_formats_var.get() == 'ScannerWare':
                error_string_constructor_list.append('"A" Record Padding Needs To Be Enabled For ScannerWare Backend')
                errors = True

            if len(str(self.a_record_padding_field.get())) != 6 and str(self.pad_arec_check.get()) == "True":
                error_string_constructor_list.append('"A" Record Padding Needs To Be Six Characters\r\n')
                errors = True

            if len(str(self.a_record_append_field.get())) != 6 and str(self.append_arec_check.get()) == "True":
                error_string_constructor_list.append('"A" Record Append Field Needs To Be Six Characters\r\n')
                errors = True

            if int(self.invoice_date_offset.get()) not in [i for i in range(-14,15)]:
                error_string_constructor_list.append("Invoice date offset not in valid range")
                errors = True

            if self.foldersnameinput['folder_name'] != 'template':
                if str(self.folder_alias_field.get()) != self.foldersnameinput['alias']:
                    proposed_folder = folders_table.find_one(alias=str(self.folder_alias_field.get()))
                    if proposed_folder != None:
                        error_string_constructor_list.append("Folder Alias Already In Use\r\n")
                        errors = True

                if len(self.folder_alias_field.get()) > 50:
                    error_string_constructor_list.append("Alias Too Long\r\n")
                    errors = True
            if errors ==True:
                doingstuffoverlay.destroy_overlay()
                error_string = ''.join(error_string_constructor_list)  # combine error messages into single string
                showerror(parent=self, message=error_string)  # display generated error in dialog box
                return False

            doingstuffoverlay.destroy_overlay()
            return 1


    def update_reporting(changes):
        # push new settings into table
        oversight_and_defaults.update(changes, ['id'])


    def update_folder_alias(folder_edit):  # update folder settings in database with results from EditDialog
        folders_table.update(folder_edit, ['id'])
        refresh_users_list()


    def refresh_users_list():
        users_list_frame.destroy()  # destroy old users list
        make_users_list()  # create new users list
        users_list_frame.pack(side=RIGHT, fill=BOTH, expand=1)  # repack new users list
        set_main_button_states()


    def delete_folder_entry(folder_to_be_removed):
        # delete specified folder configuration and it's queued emails and obe queue
        folders_table.delete(id=folder_to_be_removed)
        processed_files.delete(folder_id=folder_to_be_removed)
        emails_table.delete(folder_id=folder_to_be_removed)


    def delete_folder_entry_wrapper(folder_to_be_removed, alias):
        # a wrapper function to both delete the folder entry and update the users list.
        if askyesno(message="Are you sure you want to remove the folder " + alias + "?"):
            delete_folder_entry(folder_to_be_removed)
            refresh_users_list()
            set_main_button_states()


    def graphical_process_directories(folders_table_process):  # process folders while showing progress overlay
        missing_folder = False
        for folder_test in folders_table_process.find(folder_is_active="True"):
            if not os.path.exists(folder_test['folder_name']):
                missing_folder = True
        if missing_folder ==True:
            showerror(parent=root, title="Error", text="One or more expected folders are missing.")
        else:
            if folders_table_process.count(folder_is_active="True") > 0:
                doingstuffoverlay.make_overlay(parent=root, overlay_text="processing folders...")
                process_directories(folders_table_process)
                refresh_users_list()  # refresh the users list in case the active state has changed
                set_main_button_states()
                doingstuffoverlay.destroy_overlay()
            else:
                showerror(parent=root, title="Error", text="No Active Folders")


    def set_defaults_popup():
        defaults = oversight_and_defaults.find_one(id=1)
        EditDialog(root, defaults)


    def process_directories(folders_table_process):
        original_folder = os.getcwd()
        global emails_table
        settings_dict = settings.find_one(id=1)
        if settings_dict['enable_interval_backups'] and settings_dict['backup_counter'] >= \
                settings_dict['backup_counter_maximum']:
            backup_increment.do_backup(database_path)
            settings_dict['backup_counter'] = 0
        settings_dict['backup_counter'] += 1
        settings.update(settings_dict, ['id'])
        log_folder_creation_error = False
        start_time = str(datetime.datetime.now())
        reporting = oversight_and_defaults.find_one(id=1)
        run_log_name_constructor = "Run Log " + str(time.ctime()).replace(":", "-") + ".txt"
        # check for configured logs directory, and create it if necessary
        if not os.path.isdir(logs_directory['logs_directory']):
            try:
                os.mkdir(logs_directory['logs_directory'])
            except IOError:
                log_folder_creation_error = True
        if check_logs_directory() ==False or log_folder_creation_error ==True:
            if args.automatic ==False:
                # offer to make new log directory
                while check_logs_directory() ==False:  # don't let user out unless they pick a writable folder, or cancel
                    if askokcancel("Error", "Can't write to log directory,\r\n"
                                            " would you like to change reporting settings?"):
                        EditSettingsDialog(root, oversight_and_defaults.find_one(id=1))
                    else:
                        # the logs must flow. aka, stop here if user declines selecting a new writable log folder
                        showerror(parent=root, message="Can't write to log directory, exiting")
                        raise SystemExit
            else:
                try:
                    # can't prompt for new logs directory, can only complain in a critical log and quit
                    print("can't write into logs directory. in automatic mode,"
                          " so no prompt. this error will be stored in critical log")
                    process_folders_critical_log = open("critical_error.log", 'a')
                    process_folders_critical_log.write(str(datetime.datetime.now()) +
                                                       "can't write into logs directory."
                                                       " in automatic mode, so no prompt\r\n")
                    process_folders_critical_log.close()
                    raise SystemExit
                except IOError:
                    # can't complain in a critical log, so ill complain in standard output and quit
                    print("Can't write critical error log, aborting")
                    raise SystemExit
        run_log_path = reporting['logs_directory']
        run_log_path = str(run_log_path)  # convert possible unicode path to standard python string to fix weird path bugs
        run_log_full_path = os.path.join(run_log_path, run_log_name_constructor)

        run_summary_string = ""

        with open(run_log_full_path, 'wb') as run_log:
            clear_old_files.do_clear(run_log_path, 1000)
            run_log.write(("Batch File Sender Version " + version + "\r\n").encode())
            run_log.write(("starting run at " + time.ctime() + "\r\n").encode())
            if reporting['enable_reporting'] == "True":
                # add run log to email queue if reporting is enabled
                emails_table.insert(dict(log=run_log_full_path, folder_alias=run_log_name_constructor))
            # call dispatch module to process active folders
            try:
                run_error_bool, run_summary_string = dispatch.process(database_connection, folders_table_process, run_log,
                                                                      emails_table, reporting['logs_directory'], reporting,
                                                                      processed_files, root, args, version,
                                                                      errors_directory, edi_converter_scratch_folder,
                                                                      settings_dict,
                                                                      simple_output=None if not args.automatic else
                                                                      feedback_text)
                if run_error_bool ==True and not args.automatic:
                    showinfo(parent=root, title="Run Status", message="Run completed with errors.")
                os.chdir(original_folder)
            except Exception as dispatch_error:
                os.chdir(original_folder)
                # if processing folders runs into a serious error, report and log
                print("Run failed, check your configuration \r\nError from dispatch module is: \r\n" +
                      str(dispatch_error) + "\r\n")
                run_log.write(("Run failed, check your configuration \r\nError from dispatch module is: \r\n" +
                               str(dispatch_error) + "\r\n").encode())
            run_log.close()
        if reporting['enable_reporting'] == "True":
            try:
                sent_emails_removal_queue.delete()
                total_size = 0
                skipped_files = 0
                email_errors = StringIO()
                total_emails = emails_table.count()
                emails_table_batch.delete()
                emails_count = 0
                loop_count = 0
                batch_number = 1

                for log in emails_table.all():
                    emails_count += 1
                    loop_count += 1
                    if os.path.isfile(os.path.abspath(log['log'])):
                        send_log_file = copy.deepcopy(log)
                        if os.path.getsize(os.path.abspath(log['log'])) > 9000000:
                            send_log_file['log'] = str(os.path.abspath(log['log']) + ".zip")
                            with zipfile.ZipFile(send_log_file['log'], 'w') as zip:
                                zip.write(os.path.abspath(log['log']), os.path.basename(log['log']), zipfile.ZIP_DEFLATED)
                        # iterate over emails to send queue, breaking it into 9mb chunks if necessary
                        # add size of current file to total
                        total_size += os.path.getsize(os.path.abspath(send_log_file['log']))
                        emails_table_batch.insert(dict(log=send_log_file['log']))
                        # if the total size is more than 9mb, then send that set and reset the total
                        if total_size > 9000000 or emails_table_batch.count() >= 15:
                            batch_log_sender.do(settings_dict, reporting, emails_table_batch, sent_emails_removal_queue,
                                                start_time, args, root, batch_number, emails_count, total_emails,
                                                feedback_text, run_summary_string)
                            emails_table_batch.delete()  # clear batch
                            total_size = 0
                            loop_count = 0
                            batch_number += 1
                    else:
                        email_errors.write("\r\n" + log['log'] + " missing, skipping")
                        email_errors.write("\r\n file was expected to be at " + log['log'] + " on the sending computer")
                        skipped_files += 1
                        sent_emails_removal_queue.insert(log)
                batch_log_sender.do(settings_dict, reporting, emails_table_batch, sent_emails_removal_queue,
                                    start_time, args, root, batch_number, emails_count, total_emails, feedback_text,
                                    run_summary_string)
                emails_table_batch.delete()  # clear batch
                for line in sent_emails_removal_queue.all():
                    emails_table.delete(log=str(line['log']))
                sent_emails_removal_queue.delete()
                if skipped_files > 0:  # log any skipped files, try to send that error in the run log
                    batch_number += 1
                    emails_count += 1
                    email_errors.write("\r\n\r\n" + str(skipped_files) + " emails skipped")
                    email_errors_log_name_constructor = "Email Errors Log " + str(time.ctime()).replace(":", "-") + ".txt"
                    email_errors_log_full_path = os.path.join(run_log_path, email_errors_log_name_constructor)
                    reporting_emails_errors = open(email_errors_log_full_path, 'w')
                    reporting_emails_errors.write(email_errors.getvalue())
                    reporting_emails_errors.close()
                    emails_table_batch.insert(dict(log=email_errors_log_full_path,
                                                   folder_alias=email_errors_log_name_constructor))
                    try:
                        batch_log_sender.do(settings_dict, reporting, emails_table_batch, sent_emails_removal_queue,
                                            start_time, args, root, batch_number, emails_count, total_emails, feedback_text,
                                            "Error, cannot send all logs. ")
                        emails_table_batch.delete()
                    except Exception as email_send_error:
                        print(email_send_error)
                        doingstuffoverlay.destroy_overlay()
                        emails_table_batch.delete()
            except Exception as dispatch_error:
                emails_table_batch.delete()
                run_log = open(run_log_full_path, 'a')
                if reporting['report_printing_fallback'] == "True":
                    print("Emailing report log failed with error: " + str(dispatch_error) + ", printing file\r\n")
                    run_log.write("Emailing report log failed with error: " + str(dispatch_error) + ", printing file\r\n")
                else:
                    print("Emailing report log failed with error: " + str(
                        dispatch_error) + ", printing disabled, stopping\r\n")
                    run_log.write("Emailing report log failed with error: " + str(
                        dispatch_error) + ", printing disabled, stopping\r\n")
                run_log.close()
                if reporting['report_printing_fallback'] == "True":
                    # if for some reason emailing logs fails, and printing fallback is enabled, print the run log
                    try:
                        run_log = open(run_log_full_path, 'r')
                        print_run_log.do(run_log)
                        run_log.close()
                    except Exception as dispatch_error:
                        print("printing error log failed with error: " + str(dispatch_error) + "\r\n")
                        run_log = open(run_log_full_path, 'a')
                        run_log.write("Printing error log failed with error: " + str(dispatch_error) + "\r\n")
                        run_log.close()


    def automatic_process_directories(automatic_process_folders_table):
        if automatic_process_folders_table.count(folder_is_active="True") > 0:
            print("batch processing configured directories")
            try:
                Label(root, text="Running In Automatic Mode...").pack(side=TOP)
                root.minsize(400, root.winfo_height())
                root.update()
                process_directories(automatic_process_folders_table)
            except Exception as automatic_process_error:
                print(str(automatic_process_error))
                automatic_process_critical_log = open("critical_error.log", 'a')
                automatic_process_critical_log.write(str(automatic_process_error) + "\r\n")
                automatic_process_critical_log.close()
        else:
            print("Error, No Active Folders")
        raise SystemExit


    def remove_inactive_folders():  # loop over folders and safely remove ones marked as inactive
        maintenance_popup.unbind("<Escape>")
        users_refresh = False
        if folders_table.count(folder_is_active="False") > 0:
            users_refresh = True
        folders_total = folders_table.count(folder_is_active="False")
        folders_count = 0
        doingstuffoverlay.make_overlay(maintenance_popup, "removing " + str(folders_count) + " of " + str(folders_total))
        for folder_to_be_removed in folders_table.find(folder_is_active="False"):
            folders_count += 1
            doingstuffoverlay.update_overlay(maintenance_popup, "removing " + str(folders_count) + " of " +
                                             str(folders_total))
            delete_folder_entry(folder_to_be_removed['id'])
        doingstuffoverlay.destroy_overlay()
        if users_refresh:
            refresh_users_list()
        maintenance_popup.bind("<Escape>", destroy_maintenance_popup)


    def mark_active_as_processed(master, selected_folder=None):
        if selected_folder ==None:
            maintenance_popup.unbind("<Escape>")
        starting_folder = os.getcwd()
        folder_count = 0
        folders_table_list = []
        if selected_folder ==None:
            for row in folders_table.find(folder_is_active="True"):
                folders_table_list.append(row)
        else:
            folders_table_list = [folders_table.find_one(id=selected_folder)]
        folder_total = len(folders_table_list)
        if selected_folder ==None:
            doingstuffoverlay.make_overlay(master, "adding files to processed list...")
        for parameters_dict in folders_table_list:  # create list of active directories
            file_total = 0
            file_count = 0
            folder_count += 1
            doingstuffoverlay.update_overlay(parent=master,
                                             overlay_text="adding files to processed list...\n\n" + " folder " +
                                                          str(folder_count) + " of " + str(folder_total) + " file " +
                                                          str(file_count) + " of " + str(file_total))
            os.chdir(os.path.abspath(parameters_dict['folder_name']))
            files = [f for f in os.listdir('.') if os.path.isfile(f)]
            # create list of all files in directory
            file_total = len(files)
            filtered_files = []
            for f in files:
                file_count += 1
                doingstuffoverlay.update_overlay(parent=master,
                                                 overlay_text="checking files for already processed\n\n" +
                                                              str(folder_count) + " of " + str(folder_total) + " file " +
                                                              str(file_count) + " of " + str(file_total))
                if processed_files.find_one(file_name=os.path.join(os.getcwd(), f), file_checksum=hashlib.md5(
                        open(f, 'rb').read()).hexdigest()) ==None:
                    filtered_files.append(f)
            file_total = len(filtered_files)
            file_count = 0
            for filename in filtered_files:
                print(filename)
                file_count += 1
                doingstuffoverlay.update_overlay(parent=master,
                                                 overlay_text="adding files to processed list...\n\n" + " folder " +
                                                              str(folder_count) + " of " + str(folder_total) +
                                                              " file " + str(file_count) + " of " + str(file_total))
                processed_files.insert(dict(file_name=str(os.path.abspath(filename)),
                                            file_checksum=hashlib.md5
                                            (open(filename, 'rb').read()).hexdigest(),
                                            folder_id=parameters_dict['id'],
                                            folder_alias=parameters_dict['alias'],
                                            copy_destination="N/A",
                                            ftp_destination="N/A",
                                            email_destination="N/A",
                                            sent_date_time=datetime.datetime.now(),
                                            resend_flag=False))
        doingstuffoverlay.destroy_overlay()
        os.chdir(starting_folder)
        set_main_button_states()
        if selected_folder ==None:
            maintenance_popup.bind("<Escape>", destroy_maintenance_popup)


    def set_all_inactive():
        maintenance_popup.unbind("<Escape>")
        doingstuffoverlay.make_overlay(maintenance_popup, "Working...")
        maintenance_popup.update()
        database_connection.query('update folders set folder_is_active="False" where folder_is_active="True"')
        refresh_users_list()
        doingstuffoverlay.destroy_overlay()
        maintenance_popup.update()
        maintenance_popup.bind("<Escape>", destroy_maintenance_popup)


    def set_all_active():
        maintenance_popup.unbind("<Escape>")
        doingstuffoverlay.make_overlay(maintenance_popup, "Working...")
        maintenance_popup.update()
        database_connection.query('update folders set folder_is_active="True" where folder_is_active="False"')
        refresh_users_list()
        doingstuffoverlay.destroy_overlay()
        maintenance_popup.update()
        maintenance_popup.bind("<Escape>", destroy_maintenance_popup)


    def clear_resend_flags():
        maintenance_popup.unbind("<Escape>")
        doingstuffoverlay.make_overlay(maintenance_popup, "Working...")
        maintenance_popup.update()
        database_connection.query('update processed_files set resend_flag=0 where resend_flag=1')
        doingstuffoverlay.destroy_overlay()
        maintenance_popup.update()
        maintenance_popup.bind("<Escape>", destroy_maintenance_popup)


    def clear_processed_files_log():
        if askokcancel(message="This will clear all records of sent files.\nAre you sure?"):
            maintenance_popup.unbind("<Escape>")
            processed_files.delete()
            set_main_button_states()
            maintenance_popup.bind("<Escape>", destroy_maintenance_popup)


    def destroy_maintenance_popup(_=None):
        maintenance_popup.destroy()


    def database_import_wrapper(backup_path):
        if database_import.import_interface(maintenance_popup, database_path,
                                            running_platform, backup_path, database_version):
            maintenance_popup.unbind("<Escape>")
            doingstuffoverlay.make_overlay(maintenance_popup, "Working...")
            connect_to_databases()
            open_tables()
            settings_dict = settings.find_one(id=1)
            print(settings_dict['enable_email'])
            if not settings_dict['enable_email']:
                for email_backend_to_disable in folders_table.find(process_backend_email=True):
                    email_backend_to_disable['process_backend_email'] = False
                    folders_table.update(email_backend_to_disable, ['id'])
                for folder_to_disable in folders_table.find(process_backend_email=False, process_backend_ftp=False,
                                                            process_backend_copy=False, folder_is_active="True"):
                    folder_to_disable['folder_is_active'] = "False"
                    folders_table.update(folder_to_disable, ['id'])
            refresh_users_list()
            doingstuffoverlay.destroy_overlay()
        maintenance_popup.bind("<Escape>", destroy_maintenance_popup)
        maintenance_popup.grab_set()
        maintenance_popup.focus_set()


    def maintenance_functions_popup():
        # first, warn the user that they can do very bad things with this dialog, and give them a chance to go back
        if askokcancel(message="Maintenance window is for advanced users only, potential for data loss if incorrectly used."
                               " Are you sure you want to continue?"):
            backup_path = backup_increment.do_backup(database_path)
            global maintenance_popup
            maintenance_popup = Toplevel()
            maintenance_popup.title("Maintenance Functions")
            maintenance_popup.transient(root)
            # center dialog on main window
            maintenance_popup.geometry("+%d+%d" % (root.winfo_rootx() + 50, root.winfo_rooty() + 50))
            maintenance_popup.grab_set()
            maintenance_popup.focus_set()
            maintenance_popup.resizable(width=FALSE, height=FALSE)
            maintenance_popup_button_frame = Frame(maintenance_popup)
            # a persistent warning that this dialog can break things...
            maintenance_popup_warning_label = Label(maintenance_popup, text="WARNING:\nFOR\nADVANCED\nUSERS\nONLY!")
            set_all_active_button = Button(maintenance_popup_button_frame,
                                           text="Move all to active (Skips Settings Validation)",
                                           command=set_all_active)
            set_all_inactive_button = Button(maintenance_popup_button_frame, text="Move all to inactive",
                                             command=set_all_inactive)
            clear_resend_flags_button = Button(maintenance_popup_button_frame, text="Clear all resend flags",
                                               command=clear_resend_flags)
            clear_emails_queue = Button(maintenance_popup_button_frame, text="Clear queued emails",
                                        command=emails_table.delete)
            move_active_to_obe_button = Button(maintenance_popup_button_frame, text="Mark all in active as processed",
                                               command=lambda: mark_active_as_processed(maintenance_popup))
            remove_all_inactive = Button(maintenance_popup_button_frame, text="Remove all inactive configurations",
                                         command=remove_inactive_folders)
            clear_processed_files_log_button = Button(maintenance_popup_button_frame, text="Clear sent file records",
                                                      command=clear_processed_files_log)
            database_import_button = Button(maintenance_popup_button_frame, text="Import old configurations...",
                                            command=lambda: database_import_wrapper(backup_path))

            # pack widgets into dialog
            set_all_active_button.pack(side=TOP, fill=X, padx=2, pady=2)
            set_all_inactive_button.pack(side=TOP, fill=X, padx=2, pady=2)
            clear_resend_flags_button.pack(side=TOP, fill=X, padx=2, pady=2)
            clear_emails_queue.pack(side=TOP, fill=X, padx=2, pady=2)
            move_active_to_obe_button.pack(side=TOP, fill=X, padx=2, pady=2)
            remove_all_inactive.pack(side=TOP, fill=X, padx=2, pady=2)
            clear_processed_files_log_button.pack(side=TOP, fill=X, padx=2, pady=2)
            database_import_button.pack(side=TOP, fill=X, padx=2, pady=2)
            maintenance_popup_button_frame.pack(side=LEFT)
            maintenance_popup_warning_label.pack(side=RIGHT, padx=20)
            maintenance_popup.bind("<Escape>", destroy_maintenance_popup)


    def export_processed_report(name, output_folder):
        def avoid_overwrite(input_file_name):
            counter = 2
            if not os.path.exists(input_file_name + ".csv"):
                return input_file_name + ".csv"
            else:
                while os.path.exists(input_file_name + " " + str(counter) + ".csv"):
                    counter += 1
                clear_file_path = input_file_name + " " + str(counter) + ".csv"
                return clear_file_path

        folder_alias = folders_table.find_one(id=name)
        processed_log_path = avoid_overwrite(str(os.path.join(output_folder, folder_alias['alias'] + " processed report")))
        processed_log = open(processed_log_path, 'w')
        processed_log.write("File,Date,Copy Destination,FTP Destination,Email Destination\n")
        for line in processed_files.find(folder_id=name):
            processed_log.write(
                line['file_name'] + "," + "\t" + str(line['sent_date_time'])[:-7] + "," + line['copy_destination'] +
                "," + line['ftp_destination'] + "," + str(line['email_destination']).replace(",", ";") + "\n")
        processed_log.close()
        showinfo(message="Processed File Report Exported To\n\n" + processed_log_path)


    def processed_files_popup():
        def close_processed_files_popup(_=None):
            processed_files_popup_dialog.destroy()
            return

        def folder_button_pressed(name):
            global export_button
            global processed_files_output_folder
            global output_folder_is_confirmed
            for child in processed_files_popup_actions_frame.winfo_children():
                child.destroy()
            Button(processed_files_popup_actions_frame, text='Choose output Folder',
                   command=set_output_folder).pack(pady=10)
            export_button = Button(processed_files_popup_actions_frame, text='Export Processed Report',
                                   command=lambda: export_processed_report(name, processed_files_output_folder))
            if output_folder_is_confirmed ==False:
                export_button.configure(state=DISABLED)
            else:
                export_button.configure(state=NORMAL)
            export_button.pack(pady=10)

        def set_output_folder():
            global output_folder_is_confirmed
            global processed_files_output_folder
            set_output_prior_folder = oversight_and_defaults.find_one(id=1)
            if os.path.exists(set_output_prior_folder['export_processed_folder_prior']):
                initial_directory = set_output_prior_folder['export_processed_folder_prior']
            else:
                initial_directory = os.path.expanduser('~')
            output_folder_proposed = askdirectory(parent=processed_files_popup_actions_frame, initialdir=initial_directory)
            if output_folder_proposed == "":
                return
            else:
                output_folder = output_folder_proposed
            update_last_folder = dict(id=1, export_processed_folder_prior=output_folder)
            oversight_and_defaults.update(update_last_folder, ['id'])
            output_folder_is_confirmed = True
            processed_files_output_folder = output_folder
            if output_folder_is_confirmed ==False:
                export_button.configure(state=DISABLED)
            else:
                export_button.configure(state=NORMAL)

        global processed_files_output_folder
        global output_folder_is_confirmed
        folder_button_variable = IntVar()
        output_folder_is_confirmed = False
        prior_folder = oversight_and_defaults.find_one(id=1)
        processed_files_output_folder = prior_folder['export_processed_folder_prior']
        processed_files_popup_dialog = Toplevel()
        processed_files_popup_dialog.title("Processed Files Report")
        processed_files_popup_dialog.transient(root)
        # center dialog on main window
        processed_files_popup_dialog.geometry("+%d+%d" % (root.winfo_rootx() + 50, root.winfo_rooty() + 50))
        processed_files_popup_dialog.grab_set()
        processed_files_popup_dialog.focus_set()
        processed_files_popup_dialog.resizable(width=FALSE, height=FALSE)
        processed_files_popup_body_frame = Frame(processed_files_popup_dialog)
        processed_files_popup_list_container = Frame(processed_files_popup_body_frame)
        processed_files_popup_list_frame = scrollbuttons.VerticalScrolledFrame(processed_files_popup_list_container)
        processed_files_popup_close_frame = Frame(processed_files_popup_dialog)
        processed_files_popup_actions_frame = Frame(processed_files_popup_body_frame)
        processed_files_loading_label = Label(master=processed_files_popup_dialog, text="Loading...")
        processed_files_loading_label.pack()
        root.update()
        Label(processed_files_popup_actions_frame, text="Select a Folder.").pack(padx=10)
        if processed_files.count() == 0:
            no_processed_label = Label(processed_files_popup_list_frame, text="No Folders With Processed Files")
            no_processed_label.pack(fill=BOTH, expand=1, padx=10)
        processed_files_distinct_list = []
        for row in processed_files.distinct('folder_id'):
            processed_files_distinct_list.append(row['folder_id'])
        folder_entry_tuple_list = []
        for entry in processed_files_distinct_list:
            folder_dict = folders_table.find_one(id=str(entry))
            folder_alias = folder_dict['alias']
            folder_entry_tuple_list.append([entry, folder_alias])
        sorted_folder_list = sorted(folder_entry_tuple_list, key=itemgetter(1))

        for folders_name, folder_alias in sorted_folder_list:
            folder_row = processed_files.find_one(folder_id=str(folders_name))
            tkinter.Radiobutton(processed_files_popup_list_frame.interior, text=folder_alias.center(15),
                                variable=folder_button_variable,
                                value=folder_alias, indicatoron=FALSE,
                                command=lambda name=folder_row['folder_id']:
                                folder_button_pressed(name)).pack(anchor='w', fill='x')
        close_button = Button(processed_files_popup_close_frame, text="Close", command=close_processed_files_popup)
        close_button.pack(pady=5)
        processed_files_popup_dialog.bind("<Escape>", close_processed_files_popup)
        processed_files_loading_label.destroy()
        processed_files_popup_list_container.pack(side=LEFT)
        processed_files_popup_list_frame.pack()
        processed_files_popup_actions_frame.pack(side=RIGHT, anchor=N, padx=5)
        processed_files_popup_body_frame.pack()
        Separator(master=processed_files_popup_dialog, orient=HORIZONTAL).pack(fill='x')
        processed_files_popup_close_frame.pack()


    def set_main_button_states():
        if folders_table.count() == 0:
            process_folder_button.configure(state=DISABLED)
        else:
            if folders_table.count(folder_is_active="True") > 0:
                process_folder_button.configure(state=NORMAL)
            else:
                process_folder_button.configure(state=DISABLED)
        if processed_files.count() > 0:
            processed_files_button.configure(state=NORMAL)
            allow_resend_button.configure(state=NORMAL)
        else:
            processed_files_button.configure(state=DISABLED)
            allow_resend_button.configure(state=DISABLED)


    launch_options.add_argument('-a', '--automatic', action='store_true')
    args = launch_options.parse_args()
    if args.automatic:
        automatic_process_directories(folders_table)

    make_users_list()

    # define main window widgets
    open_folder_button = Button(options_frame, text="Add Directory...", command=select_folder)
    open_multiple_folder_button = Button(options_frame, text="Batch Add Directories...", command=batch_add_folders)
    default_settings = Button(options_frame, text="Set Defaults...", command=set_defaults_popup)
    edit_reporting = Button(options_frame, text="Edit Settings...",
                            command=lambda: EditSettingsDialog(root, oversight_and_defaults.find_one(id=1)))
    process_folder_button = Button(options_frame, text="Process All Folders",
                                   command=lambda: graphical_process_directories(folders_table))

    allow_resend_button = Button(options_frame, text="Enable Resend...",
                                 command=lambda: resend_interface.do(database_connection, root))

    maintenance_button = Button(options_frame, text="Maintenance...", command=maintenance_functions_popup)
    processed_files_button = Button(options_frame, text="Processed Files Report...", command=processed_files_popup)
    options_frame_divider = Separator(root, orient=VERTICAL)

    set_main_button_states()

    # pack main window widgets
    open_folder_button.pack(side=TOP, fill=X, pady=2, padx=2)
    open_multiple_folder_button.pack(side=TOP, fill=X, pady=2, padx=2)
    default_settings.pack(side=TOP, fill=X, pady=2, padx=2)
    edit_reporting.pack(side=TOP, fill=X, pady=2, padx=2)
    process_folder_button.pack(side=BOTTOM, fill=X, pady=2, padx=2)
    Separator(options_frame, orient=HORIZONTAL).pack(fill='x', side=BOTTOM)
    maintenance_button.pack(side=TOP, fill=X, pady=2, padx=2)
    allow_resend_button.pack(side=BOTTOM, fill=X, pady=2, padx=2)
    Separator(options_frame, orient=HORIZONTAL).pack(fill='x', side=BOTTOM)
    processed_files_button.pack(side=TOP, fill=X, pady=2, padx=2)
    feedback_text.destroy()
    options_frame.pack(side=LEFT, anchor='n', fill=Y)
    options_frame_divider.pack(side=LEFT, fill=Y)

    # set parameters for root window

    # set window minimum size to prevent user making it ugly
    root.update()  # update window geometry
    # don't allow window to be resized smaller than current dimensions
    root.minsize(root.winfo_width(), root.winfo_height())
    root.resizable(width=FALSE, height=TRUE)

    root.mainloop()
