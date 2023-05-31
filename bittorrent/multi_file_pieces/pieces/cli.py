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
import time
import logging
import os
import threading

from concurrent.futures import CancelledError
from pieces.magnet2torrent import magnet2torrent
from pieces.torrent import Torrent
from pieces.client import TorrentClient
from pieces.tkinter_gui.gui import App

def main():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    log = logging.getLogger('kademlia')
    log.addHandler(handler)


    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )


    parser.add_argument('-t', '--torrent',
                        help='the .torrent to download')
    
    parser.add_argument('-m', '--magnet-link',
                        help='the magnet link url to download')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='enable verbose output')
    
    parser.add_argument(
        "-o",
        "--optimistic-unchoking",
        action='store_true',
        default=False,
        help="Whether to use the optimistic unchoking strategy.",
    )

    parser.add_argument(
        "-a",
        "--anti-snubbing",
        action='store_true',
        default=False,
        help="Whether to use the anti-snubbing strategy.",
    )

    parser.add_argument(
        "-c",
        "--choking-strategy",
        action='store_true',
        default=False,
        help="Whether to use the choking strategy.",
    )
    
    parser.add_argument(
        "-e",
        "--end-game-mode",
        action='store_true',
        default=False,
        help="Whether to use the End-game optimization.",
    )

    parser.add_argument(
        "-r",
        "--rarest-piece-first",
        action='store_true',
        default=False,
        help="Whether to use the rarest piece first strategy.",
    )

    parser.add_argument(
        "-b",
        "--bbs-plus",
        action='store_true',
        default=False,
        help="Whether to enable bbs plus optimization (May lead to network congestion and bandwidth waste).",
    )

    parser.add_argument(
        "-p",
        "--port",
        default=None,
        help="The port that the local DHT node is listening from.",
    )

    parser.add_argument(
        "-d",
        "--dht",
        action='store_true',
        default=False,
        help="Whether use DHT(Distributed Hash Table) extension.",
    )
    
    parser.add_argument(
        "-g",
        "--gui",
        action='store_true',
        default=False,
        help="Whether to use the graphical application",
    )

    args = parser.parse_args()
    
    if args.gui:
            
        app = App(
            enable_optimistic_unchoking = False,
            enable_anti_snubbing = False,
            enable_choking_strategy = False,
            enable_end_game_mode = False,
            enable_rarest_piece_first = False,
            enable_bbs_plus= False,
            enabel_dht_network=False
        )
        def _(app):
            #print(2)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            while True:
                time.sleep(3)
                if app.torrent_client_mode:
                    # print(torrent_path)
                    
                    torrent_path = app.entry.get()
                    if isinstance(torrent_path, str) and torrent_path.startswith('magnet'):
                        filename = magnet2torrent(mag_link=torrent_path)
                        current_dir = os.path.dirname(__file__)
                        torrent_path = os.path.join(current_dir, filename)
                        logging.info("The path of the torrent file from the magnet link url is: {path}"\
                                    .format(path = torrent_path))
                        app.add_text("The path of the torrent file from the magnet link url is: {path}"\
                                    .format(path = torrent_path))

                    if isinstance(torrent_path, str) and os.path.exists(torrent_path) and torrent_path.endswith('.torrent'):
                     
                        client = TorrentClient(
                                    torrent = Torrent(torrent_path),
                                    enable_optimistic_unchoking = True if app.checkbox_1.get() == 1 else False,
                                    enable_anti_snubbing = app.checkbox_2.get(),
                                    enable_choking_strategy = app.checkbox_1.get(),
                                    enable_end_game_mode = app.checkbox_4.get(),
                                    enable_rarest_piece_first = app.checkbox_3.get(),
                                    enable_bbs_plus= app.checkbox_5.get(),
                                    enabel_dht_network=app.checkbox_6.get(),
                                    app = app
                                    )
                        
                        app.add_text("The optimistic-unchoking strategy: {}\n \
                                        The anti-snubbing strategy: {} \n \
                                        The choking strategy: {}\n \
                                        The end-game strategy:{}\n \
                                        The rarset piece frist strategy:{}\n \
                                        The bbs-plus optimzation:{} \n \
                                        The DHT network registration:{}"
                                        .format("On" if app.checkbox_1.get() else "Off",
                                                "On" if app.checkbox_2.get() else "Off",
                                                "On" if app.checkbox_1.get() else "Off",
                                                "On" if app.checkbox_4.get() else "Off",
                                                "On" if app.checkbox_3.get() else "Off",
                                                "On" if app.checkbox_5.get() else "Off",
                                                "On" if app.checkbox_6.get() else "Off"))
                        
                        task = loop.create_task(client.start(port=None))

                        try:
                            loop.run_until_complete(task)
                        except CancelledError:
                            logging.warning('Event loop was canceled')
                            break
                        except Exception:
                            break
                    else:
                        app.add_text("The torrent path: {} is invalid. \n".format(app.entry.get()))
                        app.torrent_client_mode = False

        clientThread = threading.Thread(target=_, args=[app])
        clientThread.daemon = True
        clientThread.start()
        try:
            app.mainloop()
            
            # app.quit()
            clientThread.join()
        except Exception:
            app.quit()
            app.destroy()

    else:
        if args.verbose:
            logging.basicConfig(filename='logfile.log', level=logging.DEBUG)

        if args.magnet_link:
            filename = magnet2torrent(mag_link=args.magnet_link)
            current_dir = os.path.dirname(__file__)
            args.torrent = os.path.join(current_dir, filename)
            logging.info("The path of the torrent file from the magnet link url is: {path}"\
                        .format(path = args.torrent))

        logging.debug("The optimistic-unchoking strategy: {}\n \
                    The anti-snubbing strategy: {} \n \
                    The choking strategy: {}\n \
                    The end-game strategy:{}\n \
                    The rarset piece frist strategy:{}\n \
                    The bbs-plus optimzation:{} \n \
                    The DHT network registration:{}"
                    .format("On" if args.optimistic_unchoking == True else "Off",
                            "On" if args.anti_snubbing == True else "Off",
                            "On" if args.choking_strategy == True else "Off",
                            "On" if args.end_game_mode == True else "Off",
                            "On" if args.rarest_piece_first == True else "Off",
                            "On" if args.bbs_plus == True else "Off",
                            "On" if args.dht == True else "Off"))
        logging.warning("Not implemnted yet...")

    
            
