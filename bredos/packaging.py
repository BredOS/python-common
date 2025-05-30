#
# Copyright 2024 BredOS
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pyalpm import Handle as _Handle


class handler:
    def __init__(self, dryrun=False):
        self._hd = _Handle(".", "/var/lib/pacman")
        self._dr = dryrun

    def installed(self):
        ldb = self._hd.get_localdb()
        pklist = []
        for i in ldb.pkgcache:
            pklist.append(i.name)
        return pklist

    def install(self, pks) -> bool:
        if isinstance(pks, str):
            pks = [pks]
        if self._dr:
            print("Stopping since it's a dry-run.")

    def uninstall(self, pks):
        if isinstance(pks, str):
            pks = [pks]
        if self._dr:
            print("Stopping since it's a dry-run.")
