version = "1.10.7"
database_version = "9"
print("Batch File Sender Version " + version)
try:  # try to import required modules
    from Tkinter import *
    from tkFileDialog import askdirectory
    from tkMessageBox import showerror, askyesno, showinfo, askokcancel
    from ttk import *
    from validate_email import validate_email
    import Tkinter
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
    import sqlalchemy.dialects.sqlite  # needed for py2exe
    import cStringIO
    import shutil
    import doingstuffoverlay
    import folders_database_migrator
    import resend_interface
    from tendo import singleton
except Exception, error:
    try:  # if importing doesn't work, not much to do other than log and quit
        print(str(error))
        critical_log = open("critical_error.log", 'a')
        critical_log.write("program version is " + version)
        critical_log.write(str(error) + "\r\n")
        critical_log.close()
        raise SystemExit
    except Exception, big_error:  # if logging doesn't work, at least complain
        print("error writing critical error log for error: " + str(error) + "\n" +
              "operation failed with error: " + str(big_error))
        raise SystemExit

# prevent multiple instances from running
me = singleton.SingleInstance()

if not os.path.isfile('folders.db'):  # if the database file is missing
    try:
        print("creating initial database file...")
        creating_database_popup = Tk()
        Label(creating_database_popup, text="Creating initial database file...").pack()
        creating_database_popup.update()
        create_database.do(database_version)  # make a new one
        print("done")
        creating_database_popup.destroy()
    except Exception, error:  # if that doesn't work for some reason, log and quit
        try:
            print(str(error))
            critical_log = open("critical_error.log", 'a')
            critical_log.write("program version is " + version)
            critical_log.write(str(datetime.datetime.now()) + str(error) + "\r\n")
            critical_log.close()
            raise SystemExit
        except Exception, big_error:  # if logging doesn't work, at least complain
            print("error writing critical error log for error: " + str(error) + "\n" +
                  "operation failed with error: " + str(big_error))
            raise SystemExit

try:  # try to connect to database
    database_connection = dataset.connect('sqlite:///folders.db')  # connect to database
    session_database = dataset.connect("sqlite:///session.db")
except Exception, error:  # if that doesn't work for some reason, log and quit
    try:
        print(str(error))
        critical_log = open("critical_error.log", 'a')
        critical_log.write("program version is " + version)
        critical_log.write(str(datetime.datetime.now()) + str(error) + "\r\n")
        critical_log.close()
        raise SystemExit
    except Exception, big_error:  # if logging doesn't work, at least complain
        print("error writing critical error log for error: " + str(error) + "\n" + "operation failed with error: " +
              str(big_error))
        raise SystemExit

# open table required for database check in database
db_version = database_connection['version']
db_version_dict = db_version.find_one(id=1)
if db_version_dict['version'] < database_version:
    folders_database_migrator.upgrade_database(database_connection)
if db_version_dict['version'] > database_version:
    Tk().withdraw()
    showerror("Error", "Program version too old for database version,\r\n please install a more recent release.")
    raise SystemExit

# open required tables in database
folders_table = database_connection['folders']
emails_table = database_connection['emails_to_send']
emails_table_batch = database_connection['working_batch_emails_to_send']
sent_emails_removal_queue = database_connection['sent_emails_removal_queue']
oversight_and_defaults = database_connection['administrative']
processed_files = database_connection['processed_files']

launch_options = argparse.ArgumentParser()
root = Tk()  # create root window
root.title("Sender Interface " + version)
folder = NONE
options_frame = Frame(root)  # initialize left frame
logs_directory = oversight_and_defaults.find_one(id=1)
errors_directory = oversight_and_defaults.find_one(id=1)
edi_converter_scratch_folder = oversight_and_defaults.find_one(id=1)


def check_logs_directory():
    try:
        # check to see if log directory is writable
        test_log_file = open(os.path.join(logs_directory['logs_directory'], 'test_log_file'), 'w')
        test_log_file.close()
        os.remove(os.path.join(logs_directory['logs_directory'], 'test_log_file'))
    except IOError, log_directory_error:
        print(str(log_directory_error))
        return False


def add_folder_entry(proposed_folder):  # add folder to database, copying configuration from template
    defaults = oversight_and_defaults.find_one(id=1)
    folder_alias_constructor = os.path.basename(proposed_folder)

    def folder_alias_checker(check):
        # check database to see if the folder alias exists, and return false if it does
        add_folder_entry_proposed_folder = folders_table.find_one(alias=check)
        if add_folder_entry_proposed_folder is not None:
            return False

    if folder_alias_checker(folder_alias_constructor) is False:
        # auto generate a number to add to automatic aliases
        folder_alias_end_suffix = 0
        folder_alias_deduplicate_constructor = folder_alias_constructor
        while folder_alias_checker(folder_alias_deduplicate_constructor) is False:
            folder_alias_end_suffix += folder_alias_end_suffix + 1
            print str(folder_alias_end_suffix)
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
                              email_origin_address=defaults['email_origin_address'],
                              email_origin_username=defaults['email_origin_username'],
                              email_origin_password=defaults['email_origin_password'],
                              email_origin_smtp_server=defaults['email_origin_smtp_server'],
                              process_edi=defaults['process_edi'],
                              convert_to_format=defaults['convert_to_format'],
                              calculate_upc_check_digit=defaults['calculate_upc_check_digit'],
                              include_a_records=defaults['include_a_records'],
                              include_c_records=defaults['include_c_records'],
                              include_headers=defaults['include_headers'],
                              filter_ampersand=defaults['filter_ampersand'],
                              tweak_edi=defaults['tweak_edi'],
                              pad_a_records=defaults['pad_a_records'],
                              a_record_padding=defaults['a_record_padding'],
                              email_smtp_port=defaults['email_smtp_port'],
                              reporting_smtp_port=defaults['reporting_smtp_port'],
                              ftp_port=defaults['ftp_port'],
                              email_subject_line=defaults['email_subject_line']))
    print("done")


def check_folder_exists(folder):
    folder_list = folders_table.all()
    for possible_folder in folder_list:
        possible_folder_string = possible_folder['folder_name']
        if os.path.abspath(possible_folder_string) == os.path.abspath(folder):
            return {"truefalse": True, "matched_folder": possible_folder}
    return {"truefalse": False, "matched_folder": None}


def select_folder():
    global folder
    global column_entry_value
    prior_folder = oversight_and_defaults.find_one(id=1)
    if os.path.exists(prior_folder['single_add_folder_prior']):
        initial_directory = prior_folder['single_add_folder_prior']
    else:
        initial_directory = os.getcwd()
    folder = askdirectory(initialdir=initial_directory)
    if os.path.exists(folder):
        update_last_folder = dict(id=1, single_add_folder_prior=folder)
        oversight_and_defaults.update(update_last_folder, ['id'])
        proposed_folder = check_folder_exists(folder)

        if proposed_folder['truefalse'] is False:
            doingstuffoverlay.make_overlay(root, "Adding Folder...")
            column_entry_value = folder
            add_folder_entry(folder)
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
        initial_directory = os.getcwd()
    containing_folder = askdirectory(initialdir=initial_directory)
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
                doingstuffoverlay.destroy_overlay()
                folder_count += 1
                doingstuffoverlay.make_overlay(parent=root, overlay_text="adding folders... " + str(folder_count) +
                                                                         " of " + str(len(folders_list)))
                batch_folder_add_proposed_folder = os.path.join(containing_folder, batch_folder_add_proposed_folder)
                proposed_folder = check_folder_exists(batch_folder_add_proposed_folder)
                if proposed_folder['truefalse'] is False:
                    add_folder_entry(batch_folder_add_proposed_folder)
                    added += 1
                else:
                    print("skipping existing folder: " + batch_folder_add_proposed_folder)
                    skipped += 1
            print("done adding folders")
            doingstuffoverlay.destroy_overlay()
            refresh_users_list()
            showinfo(message=str(added) + " folders added, " + str(skipped) + " folders skipped.")


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
        single_table.insert(folders_table.find_one(id=folder_id))
        doingstuffoverlay.destroy_overlay()
        graphical_process_directories(single_table)
        single_table.drop()


def make_users_list():
    global users_list_frame
    global active_users_list_frame
    global inactive_users_list_frame
    users_list_frame = Frame(root)
    active_users_list_container = Frame(users_list_frame)
    inactive_users_list_container = Frame(users_list_frame)
    active_users_list_frame = scrollbuttons.VerticalScrolledFrame(active_users_list_container)
    inactive_users_list_frame = scrollbuttons.VerticalScrolledFrame(inactive_users_list_container)
    active_users_list_label = Label(active_users_list_container, text="Active Folders")  # active users title
    inactive_users_list_label = Label(inactive_users_list_container, text="Inactive Folders")  # inactive users title
    # make labels for empty lists
    if folders_table.count(folder_is_active="True") == 0:
        no_active_label = Label(active_users_list_frame, text="No Active Folders")
        no_active_label.pack(fill=BOTH, expand=1, padx=10)
    if folders_table.count(folder_is_active="False") == 0:
        no_inactive_label = Label(inactive_users_list_frame, text="No Inactive Folders")
        no_inactive_label.pack(fill=BOTH, expand=1, padx=10)
    # iterate over list of known folders, sorting into lists of active and inactive
    for folders_name in folders_table.all():
        if str(folders_name['folder_is_active']) != "False":
            active_folder_button_frame = Frame(active_users_list_frame.interior)
            Button(active_folder_button_frame, text="Delete",
                   command=lambda name=folders_name['id'], alias=folders_name['alias']:
                   delete_folder_entry_wrapper(name, alias)).grid(column=2, row=0, sticky=E)
            Button(active_folder_button_frame, text="Send",
                   command=lambda name=folders_name['id']: send_single(name)).grid(column=1, row=0)
            Button(active_folder_button_frame, text="Edit: " + folders_name['alias'],
                   command=lambda name=folders_name['id']:
                   edit_folder_selector(name)).grid(column=0, row=0, sticky=E + W)
            active_folder_button_frame.pack(anchor='e', pady=1)
        else:
            inactive_folder_button_frame = Frame(inactive_users_list_frame.interior)
            Button(inactive_folder_button_frame, text="Delete",
                   command=lambda name=folders_name['id'], alias=folders_name['alias']:
                   delete_folder_entry_wrapper(name, alias)).grid(column=1, row=0, sticky=E)
            Button(inactive_folder_button_frame, text="Edit: " + folders_name['alias'],
                   command=lambda name=folders_name['id']:
                   edit_folder_selector(name)).grid(column=0, row=0, sticky=E + W)
            inactive_folder_button_frame.pack(anchor='e', pady=1)
    # pack widgets in correct order
    active_users_list_label.pack(pady=5)
    Separator(active_users_list_container, orient=HORIZONTAL).pack(fill=X)
    inactive_users_list_label.pack(pady=5)
    Separator(inactive_users_list_container, orient=HORIZONTAL).pack(fill=X)
    active_users_list_frame.pack(fill=BOTH, expand=1, anchor=E, padx=3, pady=3)
    inactive_users_list_frame.pack(fill=BOTH, expand=1, anchor=E, padx=3, pady=3)
    active_users_list_container.pack(side=RIGHT, fill=Y, expand=1, anchor=E)
    inactive_users_list_container.pack(side=RIGHT, fill=Y, expand=1, anchor=E)
    users_list_frame.update()


class EditReportingDialog(dialog.Dialog):  # modal dialog for folder configuration.

    def body(self, master):

        self.resizable(width=FALSE, height=FALSE)
        self.logs_directory = self.foldersnameinput['logs_directory']
        self.title("Edit Reporting Options")
        self.enable_reporting_checkbutton_variable = StringVar(master)
        self.enable_report_printing_checkbutton_variable = StringVar(master)

        report_sending_options_frame = Frame(master)

        Label(report_sending_options_frame, text="Reporting Email Address:").grid(row=1, sticky=E)
        Label(report_sending_options_frame, text="Reporting Email Username:").grid(row=2, sticky=E)
        Label(report_sending_options_frame, text="Reporting Email Password:").grid(row=3, sticky=E)
        Label(report_sending_options_frame, text="Reporting Email SMTP Server:").grid(row=4, sticky=E)
        Label(report_sending_options_frame, text="Reporting Email SMTP Port").grid(row=5, sticky=E)
        Label(report_sending_options_frame, text="Reporting Email Destination:").grid(row=6, sticky=E)

        def reporting_options_fields_state_set():
            if self.enable_reporting_checkbutton_variable.get() == "False":
                state = DISABLED
            else:
                state = NORMAL
            for child in report_sending_options_frame.winfo_children():
                child.configure(state=state)

        self.run_reporting_checkbutton = Checkbutton(master, variable=self.enable_reporting_checkbutton_variable,
                                                     onvalue="True", offvalue="False",
                                                     command=reporting_options_fields_state_set,
                                                     text="Enable Report Sending")
        self.report_email_address_field = Entry(report_sending_options_frame, width=40)
        self.report_email_username_field = Entry(report_sending_options_frame, width=40)
        self.report_email_password_field = Entry(report_sending_options_frame, show="*", width=40)
        self.report_email_smtp_server_field = Entry(report_sending_options_frame, width=40)
        self.reporting_smtp_port_field = Entry(report_sending_options_frame, width=40)
        self.report_email_destination_field = Entry(report_sending_options_frame, width=40)
        self.log_printing_fallback_checkbutton = \
            Checkbutton(report_sending_options_frame, variable=self.enable_report_printing_checkbutton_variable,
                        onvalue="True",
                        offvalue="False",
                        text="Enable Report Printing Fallback:")
        rclick_report_email_address_field = rclick_menu.RightClickMenu(self.report_email_address_field)
        rclick_report_email_username_field = rclick_menu.RightClickMenu(self.report_email_username_field)
        rclick_report_email_smtp_server_field = rclick_menu.RightClickMenu(self.report_email_smtp_server_field)
        rclick_reporting_smtp_port_field = rclick_menu.RightClickMenu(self.reporting_smtp_port_field)
        rclick_report_email_destination_field = rclick_menu.RightClickMenu(self.report_email_destination_field)
        self.report_email_address_field.bind("<3>", rclick_report_email_address_field)
        self.report_email_username_field.bind("<3>", rclick_report_email_username_field)
        self.report_email_smtp_server_field.bind("<3>", rclick_report_email_smtp_server_field)
        self.reporting_smtp_port_field.bind("<3>", rclick_reporting_smtp_port_field)
        self.report_email_destination_field.bind("<3>", rclick_report_email_destination_field)
        self.select_log_folder_button = Button(master, text="Select Log Folder...",
                                               command=lambda: select_log_directory())

        def select_log_directory():
            try:
                if os.path.exists(self.logs_directory):
                    initial_directory = self.logs_directory
                else:
                    initial_directory = os.getcwd()
            except:
                initial_directory = os.getcwd()
            logs_directory_edit_proposed = str(askdirectory(initialdir=initial_directory))
            if len(logs_directory_edit_proposed) > 0:
                self.logs_directory = logs_directory_edit_proposed

        self.enable_reporting_checkbutton_variable.set(self.foldersnameinput['enable_reporting'])
        self.report_email_address_field.insert(0, self.foldersnameinput['report_email_address'])
        self.report_email_username_field.insert(0, self.foldersnameinput['report_email_username'])
        self.report_email_password_field.insert(0, self.foldersnameinput['report_email_password'])
        self.report_email_smtp_server_field.insert(0, self.foldersnameinput['report_email_smtp_server'])
        self.reporting_smtp_port_field.insert(0, self.foldersnameinput['reporting_smtp_port'])
        self.report_email_destination_field.insert(0, self.foldersnameinput['report_email_destination'])
        self.enable_report_printing_checkbutton_variable.set(self.foldersnameinput['report_printing_fallback'])

        reporting_options_fields_state_set()

        report_sending_options_frame.grid(row=3, columnspan=3)
        self.run_reporting_checkbutton.grid(row=0, column=0, padx=2, pady=2, sticky=W)
        self.report_email_address_field.grid(row=1, column=1, padx=2, pady=2)
        self.report_email_username_field.grid(row=2, column=1, padx=2, pady=2)
        self.report_email_password_field.grid(row=3, column=1, padx=2, pady=2)
        self.report_email_smtp_server_field.grid(row=4, column=1, padx=2, pady=2)
        self.reporting_smtp_port_field.grid(row=5, column=1, padx=2, pady=2)
        self.report_email_destination_field.grid(row=6, column=1, padx=2, pady=2)
        self.select_log_folder_button.grid(row=0, column=1, padx=2, pady=2, sticky=E)
        self.log_printing_fallback_checkbutton.grid(row=7, column=1, padx=2, pady=2, sticky=W)

        return self.report_email_address_field  # initial focus

    def validate(self):

        doingstuffoverlay.make_overlay(self, "Testing Changes...")
        error_list = []
        errors = False

        if self.report_email_address_field.get() == '':
            error_list.append("Reporting Email Address Is A Required Field\r")
            errors = True
        else:
            if (validate_email(str(self.report_email_address_field.get()), verify=True)) is False:
                error_list.append("Invalid Email Origin Address\r")
                errors = True

        if self.report_email_username_field.get() == '':
            error_list.append("Reporting Email Username Is A Required Field\r")
            errors = True

        if self.report_email_password_field.get() == '':
            error_list.append("Reporting Email Password Is A Required Field\r")
            errors = True

        if self.report_email_smtp_server_field.get() == '':
            error_list.append("Reporting Email Address Is A Required Field\r")
            errors = True

        if self.reporting_smtp_port_field.get() == '':
            error_list.append("SMTP Port Is A Required Field\r")
            errors = True

        if self.report_email_destination_field.get() == '':
            error_list.append("Reporting Email Destination Is A Required Field\r")
            errors = True
        else:
            email_recepients = str(self.report_email_destination_field.get()).split(", ")
            for email_recepient in email_recepients:
                print(email_recepient)
                if (validate_email(str(email_recepient), verify=True)) is False:
                    error_list.append("Invalid Email Destination Address\r\n")
                    errors = True

        if errors is True:
            error_report = ''.join(error_list)  # combine error messages into single string
            showerror(message=error_report)  # display generated error string in error dialog
            doingstuffoverlay.destroy_overlay()
            return False
        doingstuffoverlay.destroy_overlay()
        return 1

    def ok(self, event=None):

        if self.enable_reporting_checkbutton_variable.get() == "True":
            if not self.validate():
                self.initial_focus.focus_set()  # put focus back
                return

        self.withdraw()
        self.update_idletasks()

        self.apply(self.foldersnameinput)

        self.cancel()

    def apply(self, folders_name_apply):

        doingstuffoverlay.make_overlay(self, "Applying Changes...")
        folders_name_apply['enable_reporting'] = str(self.enable_reporting_checkbutton_variable.get())
        folders_name_apply['logs_directory'] = self.logs_directory
        folders_name_apply['report_email_address'] = str(self.report_email_address_field.get())
        folders_name_apply['report_email_username'] = str(self.report_email_username_field.get())
        folders_name_apply['report_email_password'] = str(self.report_email_password_field.get())
        folders_name_apply['report_email_smtp_server'] = str(self.report_email_smtp_server_field.get())
        folders_name_apply['reporting_smtp_port'] = str(self.reporting_smtp_port_field.get())
        folders_name_apply['report_email_destination'] = str(self.report_email_destination_field.get())

        update_reporting(folders_name_apply)
        doingstuffoverlay.destroy_overlay()


class EditDialog(dialog.Dialog):  # modal dialog for folder configuration.

    def body(self, master):

        self.resizable(width=FALSE, height=FALSE)
        global copy_to_directory
        copy_to_directory = self.foldersnameinput['copy_to_directory']
        self.convert_formats_var = StringVar(master)
        self.title("Folder Settings")
        self.bodyframe = Frame(master)
        self.folderframe = Frame(self.bodyframe)
        self.prefsframe = Frame(self.bodyframe)
        self.ediframe = Frame(self.bodyframe)
        self.convert_options_frame = Frame(self.ediframe)
        self.separatorv1 = Separator(self.bodyframe, orient=VERTICAL)
        self.separatorv2 = Separator(self.bodyframe, orient=VERTICAL)
        self.backendvariable = StringVar(master)
        self.active_checkbutton = StringVar(master)
        self.ediconvert_options = StringVar(master)
        self.process_edi = StringVar(master)
        self.upc_var_check = StringVar(master)  # define  "UPC calculation" checkbox state variable
        self.a_rec_var_check = StringVar(master)  # define "A record checkbox state variable
        self.c_rec_var_check = StringVar(master)  # define "C record" checkbox state variable
        self.headers_check = StringVar(master)  # define "Column Headers" checkbox state variable
        self.ampersand_check = StringVar(master)  # define "Filter Ampersand" checkbox state variable
        self.tweak_edi = BooleanVar(master)
        self.pad_arec_check = StringVar(master)
        self.process_backend_copy_check = BooleanVar(master)
        self.process_backend_ftp_check = BooleanVar(master)
        self.process_backend_email_check = BooleanVar(master)
        self.header_frame_frame = Frame(master)
        Label(self.folderframe, text="Backends:").grid(row=2, sticky=W)
        if self.foldersnameinput['folder_name'] != 'template':
            Label(self.folderframe, text="Alias:").grid(row=5, sticky=E)
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
        Label(self.prefsframe, text="Sender Address:").grid(row=15, sticky=E)
        Label(self.prefsframe, text="Sender Username:").grid(row=16, sticky=E)
        Label(self.prefsframe, text="Sender Password:").grid(row=17, sticky=E)
        Label(self.prefsframe, text="Email Subject:").grid(row=18, sticky=E)
        Label(self.prefsframe, text="Sender SMTP Server:").grid(row=19, sticky=E)
        Label(self.prefsframe, text="SMTP Server Port:").grid(row=20, sticky=E)
        Label(self.ediframe, text="EDI Convert Settings:").grid(row=0, column=0, columnspan=2, pady=3)
        Separator(self.ediframe, orient=HORIZONTAL).grid(row=4, columnspan=2, sticky=E + W, pady=1)
        self.convert_options_frame.grid(column=0, row=5, columnspan=2, sticky=W)
        self.convert_to_selector_frame = Frame(self.convert_options_frame)
        self.convert_to_selector_label = Label(self.convert_to_selector_frame, text="Convert To: ")
        self.convert_to_selector_menu = OptionMenu(self.convert_to_selector_frame, self.convert_formats_var,
                                                   self.foldersnameinput['convert_to_format'],
                                                   'csv', 'insight')

        def select_copy_to_directory():
            global copy_to_directory
            try:
                if os.path.exists(copy_to_directory):
                    initial_directory = copy_to_directory
                else:
                    initial_directory = os.getcwd()
            except:
                initial_directory = os.getcwd()
            copy_to_directory = str(askdirectory(initialdir=initial_directory))

        def set_send_options_fields_state():
            if self.process_backend_copy_check.get() is False and self.process_backend_ftp_check.get() is False and \
                            self.process_backend_email_check.get() is False:
                self.edi_options_menu.configure(state=DISABLED)
            else:
                self.edi_options_menu.configure(state=NORMAL)
            if self.process_backend_copy_check.get() is False:
                copy_state = DISABLED
            else:
                copy_state = NORMAL
            if self.process_backend_email_check.get() is False:
                email_state = DISABLED
            else:
                email_state = NORMAL
            if self.process_backend_ftp_check.get() is False:
                ftp_state = DISABLED
            else:
                ftp_state = NORMAL
            self.copy_backend_folder_selection_button.configure(state=copy_state)
            self.email_recepient_field.configure(state=email_state)
            self.email_sender_address_field.configure(state=email_state)
            self.email_sender_username_field.configure(state=email_state)
            self.email_sender_password_field.configure(state=email_state)
            self.email_sender_subject_field.configure(state=email_state)
            self.email_smtp_field.configure(state=email_state)
            self.email_smtp_port_field.configure(state=email_state)
            self.ftp_server_field.configure(state=ftp_state)
            self.ftp_port_field.configure(state=ftp_state)
            self.ftp_folder_field.configure(state=ftp_state)
            self.ftp_username_field.configure(state=ftp_state)
            self.ftp_password_field.configure(state=ftp_state)

        def set_header_state():
            if self.active_checkbutton.get() == "False":
                self.active_checkbutton_object.configure(text="Folder Is Disabled", activebackground="green")
                self.copy_backend_checkbutton.configure(state=DISABLED)
                self.ftp_backend_checkbutton.configure(state=DISABLED)
                self.email_backend_checkbutton.configure(state=DISABLED)
            else:
                self.active_checkbutton_object.configure(text="Folder Is Enabled", activebackground="red")
                self.copy_backend_checkbutton.configure(state=NORMAL)
                self.ftp_backend_checkbutton.configure(state=NORMAL)
                self.email_backend_checkbutton.configure(state=NORMAL)

        self.active_checkbutton_object = Tkinter.Checkbutton(self.header_frame_frame, text="Active",
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
            Label(self.folderframe, text="Folder Alias:").grid(row=6, sticky=W)
            self.folder_alias_field = Entry(self.folderframe, width=30)
            rclick_folder_alias_field = rclick_menu.RightClickMenu(self.folder_alias_field)
            self.folder_alias_field.bind("<3>", rclick_folder_alias_field)
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
        self.email_sender_address_field = Entry(self.prefsframe, width=30)
        rclick_email_sender_address_field = rclick_menu.RightClickMenu(self.email_sender_address_field)
        self.email_sender_address_field.bind("<3>", rclick_email_sender_address_field)
        self.email_sender_username_field = Entry(self.prefsframe, width=30)
        rclick_email_sender_username_field = rclick_menu.RightClickMenu(self.email_sender_username_field)
        self.email_sender_username_field.bind("<3>", rclick_email_sender_username_field)
        self.email_sender_password_field = Entry(self.prefsframe, show="*", width=30)
        self.email_sender_subject_field = Entry(self.prefsframe, width=30)
        rclick_email_sender_subject_field = rclick_menu.RightClickMenu(self.email_sender_subject_field)
        self.email_sender_subject_field.bind("<3>", rclick_email_sender_subject_field)
        self.email_smtp_field = Entry(self.prefsframe, width=30)
        rclick_email_smtp_field = rclick_menu.RightClickMenu(self.email_smtp_field)
        self.email_smtp_field.bind("<3>", rclick_email_smtp_field)
        self.email_smtp_port_field = Entry(self.prefsframe, width=30)
        rclick_email_smtp_port_field = rclick_menu.RightClickMenu(self.email_smtp_port_field)
        self.email_smtp_port_field.bind("<3>", rclick_email_smtp_port_field)
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
                                                text="Include " + "C " + "Records", onvalue="True", offvalue="False")
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

        self.active_checkbutton.set(self.foldersnameinput['folder_is_active'])
        if self.foldersnameinput['folder_name'] != 'template':
            self.folder_alias_field.insert(0, self.foldersnameinput['alias'])
        self.process_backend_copy_check.set(self.foldersnameinput['process_backend_copy'])
        self.process_backend_ftp_check.set(self.foldersnameinput['process_backend_ftp'])
        self.process_backend_email_check.set(self.foldersnameinput['process_backend_email'])
        self.ftp_server_field.insert(0, self.foldersnameinput['ftp_server'])
        self.ftp_port_field.insert(0, self.foldersnameinput['ftp_port'])
        self.ftp_folder_field.insert(0, self.foldersnameinput['ftp_folder'])
        self.ftp_username_field.insert(0, self.foldersnameinput['ftp_username'])
        self.ftp_password_field.insert(0, self.foldersnameinput['ftp_password'])
        self.email_recepient_field.insert(0, self.foldersnameinput['email_to'])
        self.email_sender_address_field.insert(0, self.foldersnameinput['email_origin_address'])
        self.email_sender_username_field.insert(0, self.foldersnameinput['email_origin_username'])
        self.email_sender_password_field.insert(0, self.foldersnameinput['email_origin_password'])
        self.email_sender_subject_field.insert(0, self.foldersnameinput['email_subject_line'])
        self.email_smtp_field.insert(0, self.foldersnameinput['email_origin_smtp_server'])
        self.email_smtp_port_field.insert(0, self.foldersnameinput['email_smtp_port'])
        self.process_edi.set(self.foldersnameinput['process_edi'])
        self.upc_var_check.set(self.foldersnameinput['calculate_upc_check_digit'])
        self.a_rec_var_check.set(self.foldersnameinput['include_a_records'])
        self.c_rec_var_check.set(self.foldersnameinput['include_c_records'])
        self.headers_check.set(self.foldersnameinput['include_headers'])
        self.ampersand_check.set(self.foldersnameinput['filter_ampersand'])
        self.pad_arec_check.set(self.foldersnameinput['pad_a_records'])
        self.tweak_edi.set(self.foldersnameinput['tweak_edi'])
        self.a_record_padding_field.insert(0, self.foldersnameinput['a_record_padding'])

        def reset_ediconvert_options(argument):
            for child in self.convert_options_frame.winfo_children():
                child.grid_forget()
            make_ediconvert_options(argument)

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
                self.upc_variable_process_checkbutton.grid(row=2, column=0, sticky=W, padx=3)
                self.a_record_checkbutton.grid(row=4, column=0, sticky=W, padx=3)
                self.c_record_checkbutton.grid(row=5, column=0, sticky=W, padx=3)
                self.headers_checkbutton.grid(row=6, column=0, sticky=W, padx=3)
                self.ampersand_checkbutton.grid(row=7, column=0, sticky=W, padx=3)
                self.pad_a_records_checkbutton.grid(row=9, column=0, sticky=W, padx=3)
                self.a_record_padding_field.grid(row=9, column=2)
            if argument == 'Tweak EDI':
                self.tweak_edi.set(True)
                self.process_edi.set('False')
                self.pad_a_records_checkbutton.grid(row=9, column=0, sticky=W, padx=3)
                self.a_record_padding_field.grid(row=9, column=2)

        if self.foldersnameinput['process_edi'] == 'True':
            self.ediconvert_options.set("Convert EDI")
            make_ediconvert_options('Convert EDI')
        elif self.foldersnameinput['tweak_edi'] is True:
            self.ediconvert_options.set("Tweak EDI")
            make_ediconvert_options('Tweak EDI')
        else:
            self.ediconvert_options.set("Do Nothing")
            make_ediconvert_options('Do Nothing')

        self.edi_options_menu = OptionMenu(self.ediframe, self.ediconvert_options, self.ediconvert_options.get(),
                                           'Do Nothing', 'Convert EDI', 'Tweak EDI',
                                           command=reset_ediconvert_options)

        set_header_state()
        set_send_options_fields_state()

        self.edi_options_menu.grid(row=3)
        self.active_checkbutton_object.pack(fill=X)
        self.copy_backend_checkbutton.grid(row=3, column=0, sticky=W)
        self.ftp_backend_checkbutton.grid(row=4, column=0, sticky=W)
        self.email_backend_checkbutton.grid(row=5, column=0, sticky=W)
        if self.foldersnameinput['folder_name'] != 'template':
            self.folder_alias_field.grid(row=6, column=1)
        self.copy_backend_folder_selection_button.grid(row=4, column=0, columnspan=2)
        self.ftp_server_field.grid(row=7, column=1)
        self.ftp_port_field.grid(row=8, column=1)
        self.ftp_folder_field.grid(row=9, column=1)
        self.ftp_username_field.grid(row=10, column=1)
        self.ftp_password_field.grid(row=11, column=1)
        self.email_recepient_field.grid(row=14, column=1)
        self.email_sender_address_field.grid(row=15, column=1)
        self.email_sender_username_field.grid(row=16, column=1)
        self.email_sender_password_field.grid(row=17, column=1)
        self.email_sender_subject_field.grid(row=18, column=1)
        self.email_smtp_field.grid(row=19, column=1)
        self.email_smtp_port_field.grid(row=20, column=1)

        self.header_frame_frame.pack(fill=X)
        self.bodyframe.pack()

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
        apply_to_folder['email_origin_address'] = str(self.email_sender_address_field.get())
        apply_to_folder['email_origin_username'] = str(self.email_sender_username_field.get())
        apply_to_folder['email_origin_password'] = str(self.email_sender_password_field.get())
        apply_to_folder['email_subject_line'] = str(self.email_sender_subject_field.get())
        apply_to_folder['email_origin_smtp_server'] = str(self.email_smtp_field.get())
        apply_to_folder['email_smtp_port'] = int(self.email_smtp_port_field.get())
        apply_to_folder['process_edi'] = str(self.process_edi.get())
        apply_to_folder['convert_to_format'] = str(self.convert_formats_var.get())
        apply_to_folder['calculate_upc_check_digit'] = str(self.upc_var_check.get())
        apply_to_folder['include_a_records'] = str(self.a_rec_var_check.get())
        apply_to_folder['include_c_records'] = str(self.c_rec_var_check.get())
        apply_to_folder['include_headers'] = str(self.headers_check.get())
        apply_to_folder['filter_ampersand'] = str(self.ampersand_check.get())
        apply_to_folder['tweak_edi'] = self.tweak_edi.get()
        apply_to_folder['pad_a_records'] = str(self.pad_arec_check.get())
        apply_to_folder['a_record_padding'] = str(self.a_record_padding_field.get())

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
        if self.process_backend_ftp_check.get() is True:

            backend_count += 1

            if self.ftp_server_field.get() == "":
                error_string_constructor_list.append("FTP Server Field Is Required\r\n")
                errors = True

            if self.ftp_port_field.get() == "":
                error_string_constructor_list.append("FTP Port Field Is Required\r\n")
                errors = True

            if self.ftp_folder_field.get() == "":
                error_string_constructor_list.append("FTP Folder Field Is Required\r\n")
                errors = True
            else:
                if self.ftp_folder_field.get()[-1] is not "/":
                    error_string_constructor_list.append("FTP Folder Path Needs To End In /\r\n")
                    errors = True

            if self.ftp_username_field.get() == "":
                error_string_constructor_list.append("FTP Username Field Is Required\r\n")
                errors = True

            if self.ftp_password_field.get() == "":
                error_string_constructor_list.append("FTP Password Field Is Required\r\n")
                errors = True

            try:
                temp_smtp_port_check = int(self.ftp_port_field.get())
            except Exception:
                error_string_constructor_list.append("FTP Port Field Needs To Be A Number\r\n")
                errors = True

        if self.process_backend_email_check.get() is True:

            backend_count += 1

            if self.foldersnameinput == 'template':
                if self.email_recepient_field.get() == "":
                    error_string_constructor_list.append("Email Destination Address Field Is Required\r\n")
                    errors = True
                else:
                    email_recepients = str(self.email_recepient_field.get()).split(", ")
                    for email_recepient in email_recepients:
                        print(email_recepient)
                        if (validate_email(str(email_recepient), verify=True)) is False:
                            error_string_constructor_list.append("Invalid Email Destination Address\r\n")
                            errors = True

            if self.email_sender_address_field.get() == "":
                error_string_constructor_list.append("Email Origin Address Field Is Required\r\n")
                errors = True
            else:
                if (validate_email(str(self.email_sender_address_field.get()), verify=True)) is False:
                    error_string_constructor_list.append("Invalid Email Origin Address\r\n")
                    errors = True

            if self.email_sender_username_field.get() == "":
                error_string_constructor_list.append("Email Username Field Is Required\r\n")
                errors = True

            if self.email_sender_password_field.get() == "":
                error_string_constructor_list.append("Email Password Field Is Required\r\n")
                errors = True

            if self.email_smtp_field.get() == "":
                error_string_constructor_list.append("SMTP Server Field Is Required\r\n")
                errors = True

            if self.email_smtp_port_field.get() == "":
                error_string_constructor_list.append("SMTP Port Field Is Required\r\n")
                errors = True
            else:
                try:
                    temp_smtp_port_check = int(self.email_smtp_port_field.get())
                except Exception:
                    error_string_constructor_list.append("SMTP Port Field Needs To Be A Number\r\n")
                    errors = True

        if self.process_backend_copy_check.get() is True:

            backend_count += 1

            if copy_to_directory is None or copy_to_directory == "":
                error_string_constructor_list.append("Copy Backend Destination Is currently Unset,"
                                                     " Please Select One\r\n")
                errors = True

        if backend_count is 0 and self.active_checkbutton.get() == "True":
            error_string_constructor_list.append("No Backend Is Selected")
            errors = True

        if len(str(self.a_record_padding_field.get())) is not 6 and str(self.pad_arec_check.get()) == "True":
            error_string_constructor_list.append('"A" Record Padding Needs To Be Six Characters\r\n')
            errors = True

        if self.foldersnameinput['folder_name'] != 'template':
            if str(self.folder_alias_field.get()) != self.foldersnameinput['alias']:
                proposed_folder = folders_table.find_one(alias=str(self.folder_alias_field.get()))
                if proposed_folder is not None:
                    error_string_constructor_list.append("Folder Alias Already In Use\r\n")
                    errors = True

            if len(self.folder_alias_field.get()) > 50:
                error_string_constructor_list.append("Alias Too Long\r\n")
                errors = True
        if errors is True:
            doingstuffoverlay.destroy_overlay()
            error_string = ''.join(error_string_constructor_list)  # combine error messages into single string
            showerror(message=error_string)  # display generated error in dialog box
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
    if missing_folder is True:
        showerror("Error", "One or more expected folders are missing.")
    else:
        if folders_table_process.count(folder_is_active="True") > 0:
            doingstuffoverlay.make_overlay(parent=root, overlay_text="processing folders...")
            process_directories(folders_table_process)
            refresh_users_list()  # refresh the users list in case the active state has changed
            set_main_button_states()
            doingstuffoverlay.destroy_overlay()
        else:
            showerror("Error", "No Active Folders")


def set_defaults_popup():
    defaults = oversight_and_defaults.find_one(id=1)
    EditDialog(root, defaults)


def process_directories(folders_table_process):
    original_folder = os.getcwd()
    global emails_table
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
    if check_logs_directory() is False or log_folder_creation_error is True:
        if args.automatic is False:
            # offer to make new log directory
            while check_logs_directory() is False:  # don't let user out unless they pick a writable folder, or cancel
                if askokcancel("Error", "Can't write to log directory,\r\n"
                                        " would you like to change reporting settings?"):
                    EditReportingDialog(root, oversight_and_defaults.find_one(id=1))
                else:
                    # the logs must flow. aka, stop here if user declines selecting a new writable log folder
                    showerror(message="Can't write to log directory, exiting")
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
    run_log = open(run_log_full_path, 'w')
    run_log.write("Batch File Sender Version " + version + "\r\n")
    run_log.write("starting run at " + time.ctime() + "\r\n")
    # call dispatch module to process active folders
    try:
        run_error_bool = dispatch.process(database_connection, folders_table_process, run_log, emails_table,
                                          reporting['logs_directory'],
                                          reporting,
                                          processed_files, root, args, version, errors_directory,
                                          edi_converter_scratch_folder)
        if run_error_bool is True and not args.automatic:
            showinfo("Run Status", "Run completed with errors.")
        os.chdir(original_folder)
    except Exception, dispatch_error:
        os.chdir(original_folder)
        # if processing folders runs into a serious error, report and log
        print(
            "Run failed, check your configuration \r\nError from dispatch module is: \r\n" + str(
                    dispatch_error) + "\r\n")
        run_log.write(
                "Run failed, check your configuration \r\nError from dispatch module is: \r\n" + str(
                        dispatch_error) + "\r\n")
    run_log.close()
    if reporting['enable_reporting'] == "True":
        # add run log to email queue if reporting is enabled
        emails_table.insert(dict(log=run_log_full_path, folder_alias=run_log_name_constructor))
        try:
            sent_emails_removal_queue.delete()
            total_size = 0
            skipped_files = 0
            email_errors = cStringIO.StringIO()
            total_emails = emails_table.count()
            emails_count = 0
            batch_number = 1
            for log in emails_table.all():
                emails_count += 1
                if os.path.isfile(log['log']):
                    # iterate over emails to send queue, breaking it into 9mb chunks if necessary
                    total_size += total_size + os.path.getsize(log['log'])  # add size of current file to total
                    emails_table_batch.insert(log)
                    # if the total size is more than 9mb, then send that set and reset the total
                    if total_size > 9000000:
                        batch_log_sender.do(reporting, emails_table_batch, sent_emails_removal_queue, start_time, args,
                                            root, batch_number, emails_count, total_emails)
                        emails_table_batch.delete()  # clear batch
                        total_size = 0
                        batch_number += 1
                else:
                    email_errors.write("\r\n" + log['log'] + " missing, skipping")
                    email_errors.write("\r\n file was expected to be at " + log['log'] + " on the sending computer")
                    skipped_files += 1
                    sent_emails_removal_queue.insert(log)
            if emails_table_batch.count() > 0:
                # send the remainder of emails
                batch_log_sender.do(reporting, emails_table_batch, sent_emails_removal_queue, start_time, args, root,
                                    batch_number, emails_count, total_emails)
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
                    batch_log_sender.do(reporting, emails_table_batch, sent_emails_removal_queue, start_time, args,
                                        root, batch_number, emails_count, total_emails)
                    emails_table_batch.delete()
                except Exception, email_send_error:
                    print(email_send_error)
                    doingstuffoverlay.destroy_overlay()
                    emails_table_batch.delete()
        except Exception, dispatch_error:
            emails_table_batch.delete()
            run_log = open(run_log_full_path, 'a')
            if reporting['report_printing_fallback'] != "True":
                print("Emailing report log failed with: " + str(dispatch_error) + ", printing file\r\n")
                run_log.write("Emailing report log failed with: " + str(dispatch_error) + ", printing file\r\n")
            else:
                print("Emailing report log failed with: " + str(dispatch_error) + ", printing disabled, stopping\r\n")
                run_log.write(
                        "Emailing report log failed with: " + str(dispatch_error) + ", printing disabled, stopping\r\n")
            run_log.close()
            if reporting['report_printing_fallback'] == "True":
                # if for some reason emailing logs fails, and printing fallback is enabled, print the run log
                try:
                    run_log = open(run_log_full_path, 'r')
                    print_run_log.do(run_log)
                    run_log.close()
                except Exception, dispatch_error:
                    print("printing error log failed with error: " + str(dispatch_error) + "\r\n")
                    run_log = open(run_log_full_path, 'a')
                    run_log.write("Printing error log failed with error: " + str(dispatch_error) + "\r\n")
                    run_log.close()


def silent_process_directories(silent_process_folders_table):
    if silent_process_folders_table.count(folder_is_active="True") > 0:
        print "batch processing configured directories"
        try:
            process_directories(silent_process_folders_table)
        except Exception, silent_process_error:
            print(str(silent_process_error))
            silent_process_critical_log = open("critical_error.log", 'a')
            silent_process_critical_log.write(str(silent_process_error) + "\r\n")
            silent_process_critical_log.close()
    else:
        print("Error, No Active Folders")
    raise SystemExit


def remove_inactive_folders():  # loop over folders and safely remove ones marked as inactive
    users_refresh = False
    if folders_table.count(folder_is_active="False") > 0:
        users_refresh = True
    folders_total = folders_table.count(folder_is_active="False")
    folders_count = 0
    for folder_to_be_removed in folders_table.find(folder_is_active="False"):
        folders_count += 1
        doingstuffoverlay.make_overlay(maintenance_popup, "removing " + str(folders_count) + " of " +
                                       str(folders_total))
        delete_folder_entry(folder_to_be_removed['id'])
        doingstuffoverlay.destroy_overlay()
    if users_refresh:
        refresh_users_list()


def mark_active_as_processed():
    starting_folder = os.getcwd()
    folder_total = folders_table.count(folder_is_active="True")
    folder_count = 0
    doingstuffoverlay.make_overlay(maintenance_popup, "adding files to processed list...")
    for parameters_dict in folders_table.find(folder_is_active="True"):  # create list of active directories
        file_total = 0
        file_count = 0
        folder_count += 1
        doingstuffoverlay.destroy_overlay()
        doingstuffoverlay.make_overlay(parent=maintenance_popup,
                                       overlay_text="adding files to processed list...\n\n" + " folder " + str(
                                               folder_count) +
                                                    " of " + str(folder_total) + " file " + str(file_count) +
                                                    " of " + str(file_total))
        os.chdir(parameters_dict['folder_name'])
        files = [f for f in os.listdir('.') if os.path.isfile(f)]
        # create list of all files in directory
        file_total = len(files)
        filtered_files = []
        for f in files:
            file_count += 1
            doingstuffoverlay.destroy_overlay()
            doingstuffoverlay.make_overlay(parent=maintenance_popup,
                                           overlay_text="checking files for already processed\n\n" + str(folder_count) +
                                                        " of " + str(folder_total) + " file " + str(file_count) +
                                                        " of " + str(file_total))
            if processed_files.find_one(file_name=os.path.join(os.getcwd(), f), file_checksum=hashlib.md5(
                    open(f, 'rb').read()).hexdigest()) is None:
                filtered_files.append(f)
        file_total = len(filtered_files)
        file_count = 0
        for filename in filtered_files:
            print filename
            file_count += 1
            doingstuffoverlay.destroy_overlay()
            doingstuffoverlay.make_overlay(parent=maintenance_popup,
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


def set_all_inactive():
    total = folders_table.count(folder_is_active="True")
    count = 0
    for folder_to_be_inactive in folders_table.find(folder_is_active="True"):
        count += 1
        doingstuffoverlay.make_overlay(maintenance_popup, "processing " + str(count) + " of " + str(total))
        folder_to_be_inactive['folder_is_active'] = "False"
        folders_table.update(folder_to_be_inactive, ['id'])
        doingstuffoverlay.destroy_overlay()
    if total > 0:
        refresh_users_list()


def set_all_active():
    total = folders_table.count(folder_is_active="False")
    count = 0
    for folder_to_be_active in folders_table.find(folder_is_active="False"):
        count += 1
        doingstuffoverlay.make_overlay(maintenance_popup, "processing " + str(count) + " of " + str(total))
        folder_to_be_active['folder_is_active'] = "True"
        folders_table.update(folder_to_be_active, ['id'])
        doingstuffoverlay.destroy_overlay()
    if total > 0:
        refresh_users_list()


def maintenance_functions_popup():
    # first, warn the user that they can do very bad things with this dialog, and give them a chance to go back
    if askokcancel(message="Maintenance window is for advanced users only, potential for data loss if incorrectly used."
                           " Are you sure you want to continue?"):
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
        set_all_active_button = Button(maintenance_popup_button_frame, text="move all to active",
                                       command=set_all_active)
        set_all_inactive_button = Button(maintenance_popup_button_frame, text="move all to inactive",
                                         command=set_all_inactive)
        clear_emails_queue = Button(maintenance_popup_button_frame, text="clear queued emails",
                                    command=emails_table.delete)
        move_active_to_obe_button = Button(maintenance_popup_button_frame, text="Mark all in active as processed",
                                           command=mark_active_as_processed)
        remove_all_inactive = Button(maintenance_popup_button_frame, text="Remove all inactive configurations",
                                     command=remove_inactive_folders)
        # pack widgets into dialog
        set_all_active_button.pack(side=TOP, fill=X, padx=2, pady=2)
        set_all_inactive_button.pack(side=TOP, fill=X, padx=2, pady=2)
        clear_emails_queue.pack(side=TOP, fill=X, padx=2, pady=2)
        move_active_to_obe_button.pack(side=TOP, fill=X, padx=2, pady=2)
        remove_all_inactive.pack(side=TOP, fill=X, padx=2, pady=2)
        maintenance_popup_button_frame.pack(side=LEFT)
        maintenance_popup_warning_label.pack(side=RIGHT, padx=20)


def export_processed_report(name, output_folder):
    folder_alias = folders_table.find_one(id=name)
    processed_log_path = str(os.path.join(output_folder, folder_alias['alias'] + " processed report " + ".csv"))
    processed_log = open(processed_log_path, 'w')
    processed_log.write("File,Date,Copy Destination,FTP Destination,Email Destination\n")
    for line in processed_files.find(folder_id=name):
        processed_log.write(
                line['file_name'] + "," + "\t" + str(line['sent_date_time']) + "," + line['copy_destination'] +
                "," + line['ftp_destination'] + "," +
                str(line['email_destination']).replace(",", ";") + "\n")
    processed_log.close()
    showinfo(message="Processed File Report Exported To\n\n" + processed_log_path)


def processed_files_popup():
    global processed_files_output_folder
    folder_button_variable = IntVar()
    output_folder_is_confirmed = False
    prior_folder = oversight_and_defaults.find_one(id=1)
    processed_files_output_folder = prior_folder['export_processed_folder_prior']
    processed_files_popup_dialog = Toplevel()
    processed_files_popup_dialog.title("Generate Processed Files Report")
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
    Label(processed_files_popup_actions_frame, text="Select a Folder.").pack()
    if processed_files.count() == 0:
        no_processed_label = Label(processed_files_popup_list_frame, text="No Folders With Processed Files")
        no_processed_label.pack(fill=BOTH, expand=1, padx=10)
    for folders_name in processed_files.distinct('folder_id'):
        folder_row = processed_files.find_one(folder_id=folders_name['folder_id'])
        folder_dict = folders_table.find_one(id=folders_name['folder_id'])
        folder_alias = folder_dict['alias']
        Tkinter.Radiobutton(processed_files_popup_list_frame.interior, text=folder_alias,
                            variable=folder_button_variable,
                            value=folder_alias, indicatoron=FALSE,
                            command=lambda name=folder_row['folder_id']: folder_button_pressed(
                                    name)).pack(anchor='w',
                                                fill='x')

    def close_processed_files_popup():
        processed_files_popup_dialog.destroy()
        return

    def folder_button_pressed(name):
        global export_button
        global processed_files_output_folder
        for child in processed_files_popup_actions_frame.winfo_children():
            child.destroy()
        Button(processed_files_popup_actions_frame, text='Choose output Folder',
               command=set_output_folder).pack(pady=10)
        export_button = Button(processed_files_popup_actions_frame, text='Export Processed Report',
                               command=lambda: export_processed_report(name, processed_files_output_folder))
        if output_folder_is_confirmed is False:
            export_button.configure(state=DISABLED)
        else:
            export_button.configure(state=NORMAL)
        export_button.pack(pady=10)

    def set_output_folder():
        global output_folder_is_confirmed
        global processed_files_output_folder
        prior_folder = oversight_and_defaults.find_one(id=1)
        if os.path.exists(prior_folder['export_processed_folder_prior']):
            initial_directory = prior_folder['export_processed_folder_prior']
        else:
            initial_directory = os.getcwd()
        output_folder_proposed = askdirectory(initialdir=initial_directory)
        if output_folder_proposed == "":
            return
        else:
            output_folder = output_folder_proposed
        update_last_folder = dict(id=1, export_processed_folder_prior=output_folder)
        oversight_and_defaults.update(update_last_folder, ['id'])
        output_folder_is_confirmed = True
        processed_files_output_folder = output_folder
        if output_folder_is_confirmed is False:
            export_button.configure(state=DISABLED)
        else:
            export_button.configure(state=NORMAL)

    close_button = Button(processed_files_popup_close_frame, text="Close", command=close_processed_files_popup)
    close_button.pack()
    processed_files_popup_list_container.pack(side=LEFT)
    processed_files_popup_list_frame.pack()
    processed_files_popup_actions_frame.pack(side=RIGHT, anchor=N)
    processed_files_popup_body_frame.pack()
    processed_files_popup_close_frame.pack()


def set_main_button_states():
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
    silent_process_directories(folders_table)

make_users_list()

# define main window widgets
open_folder_button = Button(options_frame, text="Add Directory...", command=select_folder)
open_multiple_folder_button = Button(options_frame, text="Batch Add Directories...", command=batch_add_folders)
default_settings = Button(options_frame, text="Set Defaults...", command=set_defaults_popup)
edit_reporting = Button(options_frame, text="Edit Reporting...",
                        command=lambda: EditReportingDialog(root, oversight_and_defaults.find_one(id=1)))
process_folder_button = Button(options_frame, text="Process Folders",
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
options_frame.pack(side=LEFT, anchor='n', fill=Y)
options_frame_divider.pack(side=LEFT, fill=Y)
users_list_frame.pack(side=RIGHT, fill=BOTH, expand=1)

# set parameters for root window

# set window minimum size to prevent user making it ugly
root.update()  # update window geometry
# don't allow window to be resized smaller than current dimensions
root.minsize(root.winfo_width(), root.winfo_height())
root.resizable(width=FALSE, height=TRUE)

root.mainloop()
