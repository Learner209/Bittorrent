# -*- coding: gbk -*-
import asyncio
import signal
from asyncio import AbstractEventLoop
from concurrent.futures import CancelledError

from PySide2.QtCore import *
from PySide2.QtCore import QRect
from PySide2.QtGui import *
from PySide2.QtWidgets import *
from pieces.client import TorrentClient
from pieces.torrent import Torrent
# from quamash import QEventLoop

from mktorrent.mktorrent_wrapper import mainMaker

################################################################################
## Form generated from reading UI file 'ClientUIVicqLJ.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

announce_url = ['https://opentracker.i2p.rocks:443/announce']


class MyTextInput(QTextEdit):
    def __init__(self, parent=None):
        super(QTextEdit, self).__init__(parent)

    # 提取文本框的输入
    def ReadTo(self, ArgC):
        ArgC = self.toPlainText()


class MyTorrentButton(QPushButton):
    def __init__(self, inputTextBox: QTextEdit, parent=None):
        super().__init__(parent)
        self.inputTextBox = inputTextBox
        self.fw = parent

    def pushed(self):
        fileName = self.inputTextBox.toPlainText()
        if fileName != '':
            mainMaker(announce_urls=announce_url,
                      filename_of_the_file_to_be_torrented=fileName,
                      comment_to_the_metainfo="EasyHec_Hand-Eye_calibration",
                      donotWrite=None,
                      piece_length_setter=14,
                      torrent_name="EasyHec_Hand-Eye_calibration",
                      verbose=True,
                      )


class MyButton(QPushButton):
    def __init__(self, inputTextBox: QTextEdit, parent=None):
        super().__init__(parent)
        self.inputTextBox = inputTextBox
        self.fw = parent

    def pushed(self):
        torrentName = self.inputTextBox.toPlainText()
        if torrentName != '':
            self.fw.AddDownloadTask(torrentName, self.fw)


class MyDownloadWidget(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app

    def AddDownloadTask(self, taskClientName: str, parent=None):
        taskClient = TorrentClient(Torrent(taskClientName), self)
        self.widget = TaskWidget(taskClient, None, self.app, parent)
        self.widget.setObjectName(u"widget")
        self.widget.setGeometry(QRect(10, 100, 541, 221))
        self.label = QLabel(self.widget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(20, 10, 54, 12))
        self.downloadButton = QPushButton(self.widget)
        self.downloadButton.setObjectName(u"downloadButton")
        self.downloadButton.setGeometry(QRect(104, 2, 91, 41))
        self.downloadButton.setText(QCoreApplication.translate("MainWindow", u"\u5f00\u59cb\u4e0b\u8f7d", None))

        self.Thread = MyThread(self.widget)
        self.downloadButton.clicked.connect(self.widget.startDownload)

        self.progressBar = QProgressBar(self.widget)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setGeometry(QRect(340, 10, 118, 23))
        self.progressBar.setValue(0)
        self.widget.myProgressBar = self.progressBar
        self.textBrowser = QTextBrowser(self.widget)
        self.textBrowser.setObjectName(u"textBrowser")
        self.textBrowser.setGeometry(QRect(20, 40, 481, 192))
        self.textBrowser.setText('任务开始:\n')
        self.verticalScrollBar = QScrollBar(self.widget)
        self.verticalScrollBar.setObjectName(u"verticalScrollBar")
        self.verticalScrollBar.setGeometry(QRect(480, 40, 21, 181))
        self.verticalScrollBar.setOrientation(Qt.Vertical)
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u4e0b\u8f7d\u4efb\u52a1", None))
        self.widget.show()


class MyThread(QThread):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.pa = parent

    def run(self):
        self.pa.startDownload()


class TaskWidget(QWidget):
    def __init__(self, taskClient: TorrentClient, myProgressBar: QProgressBar, Mapp, parent=None):
        super().__init__(parent)
        self.taskClient = taskClient
        self.myProgressBar = myProgressBar
        self.pa = parent
        self.Mapp = Mapp

    def setProgressBar(self):
        self.myProgressBar.setValue(
            100 * (self.taskClient.piece_manager.have_pieces / self.taskClient.piece_manager.total_pieces))

    def startDownload(self):
        loop = QEventLoop(self.Mapp)
        asyncio.set_event_loop(loop)
        task = loop.create_task(self.taskClient.start())

        def signal_handler(*_):
            self.pa.textBrowser.append('Exiting, please wait until everything is shutdown...\n')
            self.taskClient.stop()
            task.cancel()

        signal.signal(signal.SIGINT, signal_handler)

        try:
            loop.run_until_complete(task)
        except CancelledError:
            self.pa.textBrowser.append('Event loop was canceled\n')
        '''
        try:
            self.taskClient.start()
        except CancelledError:
            self.pa.textBrowser.append('Event loop was canceled\n')
        '''


class Ui_MainWindow(object):
    def setupUi(self, MainWindow, app):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(575, 515)
        self.app = app
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setGeometry(QRect(0, 0, 571, 491))
        self.tab_1 = QWidget()
        self.tab_1.setObjectName(u"tab_1")
        self.textEdit = QTextEdit(self.tab_1)
        self.textEdit.setObjectName(u"textEdit")
        self.textEdit.setGeometry(QRect(0, 0, 171, 101))
        self.pushButton = MyTorrentButton(self.textEdit, self.tab_1)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setGeometry(QRect(170, 80, 75, 21))
        self.pushButton.clicked.connect(self.pushButton.pushed)
        self.tabWidget.addTab(self.tab_1, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.tabWidget.addTab(self.tab_2, "")
        self.tab_3 = MyDownloadWidget(self.app)
        self.tab_3.setObjectName(u"tab_3")
        self.textEdit_2 = QTextEdit(self.tab_3)
        self.textEdit_2.setObjectName(u"textEdit_2")
        self.textEdit_2.setGeometry(QRect(0, 0, 561, 91))
        self.pushButton_2 = MyButton(self.textEdit_2, self.tab_3)
        self.pushButton_2.setObjectName(u"pushButton_2")
        self.pushButton_2.setGeometry(QRect(440, 60, 111, 23))
        self.pushButton_2.clicked.connect(self.pushButton_2.pushed)

        self.tabWidget.addTab(self.tab_3, "")

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 575, 22))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(2)

        QMetaObject.connectSlotsByName(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("Bittorrent", u"Bittorrent", None))
        self.pushButton.setText(QCoreApplication.translate("MainWindow", u"\u786e\u8ba4\u4e0a\u4f20", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_1),
                                  QCoreApplication.translate("MainWindow", u"\u505a\u79cd\u5b50", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2),
                                  QCoreApplication.translate("MainWindow", u"\u4e0a\u4f20\u4efb\u52a1", None))
        self.textEdit_2.setDocumentTitle("")
        self.textEdit_2.setHtml(QCoreApplication.translate("MainWindow",
                                                           u"<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
                                                           "<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
                                                           "p, li { white-space: pre-wrap; }\n"
                                                           "</style></head><body style=\" font-family:'SimSun'; font-size:9pt; font-weight:400; font-style:normal;\">\n"
                                                           "<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p></body></html>",
                                                           None))
        self.pushButton_2.setText(QCoreApplication.translate("MainWindow", u"\u67e5\u8be2\u79cd\u5b50...", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3),
                                  QCoreApplication.translate("MainWindow", u"\u4e0b\u8f7d\u4efb\u52a1", None))
    # retranslateUi
