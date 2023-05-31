# Bittorrent

This repo implements the *Bittorrent* with munificient features, including distributed hash table network, choking and optimstic unchoking strategy, end game, rarest piece first, anti-snubbing. And the bittorrent peer also supports upload, magnet link conversion and so on.

### Notice:

More updates on the GUI visuallizations:

Usage:

```
cd bittorrent/multi_file_pieces
python3 piecse.py -g
```

Downloading the torrent:
![](https://notes.sjtu.edu.cn/uploads/upload_1d3746391aaad31384e2ab2af16be4c4.png)
Cheking the basic elements of torrent, tracker, peer connections(Also has Dark, Light UI style):
![](https://notes.sjtu.edu.cn/uploads/upload_6b07b19c43b0c90bd113d4b18fd92743.png)
Selecting file to be torrented in local directory:
![](https://notes.sjtu.edu.cn/uploads/upload_ceb1c6547d923403a478e7232af9a941.png)

Setting the name of the torrent:
![](https://notes.sjtu.edu.cn/uploads/upload_43a876fe41dff3a95424ba66120f87ed.png)

Successfully make torrent showup:
![](https://notes.sjtu.edu.cn/uploads/upload_6204357ded04a0272cb5741a2309a29a.png)



### Submodules:

![](https://notes.sjtu.edu.cn/uploads/upload_cde44ab90bba4d46443445e793bf05a4.png)

### 1. *mktorrent*
   make torrent with optional choices.[9]

Basic test `python pymktorrent -a annouce_url -f suhao.pdf`
Run `python pymktorrent.py -h` to say more optinal choices.


```
usage: pymktorrent.py [-h] -a ANNOUNCE_URLS -f INPUT_FILE [-c COMMENT] [-w NOT_WRITE] [-l PIECE_LENGTH]
                      [-n TORRENT_NAME] [-p TORRENT_PATH] [-v VERBOSE]

options:
  -h, --help            show this help message and exit
  -a ANNOUNCE_URLS, --announce-urls ANNOUNCE_URLS
                        Announce url of the tracker. (default: None)
  -f INPUT_FILE, --input-file INPUT_FILE
                        The input file to be made .torrent of (default: None)
  -c COMMENT, --comment COMMENT
                        Comment to the meta-info of the .torrent file (default: None)
  -w NOT_WRITE, --not-write NOT_WRITE
                        Don't write the creation date. (default: None)
  -l PIECE_LENGTH, --piece-length PIECE_LENGTH
                        The length of a piece. (default: None)
  -n TORRENT_NAME, --torrent-name TORRENT_NAME
                        set the name of the torrent (default: None)
  -p TORRENT_PATH, --torrent-path TORRENT_PATH
                        set the path and filename of the created file default is <name>.torrent (default: None)
  -v VERBOSE, --verbose VERBOSE
                        be verbose (default: None)

```

### 2. *multi-file-pieces*
Basic test: `python pieces.py -t ubuntu.torrent` to download the $.torrent$ file.([3],[4],[5],[6],[7],[8])


Run `python pieces.py -h` to say more optinal choices.
```
usage: pieces.py [-h] [-t TORRENT] [-m MAGNET_LINK] [-v] [-o] [-a] [-c] [-e] [-r] [-b] [-p PORT] [-d DHT]

options:
  -h, --help            show this help message and exit
  -t TORRENT, --torrent TORRENT
                        the .torrent to download (default: None)
  -m MAGNET_LINK, --magnet-link MAGNET_LINK
                        the magnet link url to download (default: None)
  -v, --verbose         enable verbose output (default: False)
  -o, --optimistic-unchoking
                        Whether to use the optimistic unchoking strategy. (default: False)
  -a, --anti-snubbing   Whether to use the anti-snubbing strategy. (default: False)
  -c, --choking-strategy
                        Whether to use the choking strategy. (default: False)
  -e, --end-game-mode   Whether to use the End-game optimization. (default: False)
  -r, --rarest-piece-first
                        Whether to use the rarest piece first strategy. (default: False)
  -b, --bbs-plus        Whether to enable bbs plus optimization (May lead to network congestion and bandwidth
                        waste). (default: False)
  -p PORT, --port PORT  The port that the local DHT node is listening from. (default: None)
  -d DHT, --dht DHT     Whether use DHT(Distributed Hash Table) extension. (default: None)
```

### 3. *P2P*
P2P punching([1],[2]) implemented in Python. The server serves as a STUN server or a TURN server based on the NAT type.

Python p2p chat client/server with built-in NAT traversal (UDP hole punching).  

#### Usage

Suppose you run server.py on a VPS with ip 1.2.3.4, listening on port 5678  
```bash
$ server.py 5678
```  

On client A and client B (run this on both clients):  
```bash
$ client.py 1.2.3.4 5678 100  
```  
The number `100` is used to match clients, you can choose any number you like but only clients with the **same** number will be linked by server. If two clients get linked, two people can chat by typing in terminal, and once you hit `<ENTER>` your partner will see your message in his terminal.   
Encoding is a known issue since I didn't pay much effort on making this tool perfect, but as long as you type English it will be fine.

#### Test Mode

You could do simulation testing by specifying a fourth parameter of `client.py`, it will assume that your client is behind a specific type of NAT device.

Here are the corresponding NAT type and number:  

	FullCone         0  
	RestrictNAT      1  
	RestrictPortNAT  2  
	SymmetricNAT     3   

So you might run
```bash
$ client.py 1.2.3.4 5678 100 1
```   
pretending your client is behind RestrictNAT. 


[1]:http://www.cs.nccu.edu.tw/~lien/Writing/NGN/firewall.htm
[2]:https://bford.info/pub/net/p2pnat/index.html
[3]:https://github.com/bmuller/rpcudp.git
[4]:http://bittorrent.org/beps/bep_0005.html
[5]:https://inria.hal.science/inria-00000156/en
[6]:https://www.scs.stanford.edu/~dm/home/papers/kpos.pdf
[7]:https://snarky.ca/how-the-heck-does-async-await-work-in-python-3-5/
[8]:https://github.com/danfolkes/Magnet2Torrent.git
[9]:https://en.wikipedia.org/wiki/Bencode

