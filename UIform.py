# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
##
## Created by: Qt User Interface Compiler version 5.15.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QDate, QDateTime, QMetaObject,
    QObject, QPoint, QRect, QSize, QTime, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPalette, QPainter,
    QPixmap, QRadialGradient)
from PySide2.QtWidgets import *


class Ui_main(object):
    def setupUi(self, main):
        if not main.objectName():
            main.setObjectName(u"main")
        main.resize(800, 600)
        self.actionQuit = QAction(main)
        self.actionQuit.setObjectName(u"actionQuit")
        self.centralwidget = QWidget(main)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_2 = QGridLayout(self.centralwidget)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.splitter = QSplitter(self.centralwidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Vertical)
        self.btn_add_directory = QPushButton(self.splitter)
        self.btn_add_directory.setObjectName(u"btn_add_directory")
        self.splitter.addWidget(self.btn_add_directory)
        self.btn_batch_add_directories = QPushButton(self.splitter)
        self.btn_batch_add_directories.setObjectName(u"btn_batch_add_directories")
        self.splitter.addWidget(self.btn_batch_add_directories)
        self.btn_set_defaults = QPushButton(self.splitter)
        self.btn_set_defaults.setObjectName(u"btn_set_defaults")
        self.splitter.addWidget(self.btn_set_defaults)
        self.btn_edit_settings = QPushButton(self.splitter)
        self.btn_edit_settings.setObjectName(u"btn_edit_settings")
        self.splitter.addWidget(self.btn_edit_settings)
        self.btn_maintaince = QPushButton(self.splitter)
        self.btn_maintaince.setObjectName(u"btn_maintaince")
        self.splitter.addWidget(self.btn_maintaince)
        self.btn_processed_file_report = QPushButton(self.splitter)
        self.btn_processed_file_report.setObjectName(u"btn_processed_file_report")
        self.splitter.addWidget(self.btn_processed_file_report)

        self.verticalLayout.addWidget(self.splitter)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_2)

        self.splitter_2 = QSplitter(self.centralwidget)
        self.splitter_2.setObjectName(u"splitter_2")
        self.splitter_2.setOrientation(Qt.Vertical)
        self.btn_enable_resend = QPushButton(self.splitter_2)
        self.btn_enable_resend.setObjectName(u"btn_enable_resend")
        self.splitter_2.addWidget(self.btn_enable_resend)
        self.btn_process_all_folders = QPushButton(self.splitter_2)
        self.btn_process_all_folders.setObjectName(u"btn_process_all_folders")
        self.splitter_2.addWidget(self.btn_process_all_folders)

        self.verticalLayout.addWidget(self.splitter_2)


        self.gridLayout_2.addLayout(self.verticalLayout, 0, 0, 1, 1)

        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.lv_inactive_folders = QListView(self.centralwidget)
        self.lv_inactive_folders.setObjectName(u"lv_inactive_folders")

        self.gridLayout.addWidget(self.lv_inactive_folders, 1, 0, 1, 1)

        self.label_inactive_folders = QLabel(self.centralwidget)
        self.label_inactive_folders.setObjectName(u"label_inactive_folders")

        self.gridLayout.addWidget(self.label_inactive_folders, 0, 0, 1, 1)

        self.label_actions = QLabel(self.centralwidget)
        self.label_actions.setObjectName(u"label_actions")

        self.gridLayout.addWidget(self.label_actions, 0, 2, 1, 1)

        self.label_active_filters = QLabel(self.centralwidget)
        self.label_active_filters.setObjectName(u"label_active_filters")

        self.gridLayout.addWidget(self.label_active_filters, 0, 1, 1, 1)

        self.splitter_3 = QSplitter(self.centralwidget)
        self.splitter_3.setObjectName(u"splitter_3")
        self.splitter_3.setOrientation(Qt.Vertical)
        self.btn_act_activate = QPushButton(self.splitter_3)
        self.btn_act_activate.setObjectName(u"btn_act_activate")
        self.splitter_3.addWidget(self.btn_act_activate)
        self.btn_act_edit = QPushButton(self.splitter_3)
        self.btn_act_edit.setObjectName(u"btn_act_edit")
        self.splitter_3.addWidget(self.btn_act_edit)
        self.btn_act_send = QPushButton(self.splitter_3)
        self.btn_act_send.setObjectName(u"btn_act_send")
        self.splitter_3.addWidget(self.btn_act_send)

        self.gridLayout.addWidget(self.splitter_3, 1, 2, 1, 1)

        self.lv_active_folders = QListView(self.centralwidget)
        self.lv_active_folders.setObjectName(u"lv_active_folders")

        self.gridLayout.addWidget(self.lv_active_folders, 1, 1, 1, 1)

        self.btn_update_filter = QPushButton(self.centralwidget)
        self.btn_update_filter.setObjectName(u"btn_update_filter")

        self.gridLayout.addWidget(self.btn_update_filter, 2, 1, 1, 1)

        self.line_filter = QLineEdit(self.centralwidget)
        self.line_filter.setObjectName(u"line_filter")

        self.gridLayout.addWidget(self.line_filter, 2, 0, 1, 1)


        self.gridLayout_2.addLayout(self.gridLayout, 0, 1, 1, 1)

        main.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(main)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuHelp = QMenu(self.menubar)
        self.menuHelp.setObjectName(u"menuHelp")
        main.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(main)
        self.statusbar.setObjectName(u"statusbar")
        main.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuFile.addAction(self.actionQuit)

        self.retranslateUi(main)
        self.actionQuit.triggered.connect(main.close)

        QMetaObject.connectSlotsByName(main)
    # setupUi

    def retranslateUi(self, main):
        main.setWindowTitle(QCoreApplication.translate("main", u"main", None))
        self.actionQuit.setText(QCoreApplication.translate("main", u"Quit", None))
        self.btn_add_directory.setText(QCoreApplication.translate("main", u"Add Directory", None))
        self.btn_batch_add_directories.setText(QCoreApplication.translate("main", u"Batch Add Directories", None))
        self.btn_set_defaults.setText(QCoreApplication.translate("main", u"Set Defaults", None))
        self.btn_edit_settings.setText(QCoreApplication.translate("main", u"Edit Settings", None))
        self.btn_maintaince.setText(QCoreApplication.translate("main", u"Maintaince", None))
        self.btn_processed_file_report.setText(QCoreApplication.translate("main", u"Processed files report", None))
        self.btn_enable_resend.setText(QCoreApplication.translate("main", u"Enable Resend", None))
        self.btn_process_all_folders.setText(QCoreApplication.translate("main", u"Process All Folders", None))
        self.label_inactive_folders.setText(QCoreApplication.translate("main", u"Inactive Folders", None))
        self.label_actions.setText(QCoreApplication.translate("main", u"Actions", None))
        self.label_active_filters.setText(QCoreApplication.translate("main", u"Active Folders", None))
        self.btn_act_activate.setText(QCoreApplication.translate("main", u"Activate", None))
        self.btn_act_edit.setText(QCoreApplication.translate("main", u"Edit", None))
        self.btn_act_send.setText(QCoreApplication.translate("main", u"Send", None))
        self.btn_update_filter.setText(QCoreApplication.translate("main", u"Update Filter", None))
        self.menuFile.setTitle(QCoreApplication.translate("main", u"File", None))
        self.menuHelp.setTitle(QCoreApplication.translate("main", u"Help", None))
    # retranslateUi

