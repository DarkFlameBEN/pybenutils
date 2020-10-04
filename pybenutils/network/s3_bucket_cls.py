import os
import time
import posixpath
import threading
from glob import glob
from boto.s3.key import Key
from typing import List, Union
from boto import log as boto_log
from pybenutils.utils_logger.config_logger import get_logger
from boto.exception import S3ResponseError
from boto.s3.connection import S3Connection
from multiprocessing.dummy import Pool as ThreadPool
from pybenutils.os_operations.files_and_directories import get_files_in_folder

logger = get_logger()
lock = threading.Lock()
boto_log.setLevel('WARNING')  # Added because boto prints passwords


class S3BucketManager(object):
    """A manager that helps with upload and download to/from s3 bucket"""
    DOWNLOAD_THREADS_NUM = 5
    UPLOAD_THREADS_NUM = 5
    DOWNLOAD_ATTEMPTS = 3

    def __init__(self, key, password, bucket_name):
        """
        :param key: Aws key
        :param password:  Aws password
        :param bucket_name: Bucket name
        """
        self.conn = S3Connection(aws_access_key_id=key, aws_secret_access_key=password)
        self.bucket_name = bucket_name
        try:
            self.bucket_obj = self.conn.get_bucket(self.bucket_name)
        except S3ResponseError as conn_err:
            if conn_err.message.lower() == 'access denied':
                raise AssertionError(f'Access denied for bucket "{bucket_name}": {str(conn_err)}')
            else:
                raise conn_err

    def upload_file(self, source, destination, public=True):
        """Upload source to s3 server.
         The uploaded file path will be '{}/{}'.format(destination, os.path.basename(source))

        :param source: Path of the local file to upload
        :param destination: Destination dir
        :param public: If we need to set the upload as public
        :return: Uploaded file path within the bucket
        """
        attempts = S3BucketManager.DOWNLOAD_ATTEMPTS
        for attempt in range(attempts):
            try:
                logger.info(f"upload from {source} to {destination}")
                k = self.bucket_obj.new_key(posixpath.join(destination, os.path.basename(source.strip())))
                k.set_contents_from_filename(source)
                if public:
                    k.make_public()
                uploaded_file_url = 'http://{bucket}.s3.amazonaws.com/{key}'.format(bucket=self.bucket_name, key=k.key)
                logger.info('Successfully uploaded to {url}'.format(url=uploaded_file_url))
                return uploaded_file_url
            except Exception as ex:
                logger.error('Attempt {num}/{max_attempts} failed with error:{err}'.format(
                    num=attempt + 1, max_attempts=attempts, err=str(ex)))
                if attempt + 1 < attempts:
                    time.sleep(10)
                else:
                    raise ex

    def upload(self, source_list: Union[str, List[str]],
               destination: str,
               public=True,
               exclude_list: Union[str, List[str]] = '') -> List[str]:
        """An improved method to upload multiple sources to Amazon s3 server. The list can contain a file path to upload
         or a folder to upload all its content. If the source is a file, it will be uploaded directly to the s3
         destination dir. If the source is a folder, its content will be uploaded with the same hierarchical order
         (without the root dir) in the s3 destination dir.

        :param source_list: A list sources to upload (Files & Folders). Supports glob string patterns
        :param destination: Destination folder (Inside the bucket)
        :param public: Adds read permission to Everyone for the file uploaded
        :param exclude_list: List of paths to exclude (Files & Folders). Supports glob string patterns
        :return: A list of urls pointing to the uploaded files
        """

        def _upload_file_wrapper(tup):
            """A wrapper to self.upload_file_to_s3 that allows to use it in pool.map. Takes a tuple of variables and
             invokes self.upload_file_to_s3 with them as single args

            :param tup: a tuple of argument
            :return: the result of self.upload_file_to_s3 with the given input
            """
            return self.upload_file(*tup)

        source_list = source_list if type(source_list) == list else [source_list]
        if exclude_list:
            exclude_list = exclude_list if type(exclude_list) == list else [exclude_list]
        else:
            exclude_list = []  # Handling cases of empty / None exclude list

        # Building the extended files exclude list
        extended_exclude_list = []
        for exclude_item in exclude_list:
            for source in glob(exclude_item):
                source = os.path.realpath(source)
                extended_exclude_list.append(source)
                if os.path.isdir(source):
                    upload_list_from_folder = get_files_in_folder(source)
                    for file_path in upload_list_from_folder:
                        extended_exclude_list.append(file_path)

        # Building the upload details list - excluding paths as needed
        upload_details_list = []
        for unfiltered_source in source_list:
            for source in glob(unfiltered_source):
                source = os.path.realpath(source)
                if os.path.isfile(source):
                    if source not in extended_exclude_list:
                        upload_details = (source, destination, public)
                        upload_details_list.append(upload_details)
                elif os.path.isdir(source):
                    upload_list_from_folder = get_files_in_folder(source)
                    for file_path in upload_list_from_folder:
                        if file_path in extended_exclude_list:
                            continue
                        relative_path = os.path.dirname(file_path.split(source)[-1])
                        destination = '{base}{rel}'.format(base=destination, rel=relative_path.replace('\\', '/'))
                        upload_details = (file_path, destination, public)
                        upload_details_list.append(upload_details)
                else:
                    logger.info('Could not validate source for {source}. Skipping...'.format(source=source))

        pool = ThreadPool(S3BucketManager.UPLOAD_THREADS_NUM)
        uploaded_files_list = pool.map(_upload_file_wrapper, upload_details_list)
        pool.close()
        pool.join()
        return uploaded_files_list

    def get_s3_folder_content(self, s3_folder):
        """Returns the relative paths of all the objects in the given s3 folder, files and directories, recursively.
         The paths includes the root dir (s3_folder input). Directories ends with '/'

        :param s3_folder: S3 folder to examine
        :return: A list of relative paths of the objects insides the input folder
        """
        return [key.key for key in self.bucket_obj.list(prefix=s3_folder)]

    def download_file(self, source, destination):
        """Download source from s3 server. if destination is a file, the download file path will be the same. If it's a
         folder, the download file path will be '{}/{}'.format(destination, os.path.basename(source))

        :param source: Relative path of the file inside the bucket
        :param destination: Local path of the directory or file the file should be downloaded to
        """
        if '.' in destination[-5:]:  # the destination is a file path and not a folder
            dest_file_path = destination
        else:
            dest_file_path = os.path.join(destination, os.path.basename(source))
        logger.info(f'Download file from "{source}" to "{dest_file_path}"')

        destination_dir = os.path.dirname(dest_file_path)
        if not destination_dir:
            destination_dir = os.getcwd()
        with lock:
            if not os.path.exists(destination_dir):
                os.makedirs(destination_dir)
        if not os.path.exists(destination_dir):
            return

        k = Key(self.bucket_obj)
        k.key = source
        k.get_contents_to_filename(dest_file_path)
        return dest_file_path

    def download(self, source_list, destination):
        """Download folder content from s3 server. The list can contain an s3 folder name or an s3 file relative path.
        If the source is a folder, its content will be downloaded with the same hierarchical order (without the root
        dir) in the destination dir. if the source is a file, it will be downloaded directly to the destination dir

        :param source_list: List of s3 sources, files and folders
        :param destination: Destination dir
        :return: A list of the newly added files paths
        """

        def _download_file_wrapper(tup):
            """A wrapper to self.download_file_from_s3 that allows to use it in pool.map. Takes a tuple of variables
             and invokes self.download_file_from_s3 with them as single args

            :param tup: Tuple of argument
            :return: The result of self.download_file_from_s3 with the given input
            """
            return self.download_file(*tup)

        source_list = source_list if isinstance(source_list, list) else [source_list]
        download_details_list = []
        for source in source_list:
            source = source.strip('/')
            k = self.bucket_obj.get_key(source)  # check if source is a file (s3 key) or a folder
            if k:
                download_details_list.append((source, destination))
            else:  # source is a folder
                for key in self.bucket_obj.list(prefix=source):
                    relative_url = key.key
                    sub_folder = os.path.dirname(relative_url).split(source)[-1].strip('/')
                    destination = os.path.join(destination, sub_folder) if sub_folder else destination
                    download_details_list.append((relative_url, destination))

        pool = ThreadPool(S3BucketManager.DOWNLOAD_THREADS_NUM)
        download_list = pool.map(_download_file_wrapper, download_details_list)
        pool.close()
        pool.join()
        return download_list

    def delete_key_from_bucket(self, key_to_delete):
        """Delete file or folder from given s3 path

        :param key_to_delete: Folder or file path to delete
        """
        self.bucket_obj.delete_key(key_to_delete)
