#!/usr/bin/env python

import filetype
import numpy as np
import os
import re
import scipy.cluster.hierarchy as hcluster
import shutil
import time
from datetime import datetime
from dateutil import parser
from exif import Image as Image_exif
from ffprobe import FFProbe
from pathlib import Path
from PIL import Image, ExifTags
from sklearn.cluster import MeanShift, estimate_bandwidth

filtered_patterns = [
    '.*\\.thumbnails.*',
    '.*\\.csv',
    '.*\\.dmg',
    # '.*\\.dtrash.*',
    '.*\\.json',
    '.*\\.pdg',
    '.*\\.txt',
    '.*\\.swf',
    '.*\\.xml',
]

ignored_patterns = [
    '.*@eaDir.*',
    '.*SynoEAStream',
    '.*SYNOINDEX_MEDIA_INFO.*',
    '.*SYNOINDEX_VIDEO_METADATA.*',
]

filtered_patterns_combined = '(' + ')|('.join(filtered_patterns) + ')'
filtered_re = re.compile(filtered_patterns_combined)
ignored_patterns_combined = '(' + ')|('.join(ignored_patterns) + ')'
ignored_re = re.compile(ignored_patterns_combined)

path_date_re = re.compile(r'.*(?P<year>\d{4})[_\-\.]?(?P<month>\d{2})[_\-\.]?(?P<day>\d{2})[_\-T](?P<hour>\d{2})[_\-\.]?(?P<minute>\d{2})[_\-\.]?(?P<second>\d{2}).*')
manual_path_date_re = re.compile(r'.*(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}) - .*')

def get_date_from_path(path, match_folder_date=False):
    filename = os.path.basename(path)
    m = path_date_re.match(filename)
    if m is None:
        if match_folder_date:
            # Match against date in folder name
            m = manual_path_date_re.match(path)
            if m is None:
                return None
            date_data = m.groupdict()
            date_string = '{}:{}:{} 00:00:00'.format(
                date_data['year'],
                date_data['month'],
                date_data['day'],
            )
        else:
            return None
    else:
        date_data = m.groupdict()
        date_string = '{}:{}:{} {}:{}:{}'.format(
            date_data['year'],
            date_data['month'],
            date_data['day'],
            date_data['hour'],
            date_data['minute'],
            date_data['second'],
        )

    try:
        creation_datetime = datetime.strptime(date_string, '%Y:%m:%d %H:%M:%S')
    except ValueError:
        # Invalid date
        return None
    creation_ts = time.mktime(creation_datetime.timetuple())
    return creation_ts

def get_image_date(path):
    im = Image.open(path)
    exif = im.getexif()
    # exif.get(36867)
    exif_tags = { ExifTags.TAGS[k]: v for k, v in exif.items() if k in ExifTags.TAGS and type(v) is not bytes }
    creation_date = None
    if 'DateTimeOriginal' in exif_tags:
        creation_date = exif_tags['DateTimeOriginal']
    elif 'DateTime' in exif_tags:
        creation_date = exif_tags['DateTime']
    if creation_date is None:
        with open(path, 'rb') as img_file:
            try:
                # PIL exif library sometimes has problems, so try another
                img = Image_exif(img_file)
                try:
                    creation_date = img.get('datetime_original')
                except KeyError:
                    # Can't find the exif tag
                    pass
            except:
                # Some files can't be opened by this lib
                pass

    if creation_date is None:
        return get_date_from_path(path)
    try:
        creation_datetime = datetime.strptime(creation_date, '%Y:%m:%d %H:%M:%S')
    except ValueError:
        try:
            creation_datetime = parser.parse(creation_date)
        except:
            return None

    creation_ts = time.mktime(creation_datetime.timetuple())
    return creation_ts

def get_video_date(path):
    try:
        video_data = FFProbe(path)
    except:
        return get_date_from_path(path)
    if 'creation_time' in video_data.metadata:
        try:
            creation_datetime = datetime.strptime(video_data.metadata['creation_time'], '%Y-%m-%dT%H:%M:%S.%fZ')
        except:
            creation_datetime = datetime.strptime(video_data.metadata['creation_time'], '%Y-%m-%d %H:%M:%S')
        creation_ts = time.mktime(creation_datetime.timetuple())
        return creation_ts
    return get_date_from_path(path)

def process_media_list(path):
    for path_obj in Path(path).rglob('*'):
        path = str(path_obj.absolute())
        try:
            mtime = os.path.getmtime(path)
        except FileNotFoundError:
            # Probably a special synology file
            continue
        if path_obj.is_dir():
            continue
        if ignored_re.match(path):
            continue
        if filtered_re.match(path):
            yield {
                'type': 'filtered',
                'path': path,
                'mtime': mtime,
            }
            continue

        creation_datetime = None
        file_kind = filetype.guess(path)
        if file_kind is not None:
            if file_kind.mime[0:5] == 'image':
                creation_ts = get_image_date(path)
                if creation_ts is not None:
                    # @TODO: This might not be using the right timezone
                    creation_datetime = time.strftime('%a, %d %b %Y %H:%M:%S %Z', time.localtime(creation_ts))

                yield {
                    'type': 'image',
                    'mime': file_kind.mime,
                    'path': path,
                    'creation_ts': creation_ts,
                    'creation_datetime': creation_datetime,
                    'mtime': mtime,
                }
            elif file_kind.mime[0:5] == 'video':
                creation_ts = get_video_date(path)
                if creation_ts is not None:
                    # @TODO: This might not be using the right timezone
                    creation_datetime = time.strftime('%a, %d %b %Y %H:%M:%S %Z', time.localtime(creation_ts))
                yield {
                    'type': 'video',
                    'mime': file_kind.mime,
                    'path': path,
                    'creation_ts': creation_ts,
                    'creation_datetime': creation_datetime,
                    'mtime': mtime,
                }
            else:
                yield {
                    'type': 'other',
                    'mime': file_kind.mime,
                    'path': path,
                    'mtime': mtime,
                }
        else:
            yield {
                'type': 'unknown',
                'path': path,
                'mtime': mtime,
            }

# See: https://stackoverflow.com/questions/18364026/clustering-values-by-their-proximity-in-python-machine-learning
def cluster_dates(dates):
    date_array = np.array(dates)
    zero_array = np.zeros(len(dates))
    X = np.column_stack((date_array, zero_array))
    bandwidth = estimate_bandwidth(X, quantile=0.3)
    ms = MeanShift(bandwidth=bandwidth, bin_seeding=True)
    ms.fit(X)
    labels = ms.labels_
    cluster_centers = ms.cluster_centers_

    labels_unique = np.unique(labels)
    n_clusters_ = len(labels_unique)

    for k in range(n_clusters_):
        my_members = labels == k
        print('cluster {0}: {1}'.format(k, X[my_members, 0]))

def cluster_scipy(dates):
    # 4 hour threshold
    thresh = 240
    date_array = np.array(dates)
    zero_array = np.zeros(len(dates))
    X = np.column_stack((date_array, zero_array))
    clusters = hcluster.fclusterdata(X, thresh, criterion='distance')
    print(clusters)

# source = '/mnt/ellis/Photos - sorted - take 2/media_mtime2'
source = '/mnt/ellis/Photos - to sort'
destination = '/mnt/ellis/Photos - sorted - take 2'

for file_data in process_media_list(source):
    if file_data['type'] == 'image' or file_data['type'] == 'video':
        if 'creation_ts' in file_data and file_data['creation_ts'] is not None:
            datetime_path = time.strftime('%Y-%m-%d', time.localtime(file_data['creation_ts']))
            dest_dir = '{}/media_dated/{}'.format(destination, datetime_path)
        else:
            datetime_path = time.strftime('%Y-%m-%d', time.localtime(file_data['mtime']))
            dest_dir = '{}/media_mtime/{}'.format(destination, datetime_path)
    else:
        dest_dir = '{}/{}'.format(destination, file_data['type'])
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(file_data['path'])
    dest_path = '{}/{}'.format(dest_dir, filename)
    print('{} --> {}'.format(file_data['path'], dest_path))
    shutil.move(file_data['path'], dest_path)
