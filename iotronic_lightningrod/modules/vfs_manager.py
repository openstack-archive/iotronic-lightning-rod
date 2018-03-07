# Copyright 2017 MDSLAB - University of Messina
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from __future__ import with_statement

__author__ = "Nicola Peditto <npeditto@unime.it"

import errno
import os
from subprocess import call
import threading

# Iotronic imports
from iotronic_lightningrod.modules import Module

# Fuse imports
import ctypes
import ctypes.util
from fuse import FUSE
from fuse import FuseOSError
from fuse import Operations

# Logging conf
from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class VfsManager(Module.Module):

    def __init__(self, board, session):
        super(VfsManager, self).__init__("VFS", board)

        self.session = session
        self.board = board

        """
        #print session
        from iotronic_lightningrod.modules import vfs_library
        fuse=vfs_library.FuseLib("/opt/AAA")
        print fuse.getattr("/aaa.txt")
        """

        libcPath = ctypes.util.find_library("c")
        self.libc = ctypes.CDLL(libcPath)

    def finalize(self):
        pass

    def restore(self):
        pass

    def mountLocal(self, mountSource, mountPoint):

        try:

            mounter = MounterLocal(mountSource, mountPoint)
            mounter.start()

            result = "Mounted " + mountSource + " in " + mountPoint

        except Exception as msg:
            result = "Mounting error:", msg

        print(result)
        return result

    def unmountLocal(self, mountPoint):

        print("Unmounting...")

        try:

            # errorCode = self.libc.umount(mountPoint, None)
            errorCode = call(["umount", "-l", mountPoint])

            result = "Unmount " + mountPoint + " result: " + str(errorCode)

        except Exception as msg:
            result = "Unmounting error:", msg

        print(result)
        return result

    def mountRemote(self,
                    mountSource,
                    mountPoint,
                    boardRemote=None,
                    agentRemote=None
                    ):

        try:

            mounter = MounterRemote(
                mountSource,
                mountPoint,
                self.board,
                self.session,
                boardRemote,
                agentRemote
            )

            mounter.start()

            result = "Mounted " + mountSource + " in " + mountPoint

        except Exception as msg:
            result = "Mounting error:", msg

        print(result)
        return result

    def unmountRemote(self, mountPoint):

        print("Unmounting...")

        try:

            # errorCode = self.libc.umount(mountPoint, None)
            errorCode = call(["umount", "-l", mountPoint])

            result = "Unmount " + mountPoint + " result: " + str(errorCode)

        except Exception as msg:
            result = "Unmounting error:", msg

        print(result)
        return result


class MounterLocal(threading.Thread):

    def __init__(self, mountSource, mountPoint):
        threading.Thread.__init__(self)
        # self.setDaemon(1)
        self.setName("VFS-Mounter")  # Set thread name

        self.mountSource = mountSource
        self.mountPoint = mountPoint

    def run(self):
        """Mount FUSE FS

        """
        try:

            FUSE(
                FuseManager(self.mountSource),
                self.mountPoint,
                nothreads=False,
                foreground=True
            )

        except Exception as msg:
            LOG.error("Mounting FUSE error: " + str(msg))


class MounterRemote(threading.Thread):

    def __init__(
            self,
            mountSource,
            mountPoint,
            board,
            session,
            boardRemote,
            agentRemote
    ):

        threading.Thread.__init__(self)
        # self.setDaemon(1)
        self.setName("VFS-Mounter")  # Set thread name

        self.mountSource = mountSource
        self.mountPoint = mountPoint
        self.session = session
        self.board = board
        self.boardRemote = boardRemote
        self.agentRemote = agentRemote

    def run(self):
        """Mount FUSE FS.

        """
        try:

            FUSE(
                FuseRemoteManager(
                    self.mountSource,
                    self.board.agent,
                    self.session,
                    self.boardRemote,
                    self.agentRemote
                ),
                self.mountPoint,
                nothreads=False,
                foreground=True
            )

        except Exception as msg:
            LOG.error("Mounting FUSE error: " + str(msg))


async def makeCall(msg=None, agent=None, session=None):
    rpc_addr = str(agent) + '.stack4things.echo'
    LOG.debug("VFS - I'm calling " + rpc_addr)
    try:
        res = await session.call(rpc_addr, msg)
        LOG.info("NOTIFICATION " + str(res))
    except Exception as e:
        LOG.warning("NOTIFICATION error: {0}".format(e))


class FuseRemoteManager(Operations):

    def __init__(self, mountSource, agent, session, boardRemote, agentRemote):

        self.mountSource = mountSource
        self.session = session
        self.agent = agent
        self.boardRemote = boardRemote
        self.agentRemote = agentRemote

        # makeCall("UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU",
        # self.agent, self.session)  # TEMPORARY

    def join_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.mountSource, partial)
        print(path)
        return path

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        full_path = self.join_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        full_path = self.join_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        full_path = self.join_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        full_path = self.join_path(path)
        st = os.lstat(full_path)
        attr = dict((key, getattr(st, key))
                    for key in (
                        'st_atime',
                        'st_ctime',
                        'st_gid',
                        'st_mode',
                        'st_mtime',
                        'st_nlink',
                        'st_size',
                        'st_uid'
                        )
                    )

        return attr

    def readdir(self, path, fh):
        full_path = self.join_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r

    def readlink(self, path):
        pathname = os.readlink(self.join_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.mountSource)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        return os.mknod(self.join_path(path), mode, dev)

    def rmdir(self, path):
        full_path = self.join_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        return os.mkdir(self.join_path(path), mode)

    def statfs(self, path):
        full_path = self.join_path(path)
        stv = os.statvfs(full_path)
        stat = dict((key, getattr(stv, key))
                    for key in ('f_bavail',
                                'f_bfree',
                                'f_blocks',
                                'f_bsize',
                                'f_favail',
                                'f_ffree',
                                'f_files',
                                'f_flag',
                                'f_frsize',
                                'f_namemax'
                                )
                    )
        return stat

    def unlink(self, path):
        return os.unlink(self.join_path(path))

    def symlink(self, name, target):
        return os.symlink(name, self.join_path(target))

    def rename(self, old, new):
        return os.rename(self.join_path(old), self.join_path(new))

    def link(self, target, name):
        return os.link(self.join_path(target), self.join_path(name))

    def utimens(self, path, times=None):
        return os.utime(self.join_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        full_path = self.join_path(path)
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        full_path = self.join_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        full_path = self.join_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)


class FuseManager(Operations):

    def __init__(self, mountSource):
        self.mountSource = mountSource

    def join_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.mountSource, partial)
        print(path)
        return path

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        full_path = self.join_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        full_path = self.join_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        full_path = self.join_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        full_path = self.join_path(path)
        st = os.lstat(full_path)
        attr = dict((key, getattr(st, key))
                    for key in (
                        'st_atime',
                        'st_ctime',
                        'st_gid',
                        'st_mode',
                        'st_mtime',
                        'st_nlink',
                        'st_size',
                        'st_uid'
                        )
                    )

        return attr

    def readdir(self, path, fh):
        full_path = self.join_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r

    def readlink(self, path):
        pathname = os.readlink(self.join_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.mountSource)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        return os.mknod(self.join_path(path), mode, dev)

    def rmdir(self, path):
        full_path = self.join_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        return os.mkdir(self.join_path(path), mode)

    def statfs(self, path):
        full_path = self.join_path(path)
        stv = os.statvfs(full_path)
        stat = dict((key, getattr(stv, key))
                    for key in ('f_bavail',
                                'f_bfree',
                                'f_blocks',
                                'f_bsize',
                                'f_favail',
                                'f_ffree',
                                'f_files',
                                'f_flag',
                                'f_frsize',
                                'f_namemax'
                                )
                    )
        return stat

    def unlink(self, path):
        return os.unlink(self.join_path(path))

    def symlink(self, name, target):
        return os.symlink(name, self.join_path(target))

    def rename(self, old, new):
        return os.rename(self.join_path(old), self.join_path(new))

    def link(self, target, name):
        return os.link(self.join_path(target), self.join_path(name))

    def utimens(self, path, times=None):
        return os.utime(self.join_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        full_path = self.join_path(path)
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        full_path = self.join_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        full_path = self.join_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)
