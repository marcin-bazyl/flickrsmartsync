from future import standard_library
standard_library.install_aliases()
from builtins import range
from builtins import object
import html
import json
import os
import re
import time
import urllib.request, urllib.parse, urllib.error
import flickrapi
import logging
import datetime
import exifread

logger = logging.getLogger("flickrsmartsync")

#  flickr api keys
KEY = '' # todo: read it from env var or somewhere... # 'f7da21662566bc773c7c750ddf7030f7'
SECRET = '' # todo: read it from env var or somewhere... # 'c329cdaf44c6d3f3'

SKIPPED_REMOTE_SETS = ["Auto Upload", "Gosia-temp"]  # these are skipped when doing sync (they're still downloaded if doing pure "download all"), WARNING: make sure you don't have a local folder with same name

# number of retries for downloads
RETRIES = 3

PERMISSIONS = 'write' # delete

VIDEO_FAKE_URL_PREFIX='PHOTO_ID='

class Remote(object):

    def __init__(self, cmd_args):
        # Command line arguments
        self.cmd_args = cmd_args
        self.auth_api()

        # Common arguments
        self.args = {'format': 'json', 'nojsoncallback': 1}

        # photo_sets_map[folder] = id
        self.update_photo_sets_map()

    def auth_api(self):
        self.api = flickrapi.FlickrAPI(
            KEY, SECRET, username=self.cmd_args.username
        )

        if self.cmd_args.manual_auth:
            self.manual_auth()
        else:
            self.api.authenticate_via_browser(perms=PERMISSIONS)

    # Manual authentication from a different computer
    def manual_auth(self):
        # Only if the token is not valid
        if not self.api.token_valid(PERMISSIONS):
            self.api.get_request_token(oauth_callback='oob')
            authorize_url = self.api.auth_url(perms=PERMISSIONS)

            logger.info('url for authentication: %s' % authorize_url)
            # Get the verifier code from the user. Do this however you
            # want, as long as the user gives the application the code.
            verifier = str(input('Verifier code: '))

            # Trade the request token for an access token
            self.api.get_access_token(verifier)

    def get_photo_set_title_from_path(self, path):
        title = path.split('/').pop()

        return title

    # For adding photo to set
    def add_to_photo_set(self, photo_id, folder):
        # If photoset not found in online map create it else add photo to it
        # Always upload unix style
        if self.cmd_args.is_windows:
            folder = folder.replace(os.sep, '/')

        if folder not in self.photo_sets_map:
            photosets_args = self.args.copy()
            title = self.get_photo_set_title_from_path(self.cmd_args.sync_path + folder)
            photosets_args.update({'primary_photo_id': photo_id,
                                   'title': title,
                                   'description': folder})
            photo_set = json.loads(self.api.photosets_create(**photosets_args))
            self.photo_sets_map[folder] = photo_set['photoset']['id']
            logger.info('Created set [%s] and added photo' % title)
        else:
            photosets_args = self.args.copy()
            photosets_args.update({'photoset_id': self.photo_sets_map.get(folder), 'photo_id': photo_id})
            result = json.loads(self.api.photosets_addPhoto(**photosets_args))
            if result.get('stat') == 'ok':
                logger.info('Successfully added photo to %s' % folder)
            else:
                logger.error(result)

    # Get photos in a set
    def get_photos_in_set(self, folder, get_url=False):
        # bug on non utf8 machines dups
        # folder = folder.encode('utf-8') if isinstance(folder, str) else folder

        photos = {}
        # Always upload unix style
        if self.cmd_args.is_windows:
            folder = folder.replace(os.sep, '/')

        if folder in self.photo_sets_map:
            photoset_args = self.args.copy()
            page = 1
            num_pages = 1
            while page <= num_pages:
                photoset_args.update({'photoset_id': self.photo_sets_map[folder], 'page': page})
                if get_url:
                    photoset_args['extras'] = 'url_o,media'
                logger.info("getting list of photos from flickr for set [{}] args={}".format(folder, photoset_args))
                photos_in_set = json.loads(self.api.photosets_getPhotos(**photoset_args))
                
                if photos_in_set['stat'] != 'ok':
                    break

                num_pages = photos_in_set['photoset']['pages']
                page += 1

                # todo: use photos_in_set['photoset']['page'] < photos_in_set['photoset']['pages']
                for photo in photos_in_set['photoset']['photo']:
                    title = photo['title'] #.encode('utf-8')
                    extension = "" # if the title is missing the extenstion, then we guess it and put it here
                    # add missing extension if not present (take a guess as api original_format argument not working)
                    split = title.split(".")
                    # assume valid file extension is less than or equal to 5 characters and not all digits
                    if len(split) < 2 or len(split[-1]) > 5 or split[-1].isdigit():
                        if photo.get('media') == 'video':
                            extension = ".mp4"
                        else:
                            extension = ".jpg"
                    else:
                        # because of all our problems with missing extensions, we always want to keep title without extension in our lookups and keep extension separately
                        extension = "." + split[-1]
                        title = title[:-(len(split[-1])+1)]

                    if get_url and photo.get('media') == 'video':
                        # for videos we have to do an extra API call to get the url and we don't want to do it unless we are actually downloading that video,
                        # so just put the photo id into the url for now and it will be used by the download() method
                        photos[title] = {'url': VIDEO_FAKE_URL_PREFIX + photo['id'], 'ext': extension}

                    else:
                        photos[title] = {'url': photo['url_o'] if get_url else photo['id'], 'ext': extension}

        return photos

    def get_photo_sets(self):
        return self.photo_sets_map

    def update_photo_sets_map(self):
        # Get your photosets online and map it to your local
        photosets_args = self.args.copy()
        page = 1
        self.photo_sets_map = {}

        while True:
            logger.debug('Getting photosets from flickr... page %s' % page)
            photosets_args.update({'page': page, 'per_page': 500})
            sets = json.loads(self.api.photosets_getList(**photosets_args))
            page += 1
            if not sets['photosets']['photoset']:
                break

            for current_set in sets['photosets']['photoset']:
                current_set_title = html.unescape(current_set['title']['_content'])
                # current_set_title = current_set_title.encode('utf-8') if isinstance(current_set_title, str) else current_set_title

                if current_set_title:
                    self.photo_sets_map[current_set_title] = current_set['id']

            for skipped_remote_set in SKIPPED_REMOTE_SETS:
                logger.info('Skipping remote set [%s]' % (skipped_remote_set))
                del self.photo_sets_map[skipped_remote_set]

    def set_photo_date(self, file_path, photo_id):
        '''Set photo date_taken and date_posted to file mtime

        See: https://www.flickr.com/services/api/flickr.photos.setDates.html
        '''
        file_mtime = os.path.getmtime(file_path)
        utc_time = datetime.datetime.utcfromtimestamp(file_mtime)

        try:
            tags = exifread.process_file(open(file_path, 'rb'), details=False)
            exiftime = None or \
                tags.get('Image DateTimeOriginal') or \
                tags.get('Image DateTime') or \
                tags.get('Image DateTimeDigized')

            if exiftime:
                utc_time = datetime.datetime(*map(int, re.split('[: ]', exiftime.printable)))

        except Exception as e:
            print (e)

        date_iso = utc_time.isoformat(' ')  # this is wrong it gives '2020-12-28 21:52:23.330000' while flickr accepts only up to seconds, so 2020-12-28 21:52:23, but we don't need this anyway

        self.api.photos.setDates(
            photo_id=photo_id,
            date_posted=date_iso,
            date_taken=date_iso,
            # date_taken_granularity=??
        )

    def upload(self, file_path, photo, folder):
        upload_args = {
            # (Optional) The title of the photo.
            'title': photo,
            # (Optional) A description of the photo. May contain some limited HTML.
            'description': folder,
            # (Optional) Set to 0 for no, 1 for yes. Specifies who can view the photo.
            'is_public': 0,
            'is_friend': 0,
            'is_family': 0,
            # (Optional) Set to 1 for Safe, 2 for Moderate, or 3 for Restricted.
            'safety_level': 1,
            # (Optional) Set to 1 for Photo, 2 for Screenshot, or 3 for Other.
            'content_type': 1,
            # (Optional) Set to 1 to keep the photo in global search results, 2 to hide from public searches.
            'hidden': 2
        }

        for retry in range(RETRIES):
            try:
                upload = self.api.upload(file_path, None, **upload_args)
                photo_id = upload.find('photoid').text
                # self.set_photo_date(file_path, photo_id)  - we don't need this, as flickr already extracts date taken from exif data
                self.add_to_photo_set(photo_id, folder) # todo: if it fails on this step the retry uploads the duplicate file unnecesarily
                return photo_id
            except Exception as e:
                back_off = 2**(retry + 3)
                logger.warning("Retrying (after delay of {} seconds) upload of {}/{} after error: {}".format(back_off, folder, photo, e))
                time.sleep(back_off)
                

        logger.error("Failed upload of %s/%s after %d retries" % (folder, photo, RETRIES))
        exit(0)

    def download(self, url, path):
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)

        if (url.startswith(VIDEO_FAKE_URL_PREFIX)):  # special case for videos
            photo_args = self.args.copy()
            photo_args['photo_id'] = url[len(VIDEO_FAKE_URL_PREFIX):]
            sizes = json.loads(self.api.photos_getSizes(**photo_args))
            if sizes['stat'] != 'ok':
                logger.error("Flickr API call photos.getSizes() failed for a video with photo_id={}".format(photo_args['photo_id']))
                return

            original = [s for s in sizes['sizes']['size'] if isinstance(s['label'], str) and s['label'].startswith('Video Original') and s['media'] == 'video']
            if original:
                url = original.pop()['source']
            else:
                logger.error("Flickr API call photos.getSizes() for a video with photo_id={} didn't return a 'Video Original' url".format(photo_args['photo_id']))
                return


        for i in range(RETRIES):
            try:
                return urllib.request.urlretrieve(url, path)
            except Exception as e:
                logger.warning("Retrying download of %s after error: %s" % (path, e))
        # failed many times
        logger.error("Failed to download %s after %d retries" % (path, RETRIES))
