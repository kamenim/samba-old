#!/usr/bin/env python
#
# Tombstone reanimation tests
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

import sys
import optparse
import unittest

sys.path.insert(0, "bin/python")
import samba
samba.ensure_external_module("testtools", "testtools")
samba.ensure_external_module("subunit", "subunit/python")

import samba.tests
import samba.getopt as options
from ldb import (SCOPE_BASE, FLAG_MOD_DELETE, FLAG_MOD_REPLACE, Dn, Message, MessageElement)


class RestoredObjectAttributesBaseTestCase(samba.tests.TestCase):
    """ verify Samba restores required attributes when
        user restores a Deleted object
    """

    def setUp(self):
        super(RestoredObjectAttributesBaseTestCase, self).setUp()
        # load LoadParm
        lp = options.SambaOptions(optparse.OptionParser()).get_loadparm()
        self.samdb = samba.tests.connect_samdb_env("DC_SERVER", "DC_USERNAME", "DC_PASSWORD", lp=lp)
        self.base_dn = self.samdb.domain_dn()
        self.schema_dn = self.samdb.get_schema_basedn().get_linearized()
        # Get the old "dSHeuristics" if it was set
        self.dsheuristics = self.samdb.get_dsheuristics()
        # Set the "dSHeuristics" to activate the correct "userPassword" behaviour
        self.samdb.set_dsheuristics("000000001")
        # Get the old "minPwdAge"
        self.minPwdAge = self.samdb.get_minPwdAge()
        # Set it temporary to "0"
        self.samdb.set_minPwdAge("0")

    def tearDown(self):
        super(RestoredObjectAttributesBaseTestCase, self).tearDown()
        # Reset the "dSHeuristics" as they were before
        self.samdb.set_dsheuristics(self.dsheuristics)
        # Reset the "minPwdAge" as it was before
        self.samdb.set_minPwdAge(self.minPwdAge)

    def GUID_string(self, guid):
        return self.samdb.schema_format_value("objectGUID", guid)

    def search_guid(self, guid):
        res = self.samdb.search(base="<GUID=%s>" % self.GUID_string(guid),
                                scope=SCOPE_BASE, controls=["show_deleted:1"])
        self.assertEquals(len(res), 1)
        return res[0]

    def search_dn(self, dn):
        res = self.samdb.search(expression="(objectClass=*)",
                                base=dn,
                                scope=SCOPE_BASE,
                                controls=["show_recycled:1"])
        self.assertEquals(len(res), 1)
        return res[0]

    def _class_must_attrs(self, class_name):
        res = self.samdb.search(self.schema_dn,
                                expression="(&(objectClass=classSchema)(lDAPDisplayName=%s))" % class_name,
                                attrs=["subClassOf", "mustContain", "systemMustContain",
                                       "auxiliaryClass", "systemAuxiliaryClass"])
        self.assertEqual(len(res), 1)
        attr_set = set()
        # make the list from immediate class
        if "mustContain" in res[0]:
            attr_set |= set([attr for attr in res[0]["mustContain"]])
        if "systemMustContain" in res[0]:
            attr_set |= set([attr for attr in res[0]["systemMustContain"]])
        # now trace Auxiliary classes
        if "auxiliaryClass" in res[0]:
            for aux_class in res[0]["auxiliaryClass"]:
                attr_set |= self.make_class_all_must_list(aux_class)
        if "systemAuxiliaryClass" in res[0]:
            for aux_class in res[0]["systemAuxiliaryClass"]:
                attr_set |= self.make_class_all_must_list(aux_class)
        return str(res[0]["subClassOf"]), attr_set

    def make_class_all_must_list(self, class_name):
        (parent_class, attr_list) = self._class_must_attrs(class_name)
        sub_set = set()
        if class_name != "top":
            sub_set = self.make_class_all_must_list(parent_class)
        attr_list |= sub_set
        return attr_list

    def test_restore_user(self):
        print "Test restored user attributes"
        username = "restore_user"
        usr_dn = "cn=%s,cn=users,%s" % (username, self.base_dn)
        samba.tests.delete_force(self.samdb, usr_dn)
        self.samdb.add({
            "dn": usr_dn,
            "objectClass": "user",
            "description": "test user description",
            "sAMAccountName": username})
        obj = self.search_dn(usr_dn)
        guid = obj["objectGUID"][0]
        self.samdb.delete(usr_dn)
        obj_del = self.search_guid(guid)
        # restore the user
        msg = Message()
        msg.dn = obj_del.dn
        msg["isDeleted"] = MessageElement([], FLAG_MOD_DELETE, "isDeleted")
        msg["distinguishedName"] = MessageElement([usr_dn], FLAG_MOD_REPLACE, "distinguishedName")
        # add some attributes
        # strip off "sAMAccountType"
        # for attr in ['dSCorePropagationData', 'primaryGroupID', 'badPwdCount', 'logonCount', 'countryCode', 'pwdLastSet', 'codePage', 'lastLogon', 'adminCount', 'accountExpires', 'operatorCount', 'badPasswordTime', 'lastLogoff']:
        #     msg[attr] = "0"
        self.samdb.modify(msg, ["show_deleted:1"])
        # find restored object and check attributes
        obj_restore = self.search_guid(guid)
        keys_restored = obj_restore.keys()
        restored_user_attr = ['dn', 'objectClass', 'cn', 'distinguishedName', 'instanceType', 'whenCreated',
                              'whenChanged', 'uSNCreated', 'uSNChanged', 'name', 'objectGUID', 'userAccountControl',
                              'badPwdCount', 'codePage', 'countryCode', 'badPasswordTime', 'lastLogoff', 'lastLogon',
                              'pwdLastSet', 'primaryGroupID', 'operatorCount', 'objectSid', 'adminCount',
                              'accountExpires', 'logonCount', 'sAMAccountName', 'sAMAccountType', 'lastKnownParent',
                              'objectCategory', 'dSCorePropagationData']
        print set(restored_user_attr) - set(keys_restored)
        pass


if __name__ == '__main__':
    unittest.main()
