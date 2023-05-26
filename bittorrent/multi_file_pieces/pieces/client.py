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

import random
import asyncio
import logging
import math
import os
import time
from asyncio import Queue
from collections import namedtuple, defaultdict
from hashlib import sha1
import bitstring
import threading
import time
from .kademlia.network import Server
from .httpstat import httpstat

from pieces.protocol import PeerConnection, REQUEST_SIZE
from pieces.tracker import Tracker

# The number of max peer connections per TorrentClient
MAX_PEER_CONNECTIONS = 40


class TorrentClient:
    """
    The torrent client is the local peer that holds peer-to-peer
    connections to download and upload pieces for a given torrent.

    Once started, the client makes periodic announce calls to the tracker
    registered in the torrent meta-data. These calls results in a list of
    peers that should be tried in order to exchange pieces.

    Each received peer is kept in a queue that a pool of PeerConnection
    objects consume. There is a fix number of PeerConnections that can have
    a connection open to a peer. Since we are not creating expensive threads
    (or worse yet processes) we can create them all at once and they will
    be waiting until there is a peer to consume in the queue.
    """
    enable_DHT_network = None
    MAX_CONNECTION_KEEP_ALIVE_TIME = 120 # 2 minutes
    def __init__(self,
                torrent,
                enable_optimistic_unchoking,
                enable_anti_snubbing,
                enable_choking_strategy,
                enable_end_game_mode,
                enable_rarest_piece_first,
                enable_bbs_plus,
                enabel_dht_network
                ):
        
        self.tracker = Tracker(torrent)
        # The list of potential peers is the work queue, consumed by the
        # PeerConnections
        self.available_peers = Queue()
        # The list of peers is the list of workers that *might* be connected
        # to a peer. Else they are waiting to consume new remote peers from
        # the `available_peers` queue. These are our workers!
        self.peers = []
        # The piece manager implements the strategy on which pieces to
        # request, as well as the logic to persist received pieces to disk.

        # self.DHTserver = Server()
        
        self.DHTthread = None
        TorrentClient.enable_DHT_network = enabel_dht_network
        self.piece_manager = PieceManager(
                    torrent,
                    enable_end_game_mode= enable_end_game_mode,
                    enable_rarest_piece_first = enable_rarest_piece_first,
                    enable_bbs_plus=enable_bbs_plus
            )
        
        self.peer_connection_manager = PeerConnectionManager(available_peers = self.available_peers, 
                enable_optimistic_unchoking = enable_optimistic_unchoking,
                enable_anti_snubbing = enable_anti_snubbing,
                enable_choking_strategy = enable_choking_strategy,
                enable_end_game_mode = enable_end_game_mode,
            )
        
        
        self.abort = False



    async def start(self, port = None):
        """
        Start downloading the torrent held by this client.

        This results in connecting to the tracker to retrieve the list of
        peers to communicate with. Once the torrent is fully downloaded or
        if the download is aborted this method will complete.
        """
        self.peers = [PeerConnection(self.available_peers,
                                    self.tracker.torrent.info_hash,
                                    self.tracker.peer_id,
                                    self.piece_manager,
                                    peer_connection_manager = self.peer_connection_manager,
                                    on_block_cb= self._on_block_retrieved,
                                    read_request_retrieved = self._read_request_retrieved
                                    )
                        for _ in range(MAX_PEER_CONNECTIONS)]

        # The time we last made an announce call (timestamp)
        previous = None
        # Default interval between announce calls (in seconds)
        interval = 30*60

        while True:
            if self.piece_manager.complete:
                self.piece_manager._organize_files()
                logging.info('Torrent fully downloaded!')
                break
            if self.abort:
                logging.info('Aborting download...')
                break

            current = time.time()
            if (not previous) or (previous + interval < current):
                response = await self.tracker.connect(
                    first=previous if previous else False,
                    uploaded=self.piece_manager.bytes_uploaded,
                    downloaded=self.piece_manager.bytes_downloaded)

                # logging.debug(response)
                if response:
                    previous = current
                    interval = response.interval
                    self._empty_queue()
                    for peer in response.peers:
                        self.available_peers.put_nowait(peer)

                    # asyncio.run(self.DHTserver.connect_to_bootstrap_node(
                    #     args=response.peers,
                    #     server=self.DHTserver
                    # ))

                    if self.DHTthread is None and TorrentClient.enable_DHT_network:
                        self.DHTthread = threading.Thread(target= Server,
                                                        args=(response.peers, 
                                                              port,
                                                              self.tracker.torrent.info_hash))
                    elif self.DHTthread is not None:
                        self.DHTthread.join()
                    # self.DHTserver.connect_to_bootstrap_node(
                    #     args = response.peers,
                    #     server = self.DHTserver
                    # )
                    if TorrentClient.enable_DHT_network:
                        self.DHTthread.daemon = True
                        self.DHTthread.start()

                    
            else:
                await asyncio.sleep(5)
        await self.stop()


    def _empty_queue(self):
        while not self.available_peers.empty():
            self.available_peers.get_nowait()

    async def stop(self):
        """
        Stop the download or seeding process. 
        (But we can still wait for others's INTERESTED or REQUEST message)
        """
        
        logging.debug("Waiting for other peers's INTERESTED or REQUEST messages for {} seconds"
                      .format(TorrentClient.MAX_CONNECTION_KEEP_ALIVE_TIME))
        await asyncio.sleep(TorrentClient.MAX_CONNECTION_KEEP_ALIVE_TIME)
        self.abort = True
        for peer in self.peers:
            peer.stop()
        self.piece_manager.close()
        await self.tracker.close()
        self.peer_connection_manager.close()

    def _on_block_retrieved(self, peer_id, piece_index, block_offset, data, enable_end_game_mode = False):
        """
        Callback function called by the `PeerConnection` when a block is
        retrieved from a peer.

        :param peer_id: The id of the peer the block was retrieved from
        :param piece_index: The piece index this block is a part of
        :param block_offset: The block offset within its piece
        :param data: The binary data retrieved
        """
       
        return self.piece_manager.block_received(
            peer_id=peer_id,
            piece_index=piece_index,
            block_offset=block_offset,
            data=data,
            enable_end_game_mode = enable_end_game_mode)

    def _read_request_retrieved(self, peer_id, piece_index, block_offset_within_a_piece, requested_data_length):
        """
        Callback function called by the `PeerConnection` when a request from a peer need a portion of the file

        :param peer_id: The id of the peer the block was retrieved from
        :param piece_index: The piece index this block is a part of
        :param block_offset: The block offset within its piece
        :param data: The binary data retrieved
        """
        return self.piece_manager.read_request(
            peer_id=peer_id, piece_index=piece_index,
            block_offset_within_a_piece=block_offset_within_a_piece, required_data_length=requested_data_length)

class Block:
    """
    The block is a partial piece, this is what is requested and transferred
    between peers.

    A block is most often of the same size as the REQUEST_SIZE, except for the
    final block which might (most likely) is smaller than REQUEST_SIZE.
    """
    Missing = 0
    Pending = 1
    Retrieved = 2

    def __init__(self, piece: int, offset: int, length: int):
        self.piece = piece
        self.offset = offset
        self.length = length
        self.status = Block.Missing
        self.data = None

class PeerConnectionManager:
    """
    Peer Connection Manager is primraily used to implement the choking and the optimistic unchoking
    It monitnors each channel of the established peer connection
    And control the opening and close of every peer connection
    """
    Unchoked = 0
    Choked = 1

    enable_anti_snubbing = None
    enable_choking_strategy = None
    enable_optimistic_unchoking = None
    enable_end_game_mode = None
    in_end_game_mode = False

    def __init__(self,
                available_peers, 
                enable_optimistic_unchoking,
                enable_anti_snubbing,
                enable_choking_strategy,
                enable_end_game_mode,
                ) -> None:
        self.avaiable_peers = available_peers
        self.peer_connection_pool = {}
        self.peer_connection_bandwidth = {}
        self.choked_peers = []
        self.unchoked_peers = []
        self.choking_timing = time.time()
        self.optimistic_unchoking_timing = time.time()
        self.num_of_registered_peer_connections = 0
        self.choking_test_interval = 10
        self.optimistic_unchoking_interval = 30
        self.num_of_peer_connection_bandwidth_test_made = 0
        self.num_of_opt_unchoking_queries_made = 0
        self.optimistic_unchoking_random_choice = 0
        self.blocks_already_sent = {}
 
        
        PeerConnectionManager.enable_optimistic_unchoking = enable_optimistic_unchoking
        PeerConnectionManager.enable_anti_snubbing = enable_anti_snubbing
        PeerConnectionManager.enable_choking_strategy = enable_choking_strategy
        PeerConnectionManager.enable_end_game_mode = enable_end_game_mode
        

        self.thread = threading.Thread(target=self._optimistic_unchoking_choice, args=()) 
        self.thread.daemon = True
        self.thread.start()



    def close(self):
        self.thread.join()

    def _optimistic_unchoking_choice(self):
        if not PeerConnectionManager.enable_optimistic_unchoking or PeerConnectionManager.in_end_game_mode:
            return
        while True:
            if self.num_of_registered_peer_connections < 3 or len(self.choked_peers) < 2:
                # logging.debug("The length of the peer connections are {len1} and the choked peers length are {len2}"
                #               .format(len1 = self.num_of_registered_peer_connections, len2 = len(self.choked_peers)))
                time.sleep(15)
                continue

            self.optimistic_unchoking_random_choice = \
            self.choked_peers[random.randint(1,len(self.choked_peers))-1]
            
            self.optimistic_unchoking_timing = time.time()
            self.num_of_opt_unchoking_queries_made = 0
            
            self.peer_connection_pool[self.optimistic_unchoking_random_choice].restart()
            self.choked_peers.remove(self.optimistic_unchoking_random_choice)
            self.unchoked_peers.append(self.optimistic_unchoking_random_choice)

            logging.debug("We have chosen the optimstic unchoking objective: {}"
                        .format(self.optimistic_unchoking_random_choice))
            time.sleep(30)

    def anti_snubbing_startegy(self, peer_id):
        """
        
        Accoding to the spec: BitTorrent assumes it is "snubbed" by that peer and doesn't upload to it except as an optimistic unchoke.
        This frequently results in more than one concurrent optimistic unchoke,
        """
        if not PeerConnectionManager.enable_anti_snubbing or PeerConnectionManager.in_end_game_mode:
            return
        logging.debug("The peer with id {} has been snubbing me ".format(peer_id))
        #logging.debug("The peer with peer id {id} have been snugging on us. So remove it.".format(id = peer_id))
        self.peer_connection_pool[peer_id].stop()
        self.unchoked_peers.remove(peer_id)
        self.choked_peers.append(peer_id)
        ## More than one concurrent optimistic unchoke 
        if len(self.choked_peers) > 1:
            self.optimistic_unchoking_random_choice = \
            self.choked_peers[random.randint(1,len(self.choked_peers))-1]
            
            self.optimistic_unchoking_timing = time.time()
            self.num_of_opt_unchoking_queries_made = 0
            
            self.peer_connection_pool[self.optimistic_unchoking_random_choice].restart()
            self.choked_peers.remove(self.optimistic_unchoking_random_choice)
            self.unchoked_peers.append(self.optimistic_unchoking_random_choice)

            logging.debug("The anti-snugging strategy have chosen {} to be the concurrent optimistic unchoke"
                        .format(self.optimistic_unchoking_random_choice))



    def update_peer_connection_pool(self, peer_id, peer_connection):
        if peer_id not in self.peer_connection_pool.keys():
            self.peer_connection_pool[peer_id] = peer_connection
            self.peer_connection_bandwidth[peer_id] = 1
            self.num_of_registered_peer_connections += 1
            self.blocks_already_sent[peer_id] = 0
            self.unchoked_peers.append(peer_id)
            # logging.debug("Peer with peer id :{id}  have successfully entered the process".format(id=peer_id))
        
    def unregister_peer_connection(self, peer_id):
        if peer_id in self.peer_connection_pool.keys():
            del self.peer_connection_pool[peer_id]
            del self.peer_connection_bandwidth[peer_id]
            del self.blocks_already_sent[peer_id]
            if peer_id in self.unchoked_peers:
                self.unchoked_peers.remove(peer_id)
            if peer_id in self.choked_peers:
                self.choked_peers.remove(peer_id)
            self.num_of_registered_peer_connections -= 1
    
    def set_end_game_mode(self):
        if not PeerConnectionManager.in_end_game_mode:
            PeerConnectionManager.in_end_game_mode = True
        for choked_peer in self.choked_peers:
            self.peer_connection_pool[choked_peer].restart()
            self.unchoked_peers.append(choked_peer)
            self.choked_peers.remove(choked_peer)

    def peer_connection_bandwidth_test(self, peer_id, peer_ip_port, enable_end_game_mode):
        """
        Reciprocation and number of uploads capping is managed by 
        unchoking the four peers which have the best upload rate and are interested.
          This maximizes the client's download rate. 
          These four peers are referred to as downloaders, 
          because they are interested in downloading from the client."
        """
        if not PeerConnectionManager.enable_choking_strategy or PeerConnectionManager.in_end_game_mode:
            return None
        # bandwidth = httpstat.httpstat_test(
        #     server_ip= peer_ip_port.ip,
        #     server_port= peer_ip_port.port
        # )
        bandwidth = self.blocks_already_sent[peer_id] / max(list(self.blocks_already_sent.values()))
        bandwidth *= 14
        # logging.debug("We have test the peer:{ip}:{port}, its bandwidth is {bandwidth}"
        #                 .format(ip = peer_ip_port.ip, port = peer_ip_port.port, bandwidth = bandwidth))
        
        self.peer_connection_bandwidth[peer_id] = bandwidth

        self.num_of_peer_connection_bandwidth_test_made += 1

        # logging.debug("The registered peer are {peers} The bandwidth tests are {u}".format(peers=self.num_of_registered_peer_connections,
        #                       u=self.num_of_peer_connection_bandwidth_test_made))
        if self.num_of_peer_connection_bandwidth_test_made == \
            self.num_of_registered_peer_connections:
                ## Determine the first four faster channels
                logging.debug("We have successfully tested the bandwidth of every peer: {bandwidth} and their lengths are: {length}"
                              .format(bandwidth= list(self.peer_connection_bandwidth.values()), length = self.num_of_registered_peer_connections))
                
                peers_to_be_choked = sorted(self.peer_connection_bandwidth,
                                                        key=lambda x:self.peer_connection_bandwidth[x], reverse=True)
                counter = 0
                for peer_id in peers_to_be_choked:
                    if counter < (4,self.num_of_registered_peer_connections)[enable_end_game_mode]: # self.num_of_registered_peer_connections:
                        logging.debug("The peer id {id} has been reserved for unchoking".format(id = peer_id))
                        if peer_id in self.choked_peers:
                            self.peer_connection_pool[peer_id].restart()
                            self.choked_peers.remove(peer_id)
                            self.unchoked_peers.append(peer_id)
                    
                        counter += 1
                    else:
                        if peer_id in self.unchoked_peers:
                            self.peer_connection_pool[peer_id].stop()
                            self.unchoked_peers.remove(peer_id)
                            self.choked_peers.append(peer_id)

                # for peer_id in list(self.peer_connection_pool.keys()):
                #     logging.debug("The peer id {id} with {bandwidth} has been suspended".format(id = peer_id,bandwidth=self.peer_connection_bandwidth[peer_id]))
                #     self.peer_connection_pool[peer_id].restart()

                for key in self.blocks_already_sent.keys():
                    self.blocks_already_sent[key] = 0

                self.choking_timing = time.time()
                self.num_of_peer_connection_bandwidth_test_made = 0
        
        return bandwidth

    



class Piece:
    """
    The piece is a part of of the torrents content. Each piece except the final
    piece for a torrent has the same length (the final piece might be shorter).

    A piece is what is defined in the torrent meta-data. However, when sharing
    data between peers a smaller unit is used - this smaller piece is refereed
    to as `Block` by the unofficial specification (the official specification
    uses piece for this one as well, which is slightly confusing).
    """
    def __init__(self, index: int, blocks: [], hash_value):
        self.index = index
        self.blocks = blocks
        self.hash = hash_value

    def reset(self):
        """
        Reset all blocks to Missing regardless of current state.
        """
        for block in self.blocks:
            block.status = Block.Missing

    def next_request(self) -> Block:
        """
        Get the next Block to be requested(Implemented to find the first missing block)
        """
        missing = [b for b in self.blocks if b.status is Block.Missing]
        if missing:
            missing[0].status = Block.Pending
            return missing[0]
        return None
    
    def remaining_missing_blocks_in_piece(self):
        """
        Get all the remaining blocks to be requested in this piece.
        And all the remaining blocks are set to be Pneding state afterwards
        """
        missing_blocks = [b for b in self.blocks if b.status is Block.Missing]
        if missing_blocks:
            for missing_block in missing_blocks:
                missing_block.status = Block.Pending
            return missing_blocks
        # logging.debug("All the remaining blocks to be requested in this piece are of length {}"
        #               .format(len(missing_blocks)))
        return []
    
    def remaining_pending_and_missing_blocks_in_piece(self):
        """
        Get all the remaining blocks that are pending or missing in this piece.
        """
        pending_or_missing_blocks = [b for b in self.blocks if b.status in [Block.Missing, Block.Pending]]
        if pending_or_missing_blocks:
            for pending_or_missing_block in pending_or_missing_blocks:
                pending_or_missing_block.status = Block.Pending
            return pending_or_missing_blocks
        # logging.debug("All the remaining blocks to be requested in this piece are of length {}"
        #               .format(len(missing_blocks)))
        return []
    
    def block_received(self, offset: int, data: bytes):
        """
        Update block information that the given block is now received

        :param offset: The block offset (within the piece)
        :param data: The block data
        """
        matches = [b for b in self.blocks if b.offset == offset]
        block = matches[0] if matches else None
        if block:
            block.status = Block.Retrieved
            block.data = data
            return block
        else:
            logging.warning('Trying to complete a non-existing block {offset}'
                            .format(offset=offset))
            return None

    def is_complete(self) -> bool:
        """
        Checks if all blocks for this piece is retrieved (regardless of SHA1)

        :return: True or False
        """
        blocks = [b for b in self.blocks if b.status is not Block.Retrieved]
        return len(blocks) == 0

    def is_hash_matching(self):
        """
        Check if a SHA1 hash for all the received blocks match the piece hash
        from the torrent meta-info.

        :return: True or False
        """
        piece_hash = sha1(self.data).digest()
        return self.hash == piece_hash

    @property
    def data(self):
        """
        Return the data for this piece (by concatenating all blocks in order)

        NOTE: This method does not control that all blocks are valid or even
        existing!
        """
        retrieved = sorted(self.blocks, key=lambda b: b.offset)
        blocks_data = [b.data for b in retrieved]
        return b''.join(blocks_data)

    def __str__(self) -> str:
        return """
        piece_index: {piece_index} \n 
        blocks: {blocks} \n
        hash_value: {hash_value}
        """.format(piece_index = self.index, hash_value = self.hash,
                   blocks = list(map(lambda x: 'offset: {offset} status: {status} \n'
                                     .format(offset = x.offset, status = x.status), self.blocks)))

class PieceManager:
    """
    The PieceManager is responsible for keeping track of all the available
    pieces for the connected peers as well as the pieces we have available for
    other peers.

    The strategy on which piece to request is made as simple as possible in
    this implementation.
    """
    enable_end_game_mode = None
    enable_rarest_piece_first = None
    enable_bbs_plus = None

    def __init__(self, torrent, 
                enable_end_game_mode = False,
                enable_rarest_piece_first = False,
                enable_bbs_plus = False):
        
        self.torrent = torrent
        self.peers = {}
        self.pending_blocks = []
        self.missing_pieces = []
        self.ongoing_pieces = []
        self.have_pieces = []
        self.max_pending_time = 300 * 1000  # 5 minutes
        self.missing_pieces = self._initiate_pieces()
        self.total_pieces = len(torrent.pieces)
        self.end_game_mode_request = {}
        self.end_game_cancelled = {}
        self.fd = os.open(self.torrent.output_file,  os.O_RDWR | os.O_CREAT)

        PieceManager.enable_end_game_mode = enable_end_game_mode
        PieceManager.enable_rarest_piece_first = enable_rarest_piece_first
        PieceManager.enable_bbs_plus = enable_bbs_plus

    def _initiate_pieces(self) -> [Piece]:
        """
        Pre-construct the list of pieces and blocks based on the number of
        pieces and request size for this torrent.
        """
        torrent = self.torrent
        pieces = []
        total_pieces = len(torrent.pieces)
        logging.debug("Total number of the pieces are {0}".format(total_pieces))
        std_piece_blocks = math.ceil(torrent.piece_length / REQUEST_SIZE)

        for index, hash_value in enumerate(torrent.pieces):
            # The number of blocks for each piece can be calculated using the
            # request size as divisor for the piece length.
            # The final piece however, will most likely have fewer blocks
            # than 'regular' pieces, and that final block might be smaller
            # then the other blocks.
            if index < (total_pieces - 1):
                blocks = [Block(index, offset * REQUEST_SIZE, REQUEST_SIZE)
                          for offset in range(std_piece_blocks)]
            else:
                last_length = torrent.total_size % torrent.piece_length
                num_blocks = math.ceil(last_length / REQUEST_SIZE)
                blocks = [Block(index, offset * REQUEST_SIZE, REQUEST_SIZE)
                          for offset in range(num_blocks)]

                if last_length % REQUEST_SIZE > 0:
                    # Last block of the last piece might be smaller than
                    # the ordinary request size.
                    last_block = blocks[-1]
                    last_block.length = last_length % REQUEST_SIZE
                    blocks[-1] = last_block
            pieces.append(Piece(index, blocks, hash_value))
        return pieces

    def close(self):
        """
        Close any resources used by the PieceManager (such as open files)
        """
        if self.fd:
            os.close(self.fd)

    @property
    def complete(self):
        """
        Checks whether or not the all pieces are downloaded for this torrent.

        :return: True if all pieces are fully downloaded else False
        """
        return len(self.have_pieces) == self.total_pieces

    @property
    def bytes_downloaded(self) -> int:
        """
        Get the number of bytes downloaded.

        This method Only counts full, verified, pieces, not single blocks.
        """
        return len(self.have_pieces) * self.torrent.piece_length

    @property
    def bytes_uploaded(self) -> int:
        # TODO Add support for sending data
        return 0

    def add_peer_without_bitfield(self, peer_id):
        """ 
        Adds a peer without requiring a bitfield(Note sending a bitfield is optional.).
        """
        bitfield = bitstring.BitArray(int=0, length=self.total_pieces)
        self.peers[peer_id] = bitfield

    def add_peer(self, peer_id, bitfield):
        """
        Adds a peer and the bitfield representing the pieces the peer has.
        """
        self.peers[peer_id] = bitfield

    def update_peer(self, peer_id, index: int):
        """
        Updates the information about which pieces a peer has (reflects a Have
        message).
        """
        if peer_id in self.peers:
            self.peers[peer_id][index] = 1

    def remove_peer(self, peer_id):
        """
        Tries to remove a previously added peer (e.g. used if a peer connection
        is dropped)
        """
        if peer_id in self.peers:
            del self.peers[peer_id]

    def next_request(self, peer_id) -> Block:
        """
        Get the next Block that should be requested from the given peer.

        If there are no more blocks left to retrieve or if this peer does not
        have any of the missing pieces None is returned
        """
        # The algorithm implemented for which piece to retrieve is a simple
        # one. This should preferably be replaced with an implementation of
        # "rarest-piece-first" algorithm instead.
        #
        # The algorithm tries to download the pieces in sequence and will try
        # to finish started pieces before starting with new pieces.
        #
        # 1. Check any pending blocks to see if any request should be reissued
        #    due to timeout
        # 2. Check the ongoing pieces to get the next block to request
        # 3. Check if this peer have any of the missing pieces not yet started
        if peer_id not in self.peers:
            return None

        block = self._expired_requests(peer_id)
        if not block:
            block = self._next_ongoing(peer_id)
            if not block:
                piece = self._get_rarest_piece(peer_id)
                if piece == None:
                    return None
                else:
                    block = piece.next_request()
        return block

    def blocks_requests_to_be_cancelled(self, block_received, block_received_from_peer_id):
        """
       Get all the prev. requested blocks that have already been requested to prepare
       for a cancellation message
        """
        for peer_id in self.peers:
            if peer_id in self.end_game_mode_request.keys():
                if block_received in self.end_game_mode_request[peer_id]:
                    self.end_game_mode_request[peer_id].remove(block_received)

                    # logging.debug('Cancelling block in the domain of client {block} for piece {piece} '
                    #         'of {length} bytes from peer'.format(
                    #             piece=block_received.piece,
                    #             block=block_received.offset,
                    #             length=block_received.length,
                    #             ))
                    if peer_id != block_received_from_peer_id:
                        self.end_game_cancelled[peer_id].append(block_received)

    def next_request_in_end_game_mode(self, peer_id) -> Block:
        """
        Get the all blocks's information in End_Game mode

        If there are no more blocks left to retrieve or if this peer does not
        have any of the missing pieces None is returned
        """
        # The algorithm implemented for which piece to retrieve is a simple
        # one. This should preferably be replaced with an implementation of
        # "rarest-piece-first" algorithm instead.
        #
        # The algorithm tries to download the pieces in sequence and will try
        # to finish started pieces before starting with new pieces.
        #
        # 1. Check any pending blocks to see if any request should be reissued
        #    due to timeout
        # 2. Check the ongoing pieces to get all the remaining blovcks in the ongoing picecs
        # 3. Append any blocks in the left 
        if peer_id not in self.peers:
            return None

        ## Still perfect to call `self._expired_requests(peer_id)` because one block is transmitted at one time
        block_requests_in_end_game_mode = []

        expired_request_blocks = self._expired_requests(peer_id = peer_id, 
                                                    enable_end_game_mode= True)
        if expired_request_blocks:
            block_requests_in_end_game_mode += \
                expired_request_blocks
        
        block_requests_in_end_game_mode += \
            self._blocks_to_be_transmitted_in_ongoing_pieces(peer_id)
           
        # piece = self._get_rarest_piece(peer_id)

        for piece in self.missing_pieces:
            if piece is not None:

                self.ongoing_pieces.append(piece)
                self.missing_pieces.remove(piece)
                block_requests_in_end_game_mode += \
                    piece.blocks

        # if len(self.ongoing_pieces) == 1:
        #     logging.debug("All the blocks to be requested in end game mode are of {length}. \n \
        #                 and the ongoing pieces are of {ongoing}, the left unfinished: {left}, \n \
        #                    the unfinied piece: {complete}, \n \
        #                   the length of missing pieces: {missing}"
        #                 .format(length = len(block_requests_in_end_game_mode),
        #                         ongoing = len(self.ongoing_pieces),
        #                         left = self.ongoing_pieces[0].remaining_pending_and_missing_blocks_in_piece(),
        #                         complete = self.ongoing_pieces[0].is_complete(),
        #                         missing = len(self.missing_pieces)
        #                         ))
        
        for block_request_in_end_game_mode in block_requests_in_end_game_mode:
            assert(isinstance(block_request_in_end_game_mode, Block))


        self.end_game_mode_request[peer_id] = block_requests_in_end_game_mode
        ## Initialized end_game_cancelled_if_necessary
        if peer_id not in self.end_game_cancelled.keys():
            self.end_game_cancelled[peer_id] = []


        return block_requests_in_end_game_mode



    def block_received(self, peer_id, piece_index, block_offset, data, enable_end_game_mode = False):
        """
        This method must be called when a block has successfully been retrieved
        by a peer.

        Once a full piece have been retrieved, a SHA1 hash control is made. If
        the check fails all the pieces blocks are put back in missing state to
        be fetched again. If the hash succeeds the partial piece is written to
        disk and the piece is indicated as Have.
        """
        logging.debug('Received block {block_offset} for piece {piece_index} '
                      'from peer {peer_id}: in {mode}'.format(block_offset=block_offset,
                                                     piece_index=piece_index,
                                                     peer_id=peer_id,
                                                     mode = "End game mode" if enable_end_game_mode else "Normal mode"))


        # Remove from pending requests
        for index, request in enumerate(self.pending_blocks):
            if request['block'].piece == piece_index and \
               request['block'].offset == block_offset:
                del self.pending_blocks[index]
                break

        pieces = [p for p in self.ongoing_pieces if p.index == piece_index]
        piece = pieces[0] if pieces else None
        
        if piece:
            block_received = piece.block_received(block_offset, data)
            if enable_end_game_mode:
                self.blocks_requests_to_be_cancelled(
                    block_received=block_received,
                    block_received_from_peer_id = peer_id
                    )
            if piece.is_complete():
                if piece.is_hash_matching():
                    self._write(piece)
                    self.ongoing_pieces.remove(piece)
                    #logging.debug("Hayyah!")
                    self.have_pieces.append(piece)
                    complete = (self.total_pieces -
                                len(self.missing_pieces) -
                                len(self.ongoing_pieces))
                    logging.info(
                        '{complete} / {total} pieces downloaded {per:.3f} %'
                        .format(complete=complete,
                                total=self.total_pieces,
                                per=(complete/self.total_pieces)*100))
                    
                    if len(self.ongoing_pieces) == 1 and not self.ongoing_pieces[0].blocks:
                        self.have_pieces.append(self.ongoing_pieces[0])
                        self.ongoing_pieces.remove(self.ongoing_pieces[0])

                        assert(len(self.have_pieces) == self.total_pieces)
                        assert(len(self.missing_pieces) == 0)

                        logging.info(
                            '{total} / {total} pieces downloaded {per:.3f} %'
                            .format(total=self.total_pieces,
                                    per=100))
                        
                else:
                    logging.info('Discarding corrupt piece {index}'
                                 .format(index=piece.index))
                    piece.reset()
            return block_received
        else:
            ## missing_pieces = [p for p in self.missing_pieces if p.index == piece_index]
            having_pieces = [p for p in self.have_pieces if p.index == piece_index]
            if having_pieces:
                logging.debug("The piece we just received is in the already complete piece with index {piece_index}"
                                .format(piece_index = having_pieces[0].index))
            
            return None

    def read_request(self, peer_id, piece_index, block_offset_within_a_piece, required_data_length):
        """
        Read the file according to the Request

        :param piece_index: The zero based piece index
        :param block_offset_within_a_piece: The zero based offset within a piece
        :param required_data_length: The requested length of data (default 2^14)
        """
        pos = piece_index * self.torrent.piece_length + block_offset_within_a_piece
        os.lseek(self.fd, pos, os.SEEK_SET)
        read_out_data = os.read(self.fd, required_data_length)
        return read_out_data

    def _is_suitable_to_enter_the_end_game_mode(self, peer_id, end_game_mode):
        """
        When to enter end game mode is an area of discussion. 
        Some clients enter end game when all pieces have been requested.
        Others wait until the number of blocks left is lower than the number of blocks in transit, and no more than 20. 
        There seems to be agreement that it's a good idea to keep the number of pending blocks 
        low (1 or 2 blocks) to minimize the overhead, 
        and if you randomize the blocks requested, there's a lower chance of downloading duplicates. 
        """
        if PieceManager.enable_bbs_plus:
            return True
        if not PieceManager.enable_end_game_mode:
            return False

        # When all pieces have been requested.
        if end_game_mode == 1:
            if len(self.missing_pieces) == self.total_pieces:
                assert(len(self.ongoing_pieces) + len(self.have_pieces) == self.total_pieces)
                logging.debug("End game mode has been enabled because all {piece_length} pieces have all been requested"
                              .format(piece_length = self.total_pieces))
                return True
            else:
                return False
        elif end_game_mode == 2:
            numbers_of_blocks_left = numbers_of_blocks_in_transit = 0
            for missing_piece in self.missing_pieces:
                numbers_of_blocks_left += len(missing_piece.blocks)
            for ongoing_piece in self.ongoing_pieces:
                for block_in_ongoing_piece in ongoing_piece.blocks:
                    if block_in_ongoing_piece.status == Block.Missing:
                        numbers_of_blocks_left += 1
                    elif block_in_ongoing_piece.status == Block.Pending:
                        numbers_of_blocks_in_transit += 1

            if numbers_of_blocks_left < numbers_of_blocks_in_transit:
                logging.debug("End game mode has been enabled because there are {left} left blocks and {transit} blocks in transit"
                              .format(left = numbers_of_blocks_left, transit = numbers_of_blocks_in_transit))
                
            return True if numbers_of_blocks_left < numbers_of_blocks_in_transit else False
        else:
            logging.exception("Undefined End-Game mode {} has been chosen !".format(end_game_mode))

    def _expired_requests(self, peer_id, enable_end_game_mode = False) -> Block:
        """
        Go through previously requested blocks, if any one have been in the
        requested state for longer than `MAX_PENDING_TIME` return the block to
        be re-requested.

        If no pending blocks exist, None is returned
        """
        expired_request_blocks = []
        current = int(round(time.time() * 1000))
        for request in self.pending_blocks:
            if self.peers[peer_id][request['block'].piece]:
                if request['added'] + self.max_pending_time < current:
                    logging.info('Re-requesting block {block} for '
                                 'piece {piece}'.format(
                                    block=request['block'].offset,
                                    piece=request['block'].piece))
                    # Reset expiration timer
                    request['added'] = current
                    if not enable_end_game_mode:
                        return request['block']
                    expired_request_blocks.append(request['block'])
        return expired_request_blocks

    def _next_ongoing(self, peer_id) -> Block:
        """
        Go through the ongoing pieces and return the next block to be
        requested or None if no block is left to be requested.
        """
        for piece in self.ongoing_pieces:
            if self.peers[peer_id][piece.index]:
                # Is there any blocks left to request in this piece?
                block = piece.next_request()
                if block:
                    self.pending_blocks.append(
                        {'block':block, 'added':int(round(time.time()*1000))})
                    return block
        return None
    
    def _blocks_to_be_transmitted_in_ongoing_pieces(self, peer_id):
        """
        Go through the ongoing pieces and return all the remaining blocks to be
        requested or None if no block is left to be requested.
        DEBUG: return all the missing blocks that are in ongoing pieces, but not all the pending blocks in ongoing pieces.
        """
        blocks_to_be_transmitted_in_ongoing_pieces = []
        for piece in self.ongoing_pieces:
            if self.peers[peer_id][piece.index]:
   
                # remaining_blocks_in_piece = piece.remaining_missing_blocks_in_piece()
                ## Chooseing all the pendind and missing blocks in the ongonnig pieces
                remaining_blocks_in_piece = piece.remaining_pending_and_missing_blocks_in_piece()
                blocks_to_be_transmitted_in_ongoing_pieces += remaining_blocks_in_piece
                
                for remaining_block_in_piece in remaining_blocks_in_piece:
                    if remaining_block_in_piece.status == Block.Missing:
                        self.pending_blocks.append(
                            {'block':remaining_block_in_piece, 'added':int(round(time.time()*1000))})
                    ## Make sure every block in the pending blocks don;t conflict with each other

        # logging.debug("Blocks to be transmitted in {ongoing_pieces} are {len_blocks}"
        #               .format(ongoing_pieces = len(self.ongoing_pieces), 
        #                       len_blocks = len(blocks_to_be_transmitted_in_ongoing_pieces)))
        
        return blocks_to_be_transmitted_in_ongoing_pieces


    def _get_rarest_piece(self, peer_id):
        """
        Given the current list of missing pieces, get the
        rarest one first (i.e. a piece which fewest of its
        neighboring peers have)
        """
        if not PieceManager.enable_rarest_piece_first:
            return self.missing_pieces[random.randint(1, len(self.missing_pieces))-1]


        piece_count = defaultdict(int)
        for piece in self.missing_pieces:
            if not self.peers[peer_id][piece.index]:
                continue
            for p in self.peers:
                if self.peers[p][piece.index]:
                    piece_count[piece] += 1

        if len(piece_count) == 0:
            return None
        rarest_piece = min(piece_count, key=lambda p: piece_count[p])
        self.missing_pieces.remove(rarest_piece)
        self.ongoing_pieces.append(rarest_piece)
        return rarest_piece

    def _next_missing(self, peer_id) -> Block:
        """
        Go through the missing pieces and return the next block to request
        or None if no block is left to be requested.

        This will change the state of the piece from missing to ongoing - thus
        the next call to this function will not continue with the blocks for
        that piece, rather get the next missing piece.
        """
        for index, piece in enumerate(self.missing_pieces):
            if self.peers[peer_id][piece.index]:
                # Move this piece from missing to ongoing
                piece = self.missing_pieces.pop(index)
                self.ongoing_pieces.append(piece)
                # The missing pieces does not have any previously requested
                # blocks (then it is ongoing).
                return piece.next_request()
        return None

    def _write(self, piece):
        """
        Write the given piece to disk
        """
        pos = piece.index * self.torrent.piece_length
        os.lseek(self.fd, pos, os.SEEK_SET)
        os.write(self.fd, piece.data)

    def _organize_files(self):
        """ 
        Organize the file strucuture from a single file to as provided in meta_info. 
        """
        if not self.torrent.multi_file: 
            return
        #if not self.complete: 
        #    raise RuntimeError('organize_files called before completing download!')
        pos = 0 
        for file in self.torrent.files: 
            os.lseek(self.fd, pos, os.SEEK_SET)
            buffer = os.read(self.fd, file.length) 
            pos += file.length

            os.makedirs(os.path.dirname(file.path), exist_ok=True)
            tmp_fd = os.open(file.path,  os.O_RDWR | os.O_CREAT)
            os.write(tmp_fd, buffer) 
            os.close(tmp_fd) 

        # Remove the redundant tmp files 
        os.remove(self.torrent.output_file)

        return 