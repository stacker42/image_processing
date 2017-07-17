Installation
============

Dependencies
------------

To install this software, the following dependencies must first be installed:

- Python 2.7
- virtualenv
- SExtractor
- mariadb-devel
- imagemagick
- astrometry.net (which itself has dependencies)
    - GNU build tools (gcc/clang, make, etc.)
    - cairo
    - netpbm
    - libpng
    - libjpeg
    - libz
    - bzip2
    - cfitsio: http://heasarc.gsfc.nasa.gov/fitsio/
    - swig
- a web server (this guide has instructions for Apache2)



There are also a number of Python 2.7 libraries that need to be installed:

- django
- django-registration-redux
- pyfits
- numpy
- scipy
- astropy
- matplotlib
- mysql-python

Installing astrometry.net
-------------------------

The astrometry.net astrometry package needs to be compiled from source.

There are some good instructions here: http://plaidhat.com/code/astrometry.php

But - add

$ make py

to the astrometry.net make stages

And you can use the wget.sh script (in the index files directory) to download the index files required.

Installing HOYS-CAPS image processor
------------------------------------

Download the source to a convenient location.
Make sure your webserver has read/write/execute permissions for all files.

Copy image_processing/settings.py.sample to image_processing/settings.py and edit settings appropriately -
especially the paths to the directories that store data permanently and temporarily, database settings and paths to
binaries.

Data folders do not need to be in the folder containing the source files - just anywhere the web server can read and write to.

Once you have made all needed changes to the settings, you can run the following commands:


$ python manage.py makemigrations

and

$ python manage.py migrate


These will make any nessasary database migrations (which can be none) and apply all migrations to the database, which
with a fresh installation will make all the needed tables etc.

You now need to create a superuser account for the site.
Run the following and follow the prompts

$ python manage.py createsuperuser


This superuser can access the admin site at example.com/admin and manage users and their staff status.

Finally, head on over to the site and log in!

