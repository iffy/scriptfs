

## Installation ##

    pip install git+https://github.com/iffy/scriptfs.git


# WARNING #

Do not mount untrusted directories!  Mounting directories will potentially execute scripts defined in the base directory.  Consider this malicious `.config.yml`:

    - filename: sucker
      out_script: rm all_the_things

Also, this is really experimental.  Use at your own risk.


# Usage #

## Kitchen sink example

See the `example/` directory (specifically [example/basic/.config.yml](example/basic/.config.yml)).  For instance, after installing, do this:

    scriptfs examples/basic /tmp/dump
    cat /tmp/dump/.config.yml
    cat /tmp/dump/now
    cat /tmp/dump/bob


## Other usage

Pick a directory as the base directory and mount it in a different place:

    scriptfs /path/to/basedir /path/to/mountpoint

You should see all your files in `/path/to/mountpoint`.  Great... so what?

Now add a `.config.yml` file (in either the base directory or the mounted directory) with this content:

    - filename: now
      out_script: date
    - filename: google
      out_script: 'curl https://www.google.com'

You'll see a read-only file named `/path/to/mountpoint/now` that has the current date in it.  And the file `google` will have the contents of Google's homepage -- with a delay.  Do other cool things with scripts.



# Bugs #

Report bugs on [github](https://github.com/iffy/scriptfs).

Known bugs include:

- There are some locking issues when `out_script`s interact with other files in the mounted filesystem.

