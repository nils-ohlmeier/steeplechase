# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from mozdevice import DeviceManagerSUT
from optparse import OptionParser
from mozprofile import FirefoxProfile, Profile, Preferences
from mozprofile.permissions import ServerLocations
from mozhttpd import MozHttpd

import json
import mozfile
import mozlog
import moznetwork
import os
import sys

class Options(OptionParser):
    def __init__(self, **kwargs):
        OptionParser.__init__(self, **kwargs)
        usage = """
                Usage instructions for runsteeplechase.py.
                %prog [options] test <test>*
                """
        self.add_option("--binary",
                        action="store", type="string", dest="binary",
                        help="path to application (required)")
        self.add_option("--specialpowers-path",
                        action="store", type="string", dest="specialpowers",
                        help="path to specialpowers extension (required)")
        self.add_option("--prefs-file",
                        action="store", type="string", dest="prefs",
                        help="path to testing preferences file")
        self.add_option("--host",
                        action="store", type="string", dest="host",
                        help="remote host to run tests on")

        self.set_usage(usage)

class HTMLTest(object):
    def __init__(self, dm, test_file, test_root, remote_app_path):
        self.dm = dm
        self.test_root = test_root
        self.test_file = os.path.abspath(test_file)
        self.remote_app_path = remote_app_path
        #XXX: start httpd in main, not here
        self.httpd = MozHttpd(host=moznetwork.get_ip(),
                              docroot=os.path.dirname(self.test_file))

    def run(self):
        self.httpd.start(block=False)
        locations = ServerLocations()
        locations.add_host(host=self.httpd.host,
                           port=self.httpd.port,
                           options='primary,privileged')

        #TODO: use Preferences.read when prefs_general.js has been updated
        prefpath = "/Users/luser" + "/build/mozilla-central/testing/profiles/prefs_general.js"
        prefs = {}
        prefs.update(Preferences.read_prefs(prefpath))
        interpolation = { "server": "%s:%d" % self.httpd.httpd.server_address,
                          "OOP": "false"}
        prefs = json.loads(json.dumps(prefs) % interpolation)
        for pref in prefs:
          prefs[pref] = Preferences.cast(prefs[pref])

        specialpowers_path = "/Users/luser" + "/build/debug-mozilla-central/dist/xpi-stage/specialpowers"
        with mozfile.TemporaryDirectory() as profile_path:
            # Create and push profile
            profile = FirefoxProfile(profile=profile_path,
                                     preferences=prefs,
                                     addons=[specialpowers_path],
                                     locations=locations)
            remote_profile_path = os.path.join(self.test_root, "profile")
            self.dm.mkDir(remote_profile_path)
            self.dm.pushDir(profile_path, remote_profile_path)

            env = {}
            env["MOZ_CRASHREPORTER_NO_REPORT"] = "1"
            env["XPCOM_DEBUG_BREAK"] = "warn"
            env["DISPLAY"] = ":1"

            cmd = [self.remote_app_path, "-no-remote",
                   "-profile", remote_profile_path,
                   self.httpd.get_url("/" + os.path.basename(self.test_file))]
            print "cmd: %s" % (cmd, )
            output = self.dm.shellCheckOutput(cmd,
                                              env = env)
            self.httpd.stop()
        return True

def main(args):
    parser = Options()
    options, args = parser.parse_args()
    if not args or not options.binary or not options.specialpowers or not options.host:
        parser.print_usage()
        return 2

    if not os.path.isfile(options.binary):
        parser.error("Binary %s does not exist" % options.binary)
        return 2
    if not os.path.isdir(options.specialpowers):
        parser.error("SpecialPowers direcotry %s does not exist" % options.specialpowers)
        return 2
    if options.prefs and not os.path.isfile(options.prefs):
        parser.error("Prefs file %s does not exist" % options.prefs)
        return 2

    log = mozlog.getLogger('steeplechase')
    log.setLevel(mozlog.DEBUG)
    dm = DeviceManagerSUT(options.host)
    # first, push app
    test_root = dm.getDeviceRoot() + "/steeplechase"
    if dm.dirExists(test_root):
        dm.removeDir(test_root)
    dm.mkDir(test_root)
    app_path = options.binary
    remote_app_dir = test_root + "/app"
    dm.mkDir(remote_app_dir)
    dm.pushDir(os.path.dirname(app_path), remote_app_dir)
    remote_app_path = remote_app_dir + "/" + os.path.basename(app_path)

    result = True
    for arg in args:
        test = None
        if arg.endswith(".html"):
            test = HTMLTest(dm, arg, test_root, remote_app_path)
        else:
            #TODO: support C++ tests
            log.error("Unknown test type: %s", arg)
            continue
        result = result and test.run()

    return 0 if result else 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
