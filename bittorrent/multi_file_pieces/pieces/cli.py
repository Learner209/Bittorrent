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
import os

from concurrent.futures import CancelledError
from pieces.magnet2torrent import magnet2torrent
from pieces.torrent import Torrent
from pieces.client import TorrentClient


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
        default="False",
        help="Whether to use the optimistic unchoking strategy.",
    )

    parser.add_argument(
        "-a",
        "--anti-snubbing",
        action='store_true',
        default="False",
        help="Whether to use the anti-snubbing strategy.",
    )

    parser.add_argument(
        "-c",
        "--choking-strategy",
        action='store_true',
        default="False",
        help="Whether to use the choking strategy.",
    )
    
    parser.add_argument(
        "-e",
        "--end-game-mode",
        action='store_true',
        default="False",
        help="Whether to use the End-game optimization.",
    )

    parser.add_argument(
        "-r",
        "--rarest-piece-first",
        action='store_true',
        default="False",
        help="Whether to use the rarest piece first strategy.",
    )

    parser.add_argument(
        "-b",
        "--bbs-plus",
        action='store_true',
        default="False",
        help="Whether to enable bbs plus optimization (May lead to network congestion and bandwidth waste).",
    )

    parser.add_argument(
        "-p",
        "--port",
        help="The port that the local DHT node is listening from.",
    )

    parser.add_argument(
        "-d",
        "--dht",
        help="Whether use DHT(Distributed Hash Table) extension.",
    )
    

    args = parser.parse_args()
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

    loop = asyncio.get_event_loop()

    client = TorrentClient(
                torrent = Torrent(args.torrent),
                enable_optimistic_unchoking = True if args.optimistic_unchoking == True else False,
                enable_anti_snubbing = True if args.anti_snubbing == True else False,
                enable_choking_strategy = True if args.choking_strategy == True else False,
                enable_end_game_mode = True if args.end_game_mode == True else False,
                enable_rarest_piece_first = True if args.rarest_piece_first == True else False,
                enable_bbs_plus= True if args.bbs_plus == True else False,
                enabel_dht_network=True if args.dht == True else False
                )
    

    task = loop.create_task(client.start(port=int(args.port) if isinstance(int(args.port), int) else None))

    def signal_handler(*_):
        logging.info('Exiting, please wait until everything is shutdown...')
        client.stop()
        task.cancel()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        loop.run_until_complete(task)
    except CancelledError:
        logging.warning('Event loop was canceled')


