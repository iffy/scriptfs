

# Installation #

    pip install git+https://github.com/iffy/scriptfs.git


# Basic Usage #

Pick a directory as the base directory and mount it in a different place:

    scriptfs /path/to/basedir /path/to/mountpoint

You should see all your files in `/path/to/mountpoint`.  Great... so what?

Now add a `.config.yml` file (in either the base directory or the mounted directory) with this content:

    - filename: now
      out_script: date
    - filename: google
      out_script: 'curl https://www.google.com'

You'll see a read-only file named `/path/to/mountpoint/now` that has the current date in it.  And the file `google` will have the contents of Google's homepage -- with a delay.  Do other cool things with scripts.


# Warnings #

This is really experimental.  Use at your own risk.  There are some locking issues when `out_script`s interact with other files in the mounted filesystem.  And the scripts run very frequently, so slow scripts will be very annoying.
