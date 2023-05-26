#!/usr/bin/env python
# coding: utf-8
## Reference: https://github.com/pobrn/mktorrent.git
import os
import logging
import subprocess
import argparse


logging.basicConfig(level=logging.DEBUG)



def mktorrent_wrapper(cmd):
    logging.debug('Goes into cmd: {}'.format(cmd))

    cmd_env = os.environ.copy()
    # cmd_env.update(
    #     LC_ALL='C',
    # )

    open_process = subprocess.Popen(cmd, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True, env=cmd_env)

    out, err = open_process.communicate()
    out, err = out.decode(), err.decode()
    logging.debug('{}'.format(out))

    
    if err:
        logging.error("{}".format(err))


def main(announce_urls, 
         filename_of_the_file_to_be_torrented,
         comment_to_the_metainfo = None, 
         donotWrite = None, 
         piece_length_setter = None, 
         torrent_name = None, 
         torrent_path_and_filename = None, 
         verbose = None, ):
    """
    Specification: Usage: mktorrent [OPTIONS] <target directory or filename>

    -a <url>[,<url>]* : specify the full announce URLs
                    additional -a adds backup trackers
    -c <comment>      : add a comment to the metainfo
    -d                : don't write the creation date
    -e <pat>[,<pat>]* : exclude files whose name matches the pattern <pat>
                        see the man page glob(7)
    -f                : overwrite output file if it exists
    -h                : show this help screen
    -l <n>            : set the piece length to 2^n bytes,
                        default is calculated from the total size
    -n <name>         : set the name of the torrent,
                        default is the basename of the target
    -o <filename>     : set the path and filename of the created file
                        default is <name>.torrent
    -p                : set the private flag
    -s                : add source string embedded in infohash
    -v                : be verbose
    -w <url>[,<url>]* : add web seed URLs
                        additional -w adds more URLs
    -x                : ensure info hash is unique for easier cross-seeding
    """
    current_dir = os.path.dirname(__file__)
    cmd = '{current_dir}/mktorrent -a {urls}'.format(current_dir = current_dir, urls = announce_urls[0])
    if isinstance(announce_urls, list) and len(announce_urls) > 1:
        announce_urls = announce_urls[1:]
        cmd += ','
        cmd += ','.join(announce_urls)
    if comment_to_the_metainfo is not None:
        if ' ' in comment_to_the_metainfo:
            logging.warning("The comment added to the meta info:'{}' is not allowed".format(comment_to_the_metainfo))
            return None
        cmd += ' -c {}'.format(comment_to_the_metainfo)
    if donotWrite:
        cmd += ' -d'
    if piece_length_setter is not None and \
        isinstance(piece_length_setter, int) and piece_length_setter in [16, 15, 17, 18, 19, 20]:
        cmd += ' -l {}'.format(piece_length_setter)
    if torrent_name is not None:
        if ' ' in torrent_name:
            logging.warning("The comment added to the meta info:'{}' is not allowed".format(torrent_name))
            return None
        cmd += ' -n {}'.format(torrent_name)
    if torrent_path_and_filename is not None and isinstance(torrent_path_and_filename, str):
    
        if isinstance(torrent_path_and_filename, str):
            cmd += ' -o {}'.format(torrent_path_and_filename)
        else:
            logging.warning("Attempting to create .torrent at {filepath} failed."
                            .format(filepath = torrent_path_and_filename.rsplit('/')[:-1]))
            return None
    if verbose:
        cmd += ' -v'
   
    cmd += ' {}'.format(filename_of_the_file_to_be_torrented)
    mktorrent_wrapper(cmd=cmd)
    return None


if __name__ == '__main__':

    # main(
    #     announce_urls = ['https://opentracker.i2p.rocks:443/announce'], 
    #     filename_of_the_file_to_be_torrented = 'suhao.pdf',
    #     comment_to_the_metainfo = "EasyHec_Hand-Eye_calibration", 
    #     donotWrite = None, 
    #     piece_length_setter = 14, 
    #     torrent_name = "EasyHec_Hand-Eye_calibration", 
    #     torrent_path_and_filename = "~/Desktop/suhao_new", 
    #     verbose = True, 
    # )
    # Parse input arguments
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-a",
        "--announce-urls",
        required=True,
        help="Announce url of the tracker.",
    )
    parser.add_argument(
        "-f",
        "--input-file",
        required=True,
        help="The input file to be made .torrent of",
    )
    parser.add_argument(
        "-c", "--comment", help="Comment to the meta-info of the .torrent file", default=None
    )
    parser.add_argument(
        "-w",
        "--not-write",
        action='store_true',
        default=False,
        help="Don't write the creation date.",
    )
    parser.add_argument(
        "-l",
        "--piece-length",
        type=int,
        default=None,
        help="The length of a piece.",
    )
    parser.add_argument(
        "-n",
        "--torrent-name",
        default=None,
        help="set the name of the torrent",
    )
    parser.add_argument(
        "-p",
        "--torrent-path",
        default=None,
        help="set the path and filename of the created file \
                        default is <name>.torrent"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action='store_true',
        help="be verbose"
    )
    args = parser.parse_args()

    main(
        announce_urls = [args.announce_urls.split(',')], 
        filename_of_the_file_to_be_torrented = args.input_file,
        comment_to_the_metainfo = args.comment, 
        donotWrite = True if args.not_write == True else False, 
        piece_length_setter = args.piece_length, 
        torrent_name = args.torrent_name, 
        torrent_path_and_filename = args.torrent_path, 
        verbose = True if args.verbose == True else False, 
    )
