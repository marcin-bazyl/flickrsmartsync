from builtins import input
from builtins import object
import os
import logging

logger = logging.getLogger("flickrsmartsync")

EXT_IMAGE = ('jpg', 'png', 'jpeg', 'gif', 'bmp')
EXT_VIDEO = ('avi', 'wmv', 'mov', 'mp4', '3gp', 'ogg', 'ogv', 'mts')

VIDEO_MAX_SIZE = 1 * 1024 * 1024 * 1024 # 1GB
IMAGE_MAX_SIZE = 200 * 1024 * 1024      # 200MB

class Sync(object):

    def __init__(self, cmd_args, local, remote):
        global EXT_IMAGE, EXT_VIDEO
        self.cmd_args = cmd_args
        # Create local and remote objects
        self.local = local
        self.remote = remote
        # Ignore extensions
        if self.cmd_args.ignore_ext:
            extensions = self.cmd_args.ignore_ext.split(',')
            EXT_IMAGE = [e for e in EXT_IMAGE if e not in extensions]
            EXT_VIDEO = [e for e in EXT_VIDEO if e not in extensions]

    def start_sync(self):
        # Do the appropriate one time sync
        if self.cmd_args.download:
            self.download()
        elif self.cmd_args.sync_from:
            self.sync()
        else:
            self.upload()
            logger.info('Upload done')
            if self.cmd_args.monitor:
                self.local.watch_for_changes(self.upload)
                self.local.wait_for_quit()

    def sync(self):
        if self.cmd_args.sync_from == "all":
            local_photo_sets = self.local.build_photo_sets(
                self.cmd_args.sync_path,
                EXT_IMAGE + EXT_VIDEO
            )
            remote_photo_sets = self.remote.get_photo_sets()

            # First download complete remote sets that are not local
            for remote_photo_set in remote_photo_sets:
                local_photo_set = os.path.join(
                    self.cmd_args.sync_path, remote_photo_set
                ).replace("/", os.sep)

                if local_photo_set not in local_photo_sets:
                    # TODO: will generate info messages if photo_set is a suffix to other set names
                    self.cmd_args.download = local_photo_set
                    self.download()

            # Now walk our local sets
            for local_photo_set in sorted(local_photo_sets):
                remote_photo_set = local_photo_set.replace(self.cmd_args.sync_path, '').replace("/", os.sep)
                logger.info('Syncing local folder [{}]'.format(local_photo_set))
                if remote_photo_set not in remote_photo_sets:
                    logger.info('Set [{}] not among remote photo sets, all of the photos will be uploaded'.format(remote_photo_set))
                    # doesn't exist remotely, so all files need uploading
                    remote_photos = {}
                else:
                    # filter by what exists remotely, this is a dict of filename->{url, ext}
                    remote_photos = self.remote.get_photos_in_set(remote_photo_set, get_url=True)
                local_photos = local_photo_sets[local_photo_set]

                # download what doesn't exist locally
                for photo in [photo for photo in remote_photos if photo not in local_photos]:
                    if self.cmd_args.dry_run:
                        logger.info('Would download [%s] from %s to [%s] (ext=%s)' % (photo, remote_photos[photo]['url'], local_photo_set, remote_photos[photo]['ext']))
                    else:
                        logger.info('Downloading [%s] from %s to [%s] (ext=%s)' % (photo, remote_photos[photo]['url'], local_photo_set, remote_photos[photo]['ext']))
                        self.remote.download(remote_photos[photo]['url'], os.path.join(local_photo_set, photo + remote_photos[photo]['ext']))

                # upload what doesn't exist remotely
                for photo in [photo for photo in local_photos if photo not in remote_photos]:
                    file_path = os.path.join(local_photo_set, photo + local_photos[photo]['ext'])
                    file_stat = os.stat(file_path)
                    file_extension = local_photos[photo]['ext'] # includes a dot at beginning

                    # Adds skips
                    if self.cmd_args.ignore_images and file_extension[1:].lower() in EXT_IMAGE:
                        continue
                    elif self.cmd_args.ignore_videos and file_extension[1:].lower() in EXT_VIDEO:
                        continue

                    # Skip files too large
                    if file_stat.st_size >= IMAGE_MAX_SIZE and file_extension[1:].lower() in EXT_IMAGE:
                        logger.error('Skipped [%s] over image size limit' % photo)
                        continue
                    if file_stat.st_size >= VIDEO_MAX_SIZE and file_extension[1:].lower() in EXT_VIDEO:
                        logger.error('Skipped [%s] over video size limit' % photo)
                        continue

                    display_title = self.remote.get_photo_set_title_from_path(local_photo_set)
                    if self.cmd_args.dry_run:
                        logger.info('Would upload [%s] to set [%s]' % (photo + file_extension, display_title))
                    else:
                        logger.info('Uploading [%s] to set [%s]' % (photo + file_extension, display_title))
                        self.remote.upload(file_path, photo + file_extension, remote_photo_set)

        else:
            logger.warning("Unsupported sync option: %s" % self.cmd_args.sync_from)

    def download(self):
        # Download to corresponding paths
        for photo_set in self.remote.get_photo_sets():
            if photo_set and (self.cmd_args.download == '.' or self.cmd_args.download.endswith(photo_set)):
                folder = os.path.join(self.cmd_args.sync_path, photo_set)
                logger.info('Getting photos in set [%s]' % photo_set)
                photos = self.remote.get_photos_in_set(photo_set, get_url=True)
                # If Uploaded on unix and downloading on windows & vice versa
                if self.cmd_args.is_windows:
                    folder = folder.replace('/', os.sep)

                for photo in photos:
                    # Adds skips
                    if self.cmd_args.ignore_images and photos[photo]['ext'][1:].lower() in EXT_IMAGE:
                        continue
                    elif self.cmd_args.ignore_videos and photos[photo]['ext'][1:].lower() in EXT_VIDEO:
                        continue
                    path = os.path.join(folder, photo + photos[photo]['ext'])
                    upper_case_ext_path = os.path.join(folder, photo + photos[photo]['ext'].upper())

                    if os.path.exists(path):
                        logger.debug('Skipped [%s/%s] already downloaded' % (photo_set, photo))
                    elif os.path.exists(upper_case_ext_path):
                        logger.debug('Skipped [%s/%s] already downloaded' % (photo_set, photo))
                    # todo: for movies, try also avi/AVI/mov/MOV/3gp/3GP/mpg/MPG                                
                    elif self.cmd_args.dry_run:
                        logger.info('Would download photo [%s/%s] to path [%s]' % (photo_set, photo, path))
                    else:
                        logger.info('Downloading photo [%s/%s] to path [%s]' % (photo_set, photo, path))
                        self.remote.download(photos[photo]['url'], path)

    def upload(self, specific_path=None):
        if specific_path is None:
            only_dir = self.cmd_args.sync_path
        else:
            only_dir = os.path.dirname(specific_path)
        photo_sets = self.local.build_photo_sets(only_dir, EXT_IMAGE + EXT_VIDEO)
        logger.info('Found %s photo sets' % len(photo_sets))

        # Loop through all local photo set map and
        # upload photos that does not exists in online map
        for photo_set in sorted(photo_sets):
            folder = photo_set.replace(self.cmd_args.sync_path, '')
            display_title = self.remote.get_photo_set_title_from_path(photo_set)
            logger.info('Getting photos in set [%s]' % display_title)
            photos = self.remote.get_photos_in_set(folder)
            logger.info('Found %s photos' % len(photos))

            for photo in photo_sets[photo_set]:
                file_extension = photo_sets[photo_set][photo]['ext'] # includes a dot at beginning
                file_stat = photo_sets[photo_set][photo]['file_stat']
                photo_with_extension = photo + file_extension

                # Adds skips
                if self.cmd_args.ignore_images and file_extension[1:].lower() in EXT_IMAGE:
                    continue
                elif self.cmd_args.ignore_videos and file_extension[1:].lower() in EXT_VIDEO:
                    continue

                if photo in photos or self.cmd_args.is_windows and photo.replace(os.sep, '/') in photos:
                    logger.debug('Skipped [%s] already exists in set [%s]' % (photo_with_extension, display_title))
                else:
                    # Skip files too large
                    if file_stat.st_size >= IMAGE_MAX_SIZE and file_extension[1:].lower() in EXT_IMAGE:
                        logger.error('Skipped [%s] over image size limit' % photo_with_extension)
                        continue
                    if file_stat.st_size >= VIDEO_MAX_SIZE and file_extension[1:].lower() in EXT_VIDEO:
                        logger.error('Skipped [%s] over video size limit' % photo_with_extension)
                        continue

                    if self.cmd_args.dry_run:
                        logger.info('Would upload [%s] to set [%s]' % (photo_with_extension, display_title))
                        continue

                    logger.info('Uploading [%s] to set [%s]' % (photo_with_extension, display_title))
                    file_path = os.path.join(photo_set, photo_with_extension)
                    photo_id = self.remote.upload(file_path, photo_with_extension, folder)
                    if photo_id:
                        photos[photo] = {'url': photo_id, 'ext': file_extension}