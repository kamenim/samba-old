# Unix SMB/CIFS implementation.
#
# Copyright (C) Kamen Mazdrashki <kamenim@samba.org> 2014
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
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

"""Samba DSDB tests."""

import os
import sys

sys.path.insert(0, "bin/python")

from samba import param
from ldb import SCOPE_BASE
import samba.tests

class SamdbConnectBaseTest(samba.tests.TestCase):
    """Base class for tests that are to connect to samdb

    This class will create samdb connection during setUp
    based on environment variables for target DC_SERVER,
    DC_USERNAME and DC_PASSWORD.
    Also, the class provides some convenient helpers during
    testing like search_guid(), search_dn() etc.
    """

    def setUp(self):
        super(SamdbConnectBaseTest, self).setUp()
        # load LoadParm
        lp = self.get_loadparm()
        self.samdb = samba.tests.connect_samdb_env("DC_SERVER", "DC_USERNAME",
                                                   "DC_PASSWORD", lp=lp)

    @staticmethod
    def get_loadparm():
        lp = param.LoadParm()
        if os.getenv("SMB_CONF_PATH") is not None:
            lp.load(os.getenv("SMB_CONF_PATH"))
        else:
            lp.load_default()
        return lp

    def GUID_string(self, guid):
        return self.samdb.schema_format_value("objectGUID", guid)

    def search_guid(self, guid, controls=None):
        """Returns the object with given GUID
        using ["show_recycled:1"] controls by default"""
        if not controls: controls = ["show_recycled:1"]
        res = self.samdb.search(base="<GUID=%s>" % self.GUID_string(guid),
                                scope=SCOPE_BASE, controls=controls)
        self.assertEquals(len(res), 1)
        return res[0]

    def search_dn(self, dn, controls=None):
        """Returns the object with given dn
        using ["show_recycled:1"] controls by default"""
        if not controls: controls = ["show_recycled:1"]
        res = self.samdb.search(expression="(objectClass=*)",
                                base=dn,
                                scope=SCOPE_BASE,
                                controls=controls)
        self.assertEquals(len(res), 1)
        return res[0]
