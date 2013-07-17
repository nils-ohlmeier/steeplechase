# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from optparse import OptionParser
from mozprofile import FirefoxProfile, Profile, Preferences
from mozprofile.permissions import ServerLocations
from mozrunner import FirefoxRunner, Runner
from mozhttpd import MozHttpd

import json
import mozfile
import mozlog
import os
import sys

class Options(OptionParser):
    def __init__(self, **kwargs):
        OptionParser.__init__(self, **kwargs)
        usage = """
                Usage instructions for runsteeplechase.py.
                %prog [options] test <test>*
                """
        #app path
        #extension path
        #prefs path

        self.set_usage(usage)

class HTMLTest(object):
    def __init__(self, test_file):
        self.test_file = os.path.abspath(test_file)
        self.httpd = MozHttpd(docroot=os.path.dirname(self.test_file))

    def run(self):
        self.httpd.start(block=False)
        locations = ServerLocations()
        locations.add_host(host=self.httpd.host,
                           port=self.httpd.port,
                           options='primary,privileged')

        #TODO: use Preferences.read when prefs_general.js has been updated
        prefpath = "/build/mozilla-central/testing/profiles/prefs_general.js"
        prefs = {}
        prefs.update(Preferences.read_prefs(prefpath))
        interpolation = { "server": "%s:%d" % self.httpd.httpd.server_address,
                          "OOP": "false"}
        prefs = json.loads(json.dumps(prefs) % interpolation)
        for pref in prefs:
          prefs[pref] = Preferences.cast(prefs[pref])

        app_path = "/build/debug-mozilla-central/dist/bin/firefox"
        specialpowers_path = "/build/debug-mozilla-central/dist/xpi-stage/specialpowers"
        with mozfile.TemporaryDirectory() as profile_path:
            profile = FirefoxProfile(profile=profile_path,
                                     preferences=prefs,
                                     addons=[specialpowers_path],
                                     locations=locations)

            env = os.environ.copy()
            env["MOZ_CRASHREPORTER_NO_REPORT"] = "1"
            env["XPCOM_DEBUG_BREAK"] = "warn"

            cmdargs = [self.httpd.get_url("/" + os.path.basename(self.test_file))]
            print "cmdargs: %s" % (cmdargs, )
            runner = FirefoxRunner(profile=profile,
                                   binary=app_path,
                                   cmdargs=cmdargs,
                                   env=env)
            runner.start()
            #debug_args=debug_args, interactive=interactive
            runner.wait()
            self.httpd.stop()
        return True

def main(args):
    parser = Options()
    options, args = parser.parse_args()
    if not args:
        parser.print_usage()
        return 2

    log = mozlog.getLogger('steeplechase')
    result = True
    for arg in args:
        test = None
        if arg.endswith(".html"):
            test = HTMLTest(arg)
        else:
            #TODO: support C++ tests
            log.error("Unknown test type: %s", arg)
            continue
        result = result and test.run()

    return 0 if result else 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
