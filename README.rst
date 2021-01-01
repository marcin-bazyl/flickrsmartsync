flickrsmartsync - Sync/backup your photos to flickr easily
**********************************************************

flickrsmartsync is a tool you can use to easily sync up or down your
photos in a drive/folder to flickr since now it has a free 1TB storage
you can probably sync all your photo collection.


Install
=======

Simply run the following::

    $ python setup.py install

or `PyPi`_::

    $ pip install flickrsmartsync


Example Usage
==============

Both run from source and command line have same parameters::

    start uploading all photos/videos under that folder
    $ flickrsmartsync
    ignore videos for others use --help
    $ flickrsmartsync --ignore-videos

    start downloading all photos on flickr to that folder
    $ flickrsmartsync --download .

    start downloading all paths starting with that path
    $ flickrsmartsync --download 2008/2008-01-01

    for direct python access
    $ python flickrsmartsync


Links
=====
* `github.com`_ - source code
* `altlimit.com`_ - website
* `blog post`_ - blog post

.. _github.com: https://github.com/faisalraja/flickrsmartsync
.. _PyPi: https://pypi.python.org/pypi/flickrsmartsync
.. _altlimit.com: http://www.altlimit.com
.. _blog post: http://blog.altlimit.com/2013/05/backupsync-your-photos-to-flickr-script.html
