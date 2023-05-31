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

import asyncio
import logging
import struct
from asyncio import Queue
from concurrent.futures import CancelledError
import time
from collections import namedtuple
from .util import timeit
import bitstring

# The default request size for blocks of pieces is 2^14 bytes.
#
# NOTE: The official specification states that 2^15 is the default request
#       size - but in reality all implementations use 2^14. See the
#       unofficial specification for more details on this matter.
#
#       https://wiki.theory.org/BitTorrentSpecification
#
REQUEST_SIZE = 2**14


class ProtocolError(BaseException):
    pass


class PeerConnection:
    """
    A peer connection used to download and upload pieces.

    The peer connection will consume one available peer from the given queue.
    Based on the peer details the PeerConnection will try to open a connection
    and perform a BitTorrent handshake.

    After a successful handshake, the PeerConnection will be in a *choked*
    state, not allowed to request any data from the remote peer. After sending
    an interested message the PeerConnection will be waiting to get *unchoked*.

    Once the remote peer unchoked us, we can start requesting pieces.
    The PeerConnection will continue to request pieces for as long as there are
    pieces left to request, or until the remote peer disconnects.

    If the connection with a remote peer drops, the PeerConnection will consume
    the next available peer from off the queue and try to connect to that one
    instead.
    """
    IP_PORT = namedtuple("IP_PORT", ["ip", "port"])
    
    def __init__(self, queue: Queue, info_hash,
                peer_id, 
                piece_manager,
                on_block_cb, 
                read_request_retrieved,
                peer_connection_manager,
                app):
        """
        Constructs a PeerConnection and add it to the asyncio event-loop.

        Use `stop` to abort this connection and any subsequent connection
        attempts

        :param queue: The async Queue containing available peers
        :param info_hash: The SHA1 hash for the meta-data's info
        :param peer_id: Our peer ID used to to identify ourselves
        :param piece_manager: The manager responsible to determine which pieces
                              to request
        :param on_block_cb: The callback function to call when a block is
                            received from the remote peer
        """
        self.my_state = []
        self.peer_state = []
        self.queue = queue
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.remote_id = None
        self.writer = None
        self.reader = None
        self.piece_manager = piece_manager
        self.peer_connection_manager = peer_connection_manager
        self.on_block_cb = on_block_cb
        self.read_request_retrieved = read_request_retrieved
        self.future = asyncio.ensure_future(self._start())  # Start this worker
        # self.optimistic_unchoking_future = asyncio.ensure_future(piece_manager.optimistic_unchoking_choice())  # Start this worker
        self.stalled = False ## stalled means the prev. info has benn reserved
        self.ip_port = None
        self.app = app


    async def _start(self):
        while 'stopped' not in self.my_state:
            ip, port = await self.queue.get()
            self.ip_port = PeerConnection.IP_PORT(ip, port)
            logging.info('Got assigned peer with: {ip} at {port}'
                            .format(ip=ip, port = port))
            # self.app.textbox.insert('Got assigned peer with: {ip} at {port}\n'
            #                 .format(ip=ip, port = port))
            self.app.add_text('Got assigned peer with: {ip} at {port} \n'
                            .format(ip=ip, port = port))
            try:
                # TODO For some reason it does not seem to work to open a new
                # connection if the first one drops (i.e. second loop).
                self.reader, self.writer = await asyncio.open_connection(
                    ip, port)
                
                logging.info('Connection open to peer: {ip}'.format(ip=ip))
                self.app.add_text('Connection open to peer: {ip} \n'.format(ip=ip))
                
                # It's our responsibility to initiate the handshake.
                self.buffer = await self._handshake()

                self.peer_connection_manager.update_peer_connection_pool(peer_id = self.remote_id,
                                                        peer_connection = self,
                                                        ip_port = self.ip_port)
                # TODO Add support for sending data
                # Sending BitField is optional and not needed when client does
                # not have any pieces. Thus we do not send any bitfield message
                #await self._send_bitfield_after_handshake("0" * 20 + "1" * (len(self.piece_manager.torrent.pieces)-20)) ## This bitfield is currently under work when all bits are set 1
                # await self._send_bitfield_after_handshake("0" * (len(self.piece_manager.torrent.pieces))) ## This bitfield is currently under work when all bits are set 1
                # Some peers don't sent any BitField and rely on Have messages.
                # Thus we add a peer wihout any BitField.
                self.piece_manager.add_peer_without_bitfield(self.remote_id)
                # The default state for a connection is that peer is not
                # interested and we are choked
                self.my_state.append('choked')

                # Let the peer know we're interested in downloading pieces
                await self._send_interested()
                self.my_state.append('interested')
                
                # Start reading responses as a stream of messages for as
                # long as the connection is open and data is transmitted
                # while True:
                async for message in PeerStreamIterator(self.reader, self.buffer):
                    ## logging.debug("The message we have receieed is of type {}".format(type(message)))
                    if 'stopped' in self.my_state:
                        break
                    try:
                        await asyncio.wait_for(self._interact_with_peer(message=message), timeout=10)
                    except asyncio.TimeoutError: ## Have to Re-request in End-game-mode

                        if 'end_game_mode' in self.my_state:
                            await self._cancel_piece()
                            logging.debug("This end-game-mode failed, so have to re-request: {}".format(self.remote_id))
                            await self._request_piece_in_end_game_mode()

                        if not self.stalled:
                            self.peer_connection_manager.anti_snubbing_startegy(
                                peer_id = self.remote_id
                            )

            except ProtocolError as e: ## Handshake Error
                logging.exception('Protocol error')
            except (ConnectionRefusedError, TimeoutError): ## Exception caused in open_connction()
                logging.warning('Unable to connect to peer')
            except (ConnectionResetError, CancelledError):
                logging.warning('Connection closed')
                self.peer_connection_manager.unregister_peer_connection( ## Only in this scenario have we alreaady succeeded in registering the connection before
                    peer_id = self.remote_id
                )
            except Exception as e: ## Mostly likely to be the OS error in open_connection()
                logging.exception('An error occurred.')
                self.cancel()
               
                raise e

            self.cancel()

    async def _interact_with_peer(self, message):
                # logging.debug('Message received from peer with remote_id {remoteid} is of type {message_type}'
        #               .format(remoteid = self.remote_id, message_type = type(message)))
        # if self.piece_manager.have_pieces:
        #     message = Request(index = self.piece_manager.have_pieces[0].index,
        #                     begin= self.piece_manager.have_pieces[0].blocks[0].offset,
        #                     length = self.piece_manager.have_pieces[0].blocks[0].length).encode()
        #     message = Request.decode(message)
        #     #print(type(message))
        #     logging.debug("Requesting coming for piece index: {index}, blcok_offset: {offset}, piece_length: {length}"
        #                   .format(index = message.index, offset = message.begin, length = message.length))
        current_time = time.time()
        # logging.debug("current time: {time}, choking_timing: {timing}".
        #             format(time = current_time, timing = self.peer_connection_manager.choking_timing))
        if current_time - self.peer_connection_manager.choking_timing \
            > self.peer_connection_manager.choking_test_interval:
                # logging.debug("Bandwidth test executed for {peer}".format(peer = self.remote_id))
                self.peer_connection_manager.peer_connection_bandwidth_test(
                    peer_id = self.remote_id, 
                    peer_ip_port = self.ip_port, 
                    enable_end_game_mode = 'end_game_mode' in self.my_state
                )


        while self.stalled:
            current_time = time.time()
            # logging.debug("current time: {time}, choking_timing: {timing}".
            #             format(time = current_time, timing = self.peer_connection_manager.choking_timing))
            if current_time - self.peer_connection_manager.choking_timing \
                > self.peer_connection_manager.choking_test_interval:
                    # logging.debug("Bandwidth test executed for {peer}".format(peer = self.remote_id))
                    self.peer_connection_manager.peer_connection_bandwidth_test(
                        peer_id = self.remote_id, 
                        peer_ip_port = self.ip_port, 
                        enable_end_game_mode = 'end_game_mode' in self.my_state
                    )

            message = KeepAlive()
            self.writer.write(message.encode())
            await self.writer.drain()
            await asyncio.sleep(5)

        if type(message) is BitField: ## Message.bitfield is the actual payload without headers
            self.piece_manager.add_peer(self.remote_id,
                                        message.bitfield)
            #logging.debug("The peer named {0} 's bitfield is {1}".format(self.remote_id, len(message.bitfield)))
        elif type(message) is Interested:
            self.peer_state.append('interested')
            logging.debug("The peer named {0} is mysteriously interested in this repo".format(self.remote_id))
        elif type(message) is NotInterested:
            if 'interested' in self.peer_state:
                self.peer_state.remove('interested')
            logging.debug("The peer named {0} suddenly don't feel like this repo".format(self.remote_id))
        elif type(message) is Choke:
            self.my_state.append('choked')
        elif type(message) is Unchoke:
            if 'choked' in self.my_state:
                self.my_state.remove('choked')
        elif type(message) is Have:
            self.piece_manager.update_peer(self.remote_id,
                                            message.index)
        elif type(message) is KeepAlive:
            pass
        elif type(message) is Piece:
            self.peer_connection_manager.blocks_already_sent[self.remote_id] += 1
            block_received = self.on_block_cb(
                    peer_id=self.remote_id,
                    piece_index=message.index,
                    block_offset=message.begin,
                    data=message.block,
                    enable_end_game_mode = 'end_game_mode' in self.my_state)
            if 'end_game_mode' not in self.my_state and 'pending_request' in self.my_state:
                self.my_state.remove('pending_request')

        elif type(message) is Request:
            
            await self._send_request_for_peer(piece_index= message.index,
                                        block_offset_within_a_piece= message.begin,
                                        requested_data_length=message.length)
            
            
            logging.info('Sending the block with piece_index: {piece_index}, block offset: {offset}, length: {length}'
                            .format(piece_index = message.index, offset = message.begin, length = message.length))
            

        elif type(message) is Cancel:
            # TODO Add support for sending data
            logging.info('Ignoring the received Cancel message.')
        elif isinstance(message, Timeout):
            if 'end_game_mode' in self.my_state:
                await self._cancel_piece()
                logging.debug("This end-game-mode failed, so have to re-request: {}".format(self.remote_id))
                chk = await self._request_piece_in_end_game_mode()

            self.peer_connection_manager.anti_snubbing_startegy(
                peer_id = self.remote_id
            )
        # Send block request to remote peer if we're interested
        if 'choked' not in self.my_state:
            if 'interested' in self.my_state:
                if 'end_game_mode' in self.my_state:
                    
                    await self._cancel_piece()

                    # await self._request_expired_blocks_in_end_game_mode()
                elif 'pending_request' not in self.my_state:
                    if not self.piece_manager._is_suitable_to_enter_the_end_game_mode(peer_id = self.remote_id,
                                                                                    end_game_mode = 2):
                        chk = await self._request_piece()

                        if chk:
                            self.my_state.append('pending_request')
                    else:
                        chk = await self._request_piece_in_end_game_mode()
                        if chk:
                            self.my_state.append("end_game_mode")
                            self.peer_connection_manager.set_end_game_mode()
                            logging.debug("We have officailly entered into End Game mode!")


    def cancel(self):
        """
        Sends the cancel message to the remote peer and closes the connection.
        """
        logging.info('Closing peer {id}'.format(id=self.remote_id))
        if not self.future.done():
            self.future.cancel()
        if self.writer:
            self.writer.close()
        self.stalled = False

        self.queue.task_done()

    def stop(self):
        """
        Stop this connection from the current peer (if a connection exist) and
        from connecting to any new peer.
        """
        # Set state to stopped and cancel our future to break out of the loop.
        # The rest of the cleanup will eventually be managed by loop calling
        # `cancel`.

        self.stalled = True       

    def restart(self):
        """
        Restart the connection with the previos peer
        """
        # Set state to stopped and cancel our future to break out of the loop.
        # The rest of the cleanup will eventually be managed by loop calling
        # `cancel`.

        self.stalled = False   


    async def _cancel_piece(self):
        cancelled = self.piece_manager.end_game_cancelled[self.remote_id]
        if cancelled:
            for cancelled_block in cancelled:
                message = Cancel(cancelled_block.piece, cancelled_block.offset, cancelled_block.length).encode()

                # logging.debug('Cancelling block {block} for piece {piece} '
                #           'of {length} bytes from peer {peer}'.format(
                #             piece=cancelled_block.piece,
                #             block=cancelled_block.offset,
                #             length=cancelled_block.length,
                #             peer=self.remote_id))

                self.writer.write(message)
            self.piece_manager.end_game_cancelled[self.remote_id] = []
            await self.writer.drain()
            return True 
        else:
            return False


    async def _request_expired_blocks_in_end_game_mode(self):
        blocks = self.piece_manager._expired_requests(
            peer_id = self.remote_id,
            enable_end_game_mode = True
        )
        if blocks:
            ## TODO: Whether to put the self.write.drain() outside the loop or inside the loop
            for block in blocks:
                message = Request(block.piece, block.offset, block.length).encode()
                logging.debug('Re -requesting expired block {block} for piece {piece} '
                          'of {length} bytes from peer {peer} in End-Game mode'.format(
                            piece=block.piece,
                            block=block.offset,
                            length=block.length,
                            peer=self.remote_id))
                self.app.add_text('Re-requesting expired block {block} for piece {piece} '
                          'with length {length} bytes from peer {peer} in End Game mode\n'.format(
                            piece=block.piece,
                            block=block.offset,
                            length=block.length,
                            peer=self.remote_id))
                self.writer.write(message)
                await self.writer.drain()
            return True
        else:
            return False

    async def _request_piece(self):
        block = self.piece_manager.next_request(self.remote_id)
        if block:
            message = Request(block.piece, block.offset, block.length).encode()

            # logging.debug('Requesting block {block} for piece {piece} '
            #               'of {length} bytes from peer {peer}'.format(
            #                 piece=block.piece,
            #                 block=block.offset,
            #                 length=block.length,
            #                 peer=self.remote_id))

            self.writer.write(message)
            await self.writer.drain()
            return True 
        else:
            return False
        
    async def _request_piece_in_end_game_mode(self):
        blocks = self.piece_manager.next_request_in_end_game_mode(self.remote_id)
        if blocks:
            ## TODO: Whether to put the self.write.drain() outside the loop or inside the loop
            for block in blocks:
                message = Request(block.piece, block.offset, block.length).encode()
                logging.debug('Requesting block {block} for piece {piece} '
                          'of {length} bytes from peer {peer} in End-Game mode'.format(
                            piece=block.piece,
                            block=block.offset,
                            length=block.length,
                            peer=self.remote_id))
                self.app.add_text('Requesting block {block} for piece {piece} '
                          'of {length} bytes from peer {peer} in End Game mode \n'.format(
                            piece=block.piece,
                            block=block.offset,
                            length=block.length,
                            peer=self.remote_id))
                self.writer.write(message)
                await self.writer.drain()
            return True
        else:
            return False

    async def _handshake(self):
        """
        Send the initial handshake to the remote peer and wait for the peer
        to respond with its handshake.
        """
        self.writer.write(Handshake(self.info_hash, self.peer_id).encode())
        await self.writer.drain()

        buf = b''
        tries = 1
        while len(buf) < Handshake.length and tries < 10:
            tries += 1
            buf = await self.reader.read(PeerStreamIterator.CHUNK_SIZE)

        response = Handshake.decode(buf[:Handshake.length])
        if not response:
            raise ProtocolError('Unable receive and parse a handshake')
        if not response.info_hash == self.info_hash:
            raise ProtocolError('Handshake with invalid info_hash')

        # TODO: According to spec we should validate that the peer_id received
        # from the peer match the peer_id received from the tracker.
        self.remote_id = response.peer_id
        logging.info('Handshake with peer was successful')
        self.app.add_text('Handshake with peer: {} was successful \n'.format(self.remote_id))
        # We need to return the remaining buffer data, since we might have
        # read more bytes then the size of the handshake message and we need
        # those bytes to parse the next message.
        return buf[Handshake.length:]

    async def _send_interested(self):
        
        message = Interested()
        logging.debug('Sending message: {type} to peer: {id}'.format(type=message, id = self.remote_id))
        self.app.add_text('Sending message: {type} to peer: {id} \n'.format(type=message, id = self.remote_id))
        self.writer.write(message.encode())
        await self.writer.drain()

    async def _send_bitfield_after_handshake(self, bitfield_payload):
        pieces_length = len(self.piece_manager.torrent.pieces)
        bitfield_payload_round = bitfield_payload
        if len(bitfield_payload) % 8:
            bitfield_payload_round += (8 - len(bitfield_payload) % 8) * '0'
        bitfield_payload_round = '0b{}'.format(bitfield_payload_round)
        ##logging.debug('Sending bitfield immediately after handshake: {}'.format(len(bitfield_payload_round)))
        message = BitField(bitfield_payload_round)
        #logging.debug('Sending bitfield immediately after handshake: {}'.format(bitfield_payload_round))
        self.writer.write(message.encode())
        await self.writer.drain()

    async def _send_request_for_peer(self, piece_index, block_offset_within_a_piece, requested_data_length):
        """
        Send the requested data to the sepecific peer
        Data value returned by the os.read() should be of bytes type;
        """
        data = self.read_request_retrieved(peer_id = self.remote_id,
                                           piece_index = piece_index,
                                           block_offset_within_a_piece = block_offset_within_a_piece,
                                           requested_data_length = requested_data_length)
        assert(isinstance(data, bytes))

        message = Piece(index = piece_index,
                        begin = block_offset_within_a_piece,
                        block = data)
        self.writer.write(message.encode())
        await self.writer.drain()


class PeerStreamIterator:
    """
    The `PeerStreamIterator` is an async iterator that continuously reads from
    the given stream reader and tries to parse valid BitTorrent messages from
    off that stream of bytes.

    If the connection is dropped, something fails the iterator will abort by
    raising the `StopAsyncIteration` error ending the calling iteration.
    """
    CHUNK_SIZE = 10*1024

    def __init__(self, reader, initial: bytes=None):
        self.reader = reader
        self.buffer = initial if initial else b''

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            message = await asyncio.wait_for(self.anext(), timeout=10)
            return message
        except asyncio.exceptions.TimeoutError:
            logging.debug("This peer connection times out: anti-snugging strategy is executed...")
            return Timeout()

    async def anext(self):
        # Read data from the socket. When we have enough data to parse, parse
        # it and return the message. Until then keep reading from stream
        while True:
            try:
                
                data = await self.reader.read(PeerStreamIterator.CHUNK_SIZE)
                if data:
                    self.buffer += data
                    message = self.parse()
                    if message:
                        return message
                else:
                    #logging.debug('No data read from stream')
                    if self.buffer:
                        message = self.parse()
                        if message:
                            return message
                    raise StopAsyncIteration()
            except ConnectionResetError:
                logging.debug('Connection closed by peer')
                raise StopAsyncIteration()
            except CancelledError:
                raise StopAsyncIteration()
            except StopAsyncIteration as e:
                # Cath to stop logging
                raise e
            except Exception:
                logging.exception('Error when iterating over stream!')
                raise StopAsyncIteration()
        raise StopAsyncIteration()

    def parse(self):
        """
        Tries to parse protocol messages if there is enough bytes read in the
        buffer.

        :return The parsed message, or None if no message could be parsed
        """
        # Each message is structured as:
        #     <length prefix><message ID><payload>
        #
        # The `length prefix` is a four byte big-endian value
        # The `message ID` is a decimal byte
        # The `payload` is the value of `length prefix`
        #
        # The message length is not part of the actual length. So another
        # 4 bytes needs to be included when slicing the buffer.
        header_length = 4

        if len(self.buffer) > 4:  # 4 bytes is needed to identify the message
            message_length = struct.unpack('>I', self.buffer[0:4])[0]

            if message_length == 0:
                logging.debug('Got a KeepAlive message')
                # Call consume 
                self.buffer = self.buffer[header_length + message_length:]
                return KeepAlive()

            if len(self.buffer) >= message_length+header_length:
                message_id = struct.unpack('>b', self.buffer[4:5])[0]

                def _consume():
                    """Consume the current message from the read buffer"""
                    self.buffer = self.buffer[header_length + message_length:]

                def _data():
                    """"Extract the current message from the read buffer"""
                    return self.buffer[:header_length + message_length]

                if message_id is PeerMessage.BitField:
                    data = _data()
                    _consume()
                    return BitField.decode(data)
                elif message_id is PeerMessage.Interested:
                    _consume()
                    return Interested()
                elif message_id is PeerMessage.NotInterested:
                    _consume()
                    return NotInterested()
                elif message_id is PeerMessage.Choke:
                    _consume()
                    return Choke()
                elif message_id is PeerMessage.Unchoke:
                    _consume()
                    return Unchoke()
                elif message_id is PeerMessage.Have:
                    data = _data()
                    _consume()
                    return Have.decode(data)
                elif message_id is PeerMessage.Piece:
                    data = _data()
                    _consume()
                    return Piece.decode(data)
                elif message_id is PeerMessage.Request:
                    data = _data()
                    _consume()
                    return Request.decode(data)
                elif message_id is PeerMessage.Cancel:
                    data = _data()
                    _consume()
                    return Cancel.decode(data)
                else:
                    logging.info('Unsupported message!')
            else:
                pass
                ##logging.debug('Not enough in buffer in order to parse')
        return None


class PeerMessage:
    """
    A message between two peers.

    All of the remaining messages in the protocol take the form of:
        <length prefix><message ID><payload>

    - The length prefix is a four byte big-endian value.
    - The message ID is a single decimal byte.
    - The payload is message dependent.

    NOTE: The Handshake messageis different in layout compared to the other
          messages.

    Read more:
        https://wiki.theory.org/BitTorrentSpecification#Messages

    BitTorrent uses Big-Endian (Network Byte Order) for all messages, this is
    declared as the first character being '>' in all pack / unpack calls to the
    Python's `struct` module.
    """
    Choke = 0
    Unchoke = 1
    Interested = 2
    NotInterested = 3
    Have = 4
    BitField = 5
    Request = 6
    Piece = 7
    Cancel = 8
    Port = 9
    Handshake = None  # Handshake is not really part of the messages
    KeepAlive = None  # Keep-alive has no ID according to spec

    def encode(self) -> bytes:
        """
        Encodes this object instance to the raw bytes representing the entire
        message (ready to be transmitted).
        """
        pass

    @classmethod
    def decode(cls, data: bytes):
        """
        Decodes the given BitTorrent message into a instance for the
        implementing type.
        """
        pass


class Handshake(PeerMessage):
    """
    The handshake message is the first message sent and then received from a
    remote peer.

    The messages is always 68 bytes long (for this version of BitTorrent
    protocol).

    Message format:
        <pstrlen><pstr><reserved><info_hash><peer_id>

    In version 1.0 of the BitTorrent protocol:
        pstrlen = 19
        pstr = "BitTorrent protocol".

    Thus length is:
        49 + len(pstr) = 68 bytes long.
    """
    length = 49 + 19

    def __init__(self, info_hash: bytes, peer_id: bytes):
        """
        Construct the handshake message

        :param info_hash: The SHA1 hash for the info dict
        :param peer_id: The unique peer id
        """
        if isinstance(info_hash, str):
            info_hash = info_hash.encode('utf-8')
        if isinstance(peer_id, str):
            peer_id = peer_id.encode('utf-8')
        self.info_hash = info_hash
        self.peer_id = peer_id

    def encode(self) -> bytes:
        """
        Encodes this object instance to the raw bytes representing the entire
        message (ready to be transmitted).
        """
        return struct.pack(
            '>B19s8x20s20s',
            19,                         # Single byte (B)
            b'BitTorrent protocol',     # String 19s
                                        # Reserved 8x (pad byte, no value)
            self.info_hash,             # String 20s
            self.peer_id)               # String 20s

    @classmethod
    def decode(cls, data: bytes):
        """
        Decodes the given BitTorrent message into a handshake message, if not
        a valid message, None is returned.
        """
        logging.debug('Decoding Handshake of length: {length}'.format(
            length=len(data)))
        if len(data) < (49 + 19):
            return None
        parts = struct.unpack('>B19s8x20s20s', data)
        return cls(info_hash=parts[2], peer_id=parts[3])

    def __str__(self):
        return 'Handshake'


class KeepAlive(PeerMessage):
    """
    The Keep-Alive message has no payload and length is set to zero.

    Message format:
        <len=0000>
    """
    def __str__(self):
        return 'KeepAlive'

    def encode(self) -> bytes:
        """
        Keep Alive message encoded
        """
        return struct.pack('>I',0
            )           

class BitField(PeerMessage):
    """
    The BitField is a message with variable length where the payload is a
    bit array representing all the bits a peer have (1) or does not have (0).

    Message format:
        <len=0001+X><id=5><bitfield>
    """
    def __init__(self, data):
        self.bitfield = bitstring.BitArray(data)

    def encode(self) -> bytes:
        """
        Encodes this object instance to the raw bytes representing the entire
        message (ready to be transmitted).
        """
        bits_length = len(self.bitfield.bytes)
        # logging.debug("The bitfield message is {}".format(struct.pack('>Ib' + str(bits_length) + 's',
        #                    1 + bits_length,
        #                    PeerMessage.BitField, ## 5 
        #                    self.bitfield.bytes)))
        return struct.pack('>Ib' + str(bits_length) + 's',
                           1 + bits_length,
                           PeerMessage.BitField, ## 5 
                           self.bitfield.bytes)

    @classmethod
    def decode(cls, data: bytes):
        
        message_length = struct.unpack('>I', data[:4])[0]
        #logging.debug('Decoding BitField: {}'.format(message_length))
        # logging.debug('Decoding BitField of length: {length}'.format(
        #     length=message_length))

        parts = struct.unpack('>Ib' + str(message_length - 1) + 's', data)
        return cls(parts[2])

    def __str__(self):
        return 'BitField'

class Timeout(PeerMessage):
    """
    The timeout is directly cause by the peer, so accounted as inheritance of PeerMessage
    """
    def __str__(self):
        return 'Timeout'


class Interested(PeerMessage):
    """
    The interested message is fix length and has no payload other than the
    message identifiers. It is used to notify each other about interest in
    downloading pieces.

    Message format:
        <len=0001><id=2>
    """

    def encode(self) -> bytes:
        """
        Encodes this object instance to the raw bytes representing the entire
        message (ready to be transmitted).
        """
        return struct.pack('>Ib',
                           1,  # Message length
                           PeerMessage.Interested)

    def __str__(self):
        return 'Interested'


class NotInterested(PeerMessage):
    """
    The not interested message is fix length and has no payload other than the
    message identifier. It is used to notify each other that there is no
    interest to download pieces.

    Message format:
        <len=0001><id=3>
    """
    def __str__(self):
        return 'NotInterested'


class Choke(PeerMessage):
    """
    The choke message is used to tell the other peer to stop send request
    messages until unchoked.

    Message format:
        <len=0001><id=0>
    """
    def __str__(self):
        return 'Choke'


class Unchoke(PeerMessage):
    """
    Unchoking a peer enables that peer to start requesting pieces from the
    remote peer.

    Message format:
        <len=0001><id=1>
    """
    def __str__(self):
        return 'Unchoke'


class Have(PeerMessage):
    """
    Represents a piece successfully downloaded by the remote peer. The piece
    is a zero based index of the torrents pieces
    """
    def __init__(self, index: int):
        self.index = index

    def encode(self):
        return struct.pack('>IbI',
                           5,  # Message length
                           PeerMessage.Have,
                           self.index)

    @classmethod
    def decode(cls, data: bytes):
        # logging.debug('Decoding Have of length: {length}'.format(
        #     length=len(data)))
        index = struct.unpack('>IbI', data)[2]
        return cls(index)

    def __str__(self):
        return 'Have'


class Request(PeerMessage):
    """
    The message used to request a block of a piece (i.e. a partial piece).

    The request size for each block is 2^14 bytes, except the final block
    that might be smaller (since not all pieces might be evenly divided by the
    request size).

    Message format:
        <len=0013><id=6><index><begin><length>
    """
    def __init__(self, index: int, begin: int, length: int = REQUEST_SIZE):
        """
        Constructs the Request message.

        :param index: The zero based piece index
        :param begin: The zero based offset within a piece
        :param length: The requested length of data (default 2^14)
        """
        self.index = index
        self.begin = begin
        self.length = length

    def encode(self):
        return struct.pack('>IbIII',
                           13,
                           PeerMessage.Request,
                           self.index,
                           self.begin,
                           self.length)

    @classmethod
    def decode(cls, data: bytes):
        logging.debug('Decoding Request of length: {length}'.format(
            length=len(data)))
        # Tuple with (message length, id, index, begin, length)
        parts = struct.unpack('>IbIII', data)
        return cls(parts[2], parts[3], parts[4])

    def __str__(self):
        return 'Request'


class Piece(PeerMessage):
    """
    A block is a part of a piece mentioned in the meta-info. The official
    specification refer to them as pieces as well - which is quite confusing
    the unofficial specification refers to them as blocks however.

    So this class is named `Piece` to match the message in the specification
    but really, it represents a `Block` (which is non-existent in the spec).

    Message format:
        <length prefix><message ID><index><begin><block>
    """
    # The Piece message length without the block data
    length = 9

    def __init__(self, index: int, begin: int, block: bytes):
        """
        Constructs the Piece message.

        :param index: The zero based piece index
        :param begin: The zero based offset within a piece
        :param block: The block data
        """
        self.index = index
        self.begin = begin
        self.block = block

    def encode(self):
        message_length = Piece.length + len(self.block)
        return struct.pack('>IbII' + str(len(self.block)) + 's',
                           message_length,
                           PeerMessage.Piece,
                           self.index,
                           self.begin,
                           self.block)

    @classmethod
    def decode(cls, data: bytes):
        # logging.debug('Decoding Piece of length: {length}'.format(
        #     length=len(data)))
        length = struct.unpack('>I', data[:4])[0]
        parts = struct.unpack('>IbII' + str(length - Piece.length) + 's',
                              data[:length+4])
        return cls(parts[2], parts[3], parts[4])

    def __str__(self):
        return 'Piece'


class Cancel(PeerMessage):
    """
    The cancel message is used to cancel a previously requested block (in fact
    the message is identical (besides from the id) to the Request message).

    Message format:
         <len=0013><id=8><index><begin><length>
    """
    def __init__(self, index, begin, length: int = REQUEST_SIZE):
        self.index = index
        self.begin = begin
        self.length = length

    def encode(self):
        return struct.pack('>IbIII',
                           13,
                           PeerMessage.Cancel,
                           self.index,
                           self.begin,
                           self.length)

    @classmethod
    def decode(cls, data: bytes):
        logging.debug('Decoding Cancel of length: {length}'.format(
            length=len(data)))
        # Tuple with (message length, id, index, begin, length)
        parts = struct.unpack('>IbIII', data)
        return cls(parts[2], parts[3], parts[4])

    def __str__(self):
        return 'Cancel'
