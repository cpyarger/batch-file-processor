# This Python file uses the following encoding: utf-8
import sys
import os
from sys import exit, stdout
from os import path
from time import time, sleep
import logging, json,  base64

from PySide2.QtWidgets import QApplication, QMainWindow
from PySide2.QtCore import QFile
from PySide2.QtUiTools import QUiLoader
from PyQt5 import uic, QtWidgets,QtCore
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import   pyqtSlot, pyqtSignal
SCRIPT_DIR = path.dirname(path.realpath(__file__))

def get_logger( level=logging.debug):
    log_format = logging.Formatter('[%(asctime)s] (%(levelname)s) T%(thread)d : %(message)s')
    std_output = logging.StreamHandler(stdout)
    std_output.setFormatter(log_format)
    std_output.setLevel(level)
    file_output = logging.FileHandler(path.join(SCRIPT_DIR, "debug.log"))
    file_output.setFormatter(log_format)
    file_output.setLevel(level)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_output)
    logger.addHandler(std_output)
    return logger



class main(QMainWindow):
    def __init__(self):
        super(main, self).__init__()



if __name__ == "__main__":
    get_logger(logging.DEBUG)
    Form, Window = uic.loadUiType("form.ui")
    app = QApplication(sys.argv)
    window = Window()
    form = Form()
    form.setupUi(window)
    window.show()


    logging.debug("Program Startup")





    sys.exit(app.exec_())
