from __future__ import absolute_import
#
# -*- coding: utf-8 -*-
import argparse
import os
import logging
from .sync import Sync
from .local import Local
from .remote import Remote

__author__ = 'faisal'
# todo get from setup.cfg
version = '0.3.0'

logger = logging.getLogger("flickrsmartsync")
hdlr = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)8s: %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)


def main():
    parser = argparse.ArgumentParser(description='Sync current folder to your flickr account.')
    parser.add_argument('--monitor', action='store_true',
                        help='starts a daemon after sync for monitoring')
    parser.add_argument('--starts-with', type=str,
                        help='only sync that path starts with this text, e.g. "2015/06"')
    parser.add_argument('--download', type=str,
                        help='download the photos from flickr, specify a path or . for all')
    parser.add_argument('--dry-run', action='store_true',
                        help='do not download or upload anything')
    parser.add_argument('--ignore-videos', action='store_true',
                        help='ignore video files')
    parser.add_argument('--ignore-images', action='store_true',
                        help='ignore image files')
    parser.add_argument('--ignore-ext', type=str,
                        help='comma separated list of extensions to ignore, e.g. "jpg,png"')
    parser.add_argument('--version', action='store_true',
                        help='output current version: ' + version)
    parser.add_argument('--sync-path', type=str, default=os.getcwd(),
                        help='specify the sync folder (default is current dir)')
    parser.add_argument('--sync-from', type=str,
                        help='Only supported value: "all". Uploads anything that isn\'t on flickr, and download anything that isn\'t on the local filesystem')
    parser.add_argument('--username', type=str,
                        help='token username')  # token username argument for api
    parser.add_argument('--keyword', action='append', type=str, # DON'T USE THIS, it needs code change to work !!!!!!!!!!!!!!!!!
                        help='only upload files matching this keyword')
    parser.add_argument('--manual-auth', action='store_true',
                        help='authenticate in a different computer by browsing to an url and entering the returned code manually')

    args = parser.parse_args()

    if args.version:
        logger.info(version)
        exit()

    # validate args
    args.is_windows = os.name == 'nt'
    args.sync_path = args.sync_path.rstrip(os.sep) + os.sep
    if not os.path.exists(args.sync_path):
        logger.error('Sync path does not exists')
        exit(0)

    logger.debug("running with args:{}".format(str(args)))
    local = Local(args)
    remote = Remote(args)
    logger.debug("starting sync...")
    sync = Sync(args, local, remote)
    sync.start_sync()
    logger.debug("all done.")

