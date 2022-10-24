#!/usr/bin/env bash

# 1. First get datetime from exif
#   a. exiftool
#   b. jhead (for manipulation)
# 2. If not found, get from filename
#   .*(?P<year>\d{4})[_\-\.]?(?P<month>\d{2})[_\-\.]?(?P<day>\d{2})[_\-T](?P<hour>\d{2})[_\-\.]?(?P<minute>\d{2})[_\-\.]?(?P<second>\d{2}).*
# 3. If not found, get from folder name
# 4. If not in filename, mark "unknown"
# 5. Group by events
#   a. set max gap to be considered same event
#   b. set min gap to be considered separate event
#   c. adjust max and min if location the same?
# 6. Move to folders
#   - folder name needs to be special for events that cross midnight

# Photo clustering algorithms (Temporal Event Clustering)
#   - https://www.researchgate.net/publication/2875653_Temporal_Event_Clustering_for_Digital_Photo_Collections
#   - https://dl.acm.org/doi/10.1145/957013.957093
# Univariate clustering / segmentation / natural breaks optimization / 1D discretization/quantization
#   - https://cran.r-project.org/web/packages/Ckmeans.1d.dp/index.html
#   - https://stackoverflow.com/questions/35094454/how-would-one-use-kernel-density-estimation-as-a-1d-clustering-method-in-scikit/35151947#35151947
#   - https://stackoverflow.com/questions/11513484/1d-number-array-clustering
#   - https://pypi.org/project/ckwrap/
#   - https://stackoverflow.com/questions/11513484/1d-number-array-clustering
#   - https://stackoverflow.com/questions/18364026/clustering-values-by-their-proximity-in-python-machine-learning

get-date() {
    exiftool -T -d "%Y-%m-%dT%H-%M-%S" -DateTimeOriginal "$1"
    echo "$?"
}

process-file() {
    if file "$1" | grep -o -P '^.+: \w+ (image|bitmap|video)' > /dev/null ; then
        get-date "$1"
    fi
}

export -f get-date
export -f process-file

get-media() {
    find "$1" -type f -exec bash -c 'process-file "$@"' bash {} \;
}

get-media "$1"
