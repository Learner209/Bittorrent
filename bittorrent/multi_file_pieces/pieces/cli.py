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


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('torrent',
                        help='the .torrent to download')
    
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
    

    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(filename='logfile.log', level=logging.DEBUG)


    logging.debug("The optimistic-unchoking strategy: {}\n \
                  The anti-snubbing strategy: {} \n \
                  The choking strategy: {}\n \
                  The end-game strategy:{}\n \
                  The rarset piece frist strategy:{}\n \
                  The bbs-plus optimzation:{}"
                  .format("On" if args.optimistic_unchoking == True else "Off",
                          "On" if args.anti_snubbing == True else "Off",
                          "On" if args.choking_strategy == True else "Off",
                          "On" if args.end_game_mode == True else "Off",
                          "On" if args.rarest_piece_first == True else "Off",
                          "On" if args.bbs_plus == True else "Off"))

    loop = asyncio.get_event_loop()

    client = TorrentClient(
                torrent = Torrent(args.torrent),
                enable_optimistic_unchoking = True if args.optimistic_unchoking == True else False,
                enable_anti_snubbing = True if args.anti_snubbing == True else False,
                enable_choking_strategy = True if args.choking_strategy == True else False,
                enable_end_game_mode = True if args.end_game_mode == True else False,
                enable_rarest_piece_first = True if args.rarest_piece_first == True else False,
                enable_bbs_plus= True if args.bbs_plus == True else False
                )
    


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
