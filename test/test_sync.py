#!/usr/bin/env python
from builtins import object
import unittest
import logging
import sys
import os
import copy

here = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(here, '..'))
from flickrsmartsync.sync import Sync
logger = logging.getLogger("flickrsmartsync")
logger.setLevel(logging.WARNING)

fakestat = os.stat(__file__)
fakeid = 45
class fakeLocal(object):
    files = {}
    def __init__(self):
        self.files.clear()
        self.files.update({here + os.sep + "dirname": [("file1.jpg", fakestat), ("file2.avi", fakestat)]})

    def build_photo_sets(self, specific_path, exts):
        return self.files

class fakeRemote(object):
    def __init__(self):
        self.photo_sets_map = {"dirname": "12345"}
        self.files = {"12345": {"file3.jpg": 23, "file4.avi": 23}}
    def get_photo_sets(self):
        return self.photo_sets_map
    def get_photo_set_title_from_path(self, path):
        return path.split('/').pop()
    def get_photos_in_set(self, folder, get_url=False):
        return self.files[self.photo_sets_map[folder]]
    def upload(self, file_path, photo, folder):
        self.files[self.photo_sets_map[folder]][photo] = fakeid
    def download(self, url, path):
        list(fakeLocal.files.values())[0].append((os.path.basename(path), fakestat))

class syncTest(unittest.TestCase):
    maxDiff=None

    def setUp(self):
        class args(object):
            sync_path=here+os.sep
            custom_set=None
            ignore_images=False
            ignore_videos=False
            is_windows=False
            ignore_ext=False
            dry_run=True
            download="."
            sync_from="all"

        self.local = fakeLocal()
        self.remote = fakeRemote()
        self.sync = Sync(args(), self.local, self.remote)

    def tearDown(self):
        pass

    def test_upload(self):
        expected = fakeRemote().files
        for f, s in list(self.local.files.values())[0]:
            list(expected.values())[0][f] = fakeid
        self.sync.upload()
        self.assertEquals(self.remote.files, expected)

    def test_download(self):
        expected = copy.deepcopy(fakeLocal().files)
        list(expected.values())[0] += [(x, fakestat) for x in list(self.remote.files.values())[0]]
        self.sync.download()
        self.assertEquals(self.local.files, expected)

    def test_sync(self):
        expectedr = fakeRemote().files
        for f, s in list(self.local.files.values())[0]:
            list(expectedr.values())[0][f] = fakeid
        expectedl = copy.deepcopy(fakeLocal().files)
        list(expectedl.values())[0] += [(x, fakestat) for x in list(self.remote.files.values())[0]]
        self.sync.sync()
        self.assertEquals(self.remote.files, expectedr)
        self.assertEquals(self.local.files, expectedl)

if __name__ == '__main__':
    logging.debug('Started test case')
    unittest.main(verbosity=2)
