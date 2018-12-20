#!/usr/bin/env python

# Copyright 2017 Reuben Stump, Alex Mittell

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing
# permissions and limitations under the License.
'''
ServiceNow Inventory Script
=======================
Retrieve information about machines from a ServiceNow CMDB
This script will attempt to read configuration from an INI file with the same
base filename if present, or `now.ini` if not.  It is possible to create
symlinks to the inventory script to support multiple configurations, e.g.:
* `now.py` (this script)
* `now.ini` (default configuration, will be read by `now.py`)
The path to an INI file may also be specified via the `NOW_INI` environment
variable, in which case the filename matching rules above will not apply.
Host and authentication parameters may be specified via the `SN_INSTANCE`,
`SN_USERNAME` and `SN_PASSWORD` environment variables; these options will
take precedence over options present in the INI file.  An INI file is not
required if these options are specified using environment variables.

For additional usage details see: https://github.com/ServiceNowITOM/ansible-sn-inventory
'''

import os
import sys
import requests
import base64
import json
import re
#import configparser
import time
from six.moves import configparser
from cookielib import LWPCookieJar


class NowInventory(object):
    def __init__(
            self,
            hostname,
            username,
            password,
            fields=None,
            groups=None,
            selection=None,
            proxy=None):
        self.hostname = hostname

        # requests session
        self.session = requests.Session()

        self.auth = requests.auth.HTTPBasicAuth(username, password)
        # request headers
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # request cookies
        self.cookies = LWPCookieJar(os.getenv("HOME") + "/.sn_api_session")
        try:
            self.cookies.load(ignore_discard=True)
        except IOError:
            pass
        self.session.cookies = self.cookies

        if fields is None:
            fields = []

        if groups is None:
            groups = []

        if selection is None:
            selection = []

        if proxy is None:
            proxy = []

        # extra fields (table columns)
        self.fields = fields

        # extra groups (table columns)
        self.groups = groups

        # selection order
        self.selection = selection

        # proxy settings
        self.proxy = proxy

        # initialize inventory
        self.inventory = {'_meta': {'hostvars': {}}}

        return

    def _put_cache(self, name, value):
        cache_dir = os.environ.get('SN_CACHE_DIR')
        if not cache_dir and config.has_option('defaults', 'cache_dir'):
            cache_dir = os.path.expanduser(config.get('defaults', 'cache_dir'))
        if cache_dir:
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            cache_file = os.path.join(cache_dir, name)
            with open(cache_file, 'w') as cache:
                json.dump(value, cache)

    def _get_cache(self, name, default=None):
        cache_dir = os.environ.get('SN_CACHE_DIR')
        if not cache_dir and config.has_option('defaults', 'cache_dir'):
            cache_dir = config.get('defaults', 'cache_dir')
        if cache_dir:
            cache_file = os.path.join(cache_dir, name)
            if os.path.exists(cache_file):
                cache_max_age = os.environ.get('SN_CACHE_MAX_AGE')
                if not cache_max_age:
                    if config.has_option('defaults', 'cache_max_age'):
                        cache_max_age = config.getint('defaults',
                                                      'cache_max_age')
                    else:
                        cache_max_age = 0
                cache_stat = os.stat(cache_file)
                if (cache_stat.st_mtime + int(cache_max_age)) >= time.time():
                    with open(cache_file) as cache:
                        return json.load(cache)
        return default

    def __del__(self):
        self.cookies.save(ignore_discard=True)

    def _invoke(self, verb, path, data):

        cache_name = '__snow_inventory__'
        inventory = self._get_cache(cache_name, None)
        if inventory is not None:
            return inventory

        # build url
        url = "https://%s/%s" % (self.hostname, path)

        # perform REST operation
        response = self.session.get(
            url, auth=self.auth, headers=self.headers, proxies={
                'http': self.proxy, 'https': self.proxy})
        if response.status_code != 200:
            print >> sys.stderr, "http error (%s): %s" % (response.status_code,
                                                          response.text)

        self._put_cache(cache_name, response.json())
        return response.json()

    def add_group(self, target, group):
        ''' Transform group names:
                        1. lower()
                        2. non-alphanumerical characters to '_'
        '''

        # Ignore empty group names
        if group == '' or group is None:
            return

        group = group.lower()
        group = re.sub(r' ', '_', group)

        self.inventory.setdefault(group, {'hosts': []})
        self.inventory[group]['hosts'].append(target)
        return

    def add_var(self, target, key, val):
        if target not in self.inventory['_meta']['hostvars']:
            self.inventory['_meta']['hostvars'][target] = {}

        self.inventory['_meta']['hostvars'][target]["sn_" + key] = val
        return

    def generate(self):

        # table = 'cmdb_ci_server'
        table = 'cmdb_ci_linux_server'
        base_fields = [
            u'host_name', u'ip_address'
        ]
        base_groups = [u'sys_class_name',]
        options = "?sysparm_exclude_reference_link=true&sysparm_display_value=true"#&sysparm_query=u_server_mgmt_type!=Campus Routers^operational_status=5^ORoperational_status=7^ORoperational_status=11"

        columns = list(
            set(base_fields + base_groups + self.fields + self.groups))
        path = '/api/now/table/' + table #+ options + "&sysparm_fields=" + ','.join(columns)

        # Default, mandatory group 'sys_class_name'
        groups = list(set(base_groups + self.groups))

        content = self._invoke('GET', path, None)
        
        for record in content['result']:
            ''' Ansible host target selection order:
                        1. host_name
                        2. ip_address

                        '''
            target = None

            selection = self.selection
            
            if not selection:
                selection = ['ip_address','host_name']
            for k in selection:
                if record[k] != '':
                    target = record[k]

            # Skip if no target available
            if target is None:
                continue

            # hostvars
            for k in record.keys():
                self.add_var(target, k, record[k])

            # groups
            for k in groups:
                self.add_group(target, record[k])
        
        return

    def json(self):
        return json.dumps(self.inventory)


def main(args):

    instance = os.environ['SN_INSTANCE']
    username = os.environ['SN_USERNAME']
    password = os.environ['SN_PASSWORD']
    global config
    config = configparser.SafeConfigParser()

    if os.environ.get('NOW_INI', ''):
        config_files = [os.environ['NOW_INI']]
    else:
        config_files = [
            os.path.abspath(sys.argv[0]).rstrip('.py') + '.ini', 'now.ini'
        ]

    for config_file in config_files:
        if os.path.exists(config_file):
            config.read(config_file)
            break

    # Read authentication information from environment variables (if set),
    # otherwise from INI file.
    instance = os.environ.get('SN_INSTANCE')
    if not instance and config.has_option('auth', 'instance'):
        instance = config.get('auth', 'instance')

    username = os.environ.get('SN_USERNAME')
    if not username and config.has_option('auth', 'user'):
        username = config.get('auth', 'user')

    password = os.environ.get('SN_PASSWORD')
    if not password and config.has_option('auth', 'password'):
        password = config.get('auth', 'password')

    # SN_SEL_ORDER
    selection = os.environ.get("SN_SEL_ORDER", [])

    if not selection and config.has_option('config', 'selection_order'):
        selection = config.get('config', 'selection_order')
        selection = selection.encode('utf-8').replace('\n', '\n\t')
    if isinstance(selection, str):
        selection = selection.split(',')

    # SN_GROUPS
    groups = os.environ.get("SN_GROUPS", [])

    if not groups and config.has_option('config', 'groups'):
        groups = config.get('config', 'groups')
        groups = groups.encode('utf-8').replace('\n', '\n\t')
    if isinstance(groups, str):
        groups = groups.split(',')

    # SN_FIELDS
    fields = os.environ.get("SN_FIELDS", [])

    if not fields and config.has_option('config', 'fields'):
        fields = config.get('config', 'fields')
        fields = fields.encode('utf-8').replace('\n', '\n\t')
    if isinstance(fields, str):
        fields = fields.split(',')

    # SN_PROXY
    proxy = os.environ.get('SN_PROXY')
    if not proxy and config.has_option('config', 'proxy'):
        proxy = config.get('config', 'proxy')

    inventory = NowInventory(
        hostname=instance,
        username=username,
        password=password,
        fields=fields,
        groups=groups,
        selection=selection,
        proxy=proxy)
    inventory.generate()
    print(inventory.json())


if __name__ == "__main__":
    main(sys.argv)




# line 193 decides what groups are exluded ysparm_query=u_server_mgmt_type!=Campus Hosted^operational_status=5^ORoperational_status=7^ORoperational_status=11
# ^ is how you would say "and" ie.. Campus Routers^operational_status=5
# != this saying exclude these SN_GROUPS
# line 188 is where you specify the table ie..  table = 'cmdb_ci_linux_server'
#


    
