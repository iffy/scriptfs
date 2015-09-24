
from time import time
from stat import S_IFREG
from functools import wraps

#from StringIO import StringIO

import errno
import yaml
#import re
import traceback
import sys
import os
from os.path import realpath
from threading import Lock
from weakref import WeakKeyDictionary

import subprocess

from fuse import FUSE
from fuse import LoggingMixIn, Operations, FuseOSError

if not hasattr(__builtins__, 'bytes'):
    bytes = str


class File(object):
    """
    I correspond to a real file or path.
    """

    def __init__(self, fs, root):
        self.fs = fs
        self.root = realpath(root)
        self.rwlock = Lock()

    def __repr__(self):
        return '<%s 0x%x %r>' % (self.__class__.__name__, id(self), self.root)

    def child(self, segment):
        return File(self.fs, os.path.join(self.root, segment))

    def access(self, mode):
        if not os.access(self.root, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, *args, **kwargs):
        os.chmod(self.root, *args, **kwargs)

    def chown(self, *args, **kwargs):
        os.chown(self.root, *args, **kwargs)

    def create(self, mode):
        return os.open(self.root, os.O_WRONLY | os.O_CREAT, mode)

    def flush(self, fh):
        return os.fsync(fh)

    def fsync(self, datasync, fh):
        return os.fsync(fh)

    def getattr(self, fh=None):
        st = os.lstat(self.root)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def getxattr(self, name, position=0):
        raise FuseOSError(errno.EACCES)

    def link(self, target, source):
        return os.link(source, target)

    def listxattr(self):
        return []

    def mkdir(self, *args, **kwargs):
        return os.mkdir(self.root, *args, **kwargs)

    def mknod(self, *args, **kwargs):
        return os.mknod(self.root, *args, **kwargs)

    def open(self, *args, **kwargs):
        return os.open(self.root, *args, **kwargs)

    def read(self, size, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset, 0)
            return os.read(fh, size)

    def listRealChildren(self):
        return os.listdir(self.root)

    def readdir(self, fh):
        return ['.', '..'] + self.listRealChildren()

    def readLink(self, *args, **kwargs):
        return os.readlink(self.root, *args, **kwargs)

    def release(self, fh):
        return os.close(fh)

    def rename(self, old, new):
        return os.rename(old, self.root + new)

    def rmdir(self, *args, **kwargs):
        return os.rmdir(self.root, *args, **kwargs)

    def setxattr(self, name, value, options, position=0):
        pass

    def statfs(self):
        stv = os.statvfs(self.root)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def symlink(self, target, source):
        return os.symlink(source, target)

    def truncate(self, length, fh=None):
        with open(self.root, 'r+') as f:
            f.truncate(length)

    def unlink(self, *args, **kwargs):
        return os.unlink(self.root, *args, **kwargs)

    def utimens(self, *args, **kwargs):
        return os.utime(self.root, *args, **kwargs)

    def write(self, data, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset, 0)
            return os.write(fh, data)


class DynamicAwareFile(File):


    def child(self, segment):
        if segment in self.listRealChildren():
            return DynamicAwareFile(self.fs, os.path.join(self.root, segment))
        else:
            return self.dynamicSettings().getFile(self.fs, segment)

    def dynamicSettings(self):
        config_file = os.path.join(self.root, '.config.yml')
        data = []
        if os.path.exists(config_file):
            fh = open(config_file, 'rb')
            data = yaml.safe_load(fh)
        return DynamicSettings(config_file, data)

    # ------- fuse stuff

    def readdir(self, fh):
        static = File.readdir(self, fh)
        d = self.dynamicSettings()
        return static + d.listFiles()



class DynamicSettings(object):


    def __init__(self, config_file, data):
        self.data = data or []
        self.config_file = config_file


    def listFiles(self):
        return [x['filename'] for x in self.data]


    def getFile(self, fs, filename):
        for item in self.data:
            if item['filename'] == filename:
                workdir = item.get('workdir', '') or os.path.dirname(self.config_file)
                return ScriptFile(fs=fs,
                    workdir=workdir,
                    out_script=item['out_script'],
                    env=item.get('env', None))


_cache = WeakKeyDictionary()
_cache_last_run = WeakKeyDictionary()

class _CacheKey(object):

    def __init__(self, *args):
        self.args = args


def cache(f):
    @wraps(f)
    def deco(self, *args, **kwargs):
        # a string?  really?
        cache_key = getattr(self, '__cache_key__', None)
        if not cache_key:
            self.__cache_key__ = cache_key = _CacheKey(self, f)
        last_run = _cache_last_run.get(cache_key, 0)
        now = time()
        if last_run < (now - 1) or cache_key not in _cache:
            _cache[cache_key] = f(self, *args, **kwargs)
            _cache_last_run[cache_key] = now
        else:
            print 'cached'
        return _cache[cache_key]
    return deco


class ScriptFile(object):

    def __init__(self, fs, workdir, out_script, env=None):
        self.out_script = out_script
        self.workdir = workdir
        self.env = env or {}
        self.fs = fs

    @cache
    def _runOutputScript(self):
        try:
            args = self.out_script
            print 'args', repr(args)
            env = os.environ.copy()
            env.update(self.env)
            env['ROOT'] = self.fs.mountpoint
            print 'cwd', repr(self.workdir)
            p = subprocess.Popen(self.out_script,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=self.workdir)
            out, err = p.communicate('')
            print 'out?', repr(out)
            print 'err?', repr(err)
            return out
        except Exception as e:
            print 'traceback', e
            return traceback.format_exc(e)

    def get_size(self):
        return len(self._runOutputScript())

    def access(self, mode):
        pass

    def chmod(self, *args, **kwargs):
        raise FuseOSError(errno.EACCES)
        os.chmod(self.root, *args, **kwargs)

    def chown(self, *args, **kwargs):
        raise FuseOSError(errno.EACCES)
        os.chown(self.root, *args, **kwargs)

    def create(self, mode):
        raise FuseOSError(errno.EACCES)

    def flush(self, fh):
        return os.fsync(fh)

    def fsync(self, datasync, fh):
        return os.fsync(fh)    

    def getattr(self, fh=None):
        return dict(
            st_mode=(S_IFREG | 0440),
            st_nlink=1,
            st_size=self.get_size(),
            st_ctime=0,
            st_mtime=0,
            st_atime=0)

    getxattr = None

    def link(self, target, source):
        raise FuseOSError(errno.EACCES)

    listxattr = None

    def mkdir(self, *args, **kwargs):
        raise FuseOSError(errno.EACCES)

    def mknod(self, *args, **kwargs):
        raise FuseOSError(errno.EACCES)

    def open(self, *args, **kwargs):
        return 0

    def read(self, size, offset, fh):
        return self._runOutputScript()[offset:offset + size]

    def readdir(self, fh):
        raise FuseOSError(errno.EACCES)

    def readLink(self, *args, **kwargs):
        raise FuseOSError(errno.EACCES)

    def release(self, fh):
        raise FuseOSError(errno.EACCES)

    def rename(self, old, new):
        raise FuseOSError(errno.EACCES)

    def rmdir(self, *args, **kwargs):
        raise FuseOSError(errno.EACCES)

    def symlink(self, target, source):
        raise FuseOSError(errno.EACCES)

    def truncate(self, length, fh=None):
        raise FuseOSError(errno.EACCES)

    def unlink(self, *args, **kwargs):
        raise FuseOSError(errno.EACCES)

    def utimens(self, *args, **kwargs):
        raise FuseOSError(errno.EACCES)

    def write(self, data, offset, fh):
        raise FuseOSError(errno.EACCES)



class FileSystem(LoggingMixIn, Operations):

    def __init__(self, root, mountpoint):
        self.root = realpath(root)
        self.mountpoint = realpath(mountpoint)
        self.rwlock = Lock()

    def onresource(name):
        def func(self, path, *args, **kwargs):
            resource = self.resource(path)
            method = getattr(resource, name)
            if not method:
                raise FuseOSError(errno.EACCES)
            try:
                return method(*args, **kwargs)
            except Exception:
                raise
        return func

    def __call__(self, op, path, *args):
        print op, path, args
        return super(FileSystem, self).__call__(op, path, *args)

    def resource(self, path):
        segments = path.lstrip('/').split('/')
        node = DynamicAwareFile(self, self.root)
        for segment in segments:
            if not segment:
                continue
            node = node.child(segment)
        if not node:
            return DynamicAwareFile(self, os.path.join(self.root, path.lstrip('/')))
        return node

    access = onresource('access')
    chmod = onresource('chmod')
    chown = onresource('chown')
    create = onresource('create')
    flush = onresource('flush')
    fsync = onresource('fsync')
    getattr = onresource('getattr')
    getxattr = onresource('getxattr')
    link = onresource('link')
    listxattr = onresource('listxattr')
    mkdir = onresource('mkdir')
    mknod = onresource('mknod')
    open = onresource('open')
    read = onresource('read')
    readdir = onresource('readdir')
    readlink = onresource('readlink')
    release = onresource('release')
    rename = onresource('rename')
    rmdir = onresource('rmdir')
    statfs = onresource('statfs')
    symlink = onresource('symlink')
    truncate = onresource('truncate')
    unlink = onresource('unlink')
    utimens = onresource('utimens')
    write = onresource('write')



def run():
    basedir = sys.argv[1]
    mountpoint = sys.argv[2]
    fs = FileSystem(basedir, mountpoint)
    if not os.path.exists(mountpoint):
        os.makedirs(mountpoint)
    FUSE(fs, mountpoint, direct_io=True, foreground=True)


if __name__ == '__main__':
    run()
    

