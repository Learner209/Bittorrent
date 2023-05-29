#
# pieces - An experimental BitTorrent client
#
# Copyright 2016 markus.eliasson@gmail.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import asyncio
import signal
import logging

from concurrent.futures import CancelledError

from pieces.torrent import Torrent
from pieces.client import TorrentClient

# Form implementation generated from reading ui file 'connect_me.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!
# 导入程序运行必须模块
# PyQt5中使用的基本控件都在PyQt5.QtWidgets模块中
import sys
from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QProgressBar
from UI.ui_ClientUI import Ui_MainWindow


class MyMainForm(QMainWindow, Ui_MainWindow):
    def __init__(self, app, parent=None):
        super(MyMainForm, self).__init__(parent)
        self.setupUi(self, app)


def loadUI():
    # 固定的，PyQt5程序都需要QApplication对象。sys.argv是命令行参数列表，确保程序可以双击运行
    app = QApplication(sys.argv)
    # 初始化
    myWin = MyMainForm(app)
    # 将窗口控件显示在屏幕上
    myWin.show()
    return app, myWin


def main():
    app, myWin = loadUI()

    parser = argparse.ArgumentParser()
    parser.add_argument('torrent',
                        help='the .torrent to download')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='enable verbose output')

    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(filename='logfile.log', level=logging.INFO)

    loop = asyncio.get_event_loop()
    client = TorrentClient(Torrent(args.torrent), myWin)
    task = loop.create_task(client.start())

    def signal_handler(*_):
        logging.info('Exiting, please wait until everything is shutdown...')
        client.stop()
        task.cancel()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        loop.run_until_complete(task)
    except CancelledError:
        logging.warning('Event loop was canceled')

    # 程序运行，sys.exit方法确保程序完整退出。
    sys.exit(app.exec_())
