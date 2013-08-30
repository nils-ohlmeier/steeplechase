# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from mozdevice import DeviceManagerSUT
from optparse import OptionParser
from mozprofile import FirefoxProfile, Profile, Preferences
from mozprofile.permissions import ServerLocations
from mozhttpd import MozHttpd
from Queue import Queue

import json
import mozfile
import mozlog
import moznetwork
import os
import sys
import threading
import uuid

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
        self.add_option("--host1",
                        action="store", type="string", dest="host1",
                        help="first remote host to run tests on")
        self.add_option("--host2",
                        action="store", type="string", dest="host2",
                        help="first remote host to run tests on")
        self.add_option("--signalling-server",
                        action="store", type="string", dest="signalling_server",
                        help="signalling server URL to use for tests");
        self.add_option("--noSetup",
                        action="store_false", dest="setup",
                        default="True",
                        help="do not copy files to device");

        self.set_usage(usage)

class RunThread(threading.Thread):
    def __init__(self, args=(), **kwargs):
        threading.Thread.__init__(self, args=args, **kwargs)
        self.args = args

    def run(self):
        dm, cmd, env, cond, results = self.args
        try:
            output = dm.shellCheckOutput(cmd, env=env)
            print "%s\n%s\n%s" % ("=" * 20, output, "=" * 20)
        finally:
            #TODO: actual result
            cond.acquire()
            results.append((self, 0))
            cond.notify()
            cond.release()
            del self.args

class HTMLTests(object):
    def __init__(self, httpd, remote_info, options):
        self.remote_info = remote_info
        self.options = options
        self.httpd = httpd

    def run(self):
        locations = ServerLocations()
        locations.add_host(host=self.httpd.host,
                           port=self.httpd.port,
                           options='primary,privileged')

        #TODO: use Preferences.read when prefs_general.js has been updated
        prefpath = self.options.prefs
        prefs = {}
        prefs.update(Preferences.read_prefs(prefpath))
        interpolation = { "server": "%s:%d" % self.httpd.httpd.server_address,
                          "OOP": "false"}
        prefs = json.loads(json.dumps(prefs) % interpolation)
        for pref in prefs:
          prefs[pref] = Preferences.cast(prefs[pref])
        prefs["steeplechase.signalling_server"] = self.options.signalling_server
        prefs["steeplechase.signalling_room"] = str(uuid.uuid4())

        specialpowers_path = self.options.specialpowers
        threads = []
        results = []
        cond = threading.Condition()
        for info in self.remote_info:
            with mozfile.TemporaryDirectory() as profile_path:
                # Create and push profile
                print "Writing profile..."
                prefs["steeplechase.is_initiator"] = info['is_initiator']
                profile = FirefoxProfile(profile=profile_path,
                                         preferences=prefs,
                                         addons=[specialpowers_path],
                                         locations=locations)
                print "Pushing profile..."
                remote_profile_path = os.path.join(info['test_root'], "profile")
                info['dm'].mkDir(remote_profile_path)
                info['dm'].pushDir(profile_path, remote_profile_path)
                info['remote_profile_path'] = remote_profile_path

            env = {}
            env["MOZ_CRASHREPORTER_NO_REPORT"] = "1"
            env["XPCOM_DEBUG_BREAK"] = "warn"
            env["DISPLAY"] = ":0"

            cmd = [info['remote_app_path'], "-no-remote",
                   "-profile", info['remote_profile_path'],
                   self.httpd.get_url("/index.html")]
            print "cmd: %s" % (cmd, )
            t = RunThread(args=(info['dm'], cmd, env, cond, results))
            threads.append(t)

        for t in threads:
            t.start()

        print "Waiting for results..."
        while threads:
            cond.acquire()
            while not results:
                cond.wait()
            res = results.pop(0)
            cond.release()
            print "Got result: %d" % res[1]
            threads.remove(res[0])
        print "Done!"
        return True

def main(args):
    parser = Options()
    options, args = parser.parse_args()
    if not options.binary or not options.specialpowers or not options.host1 or not options.host2 or not options.signalling_server:
        parser.print_usage()
        return 2

    if not os.path.isfile(options.binary):
        parser.error("Binary %s does not exist" % options.binary)
        return 2
    if not os.path.isdir(options.specialpowers):
        parser.error("SpecialPowers directory %s does not exist" % options.specialpowers)
        return 2
    if options.prefs and not os.path.isfile(options.prefs):
        parser.error("Prefs file %s does not exist" % options.prefs)
        return 2

    log = mozlog.getLogger('steeplechase')
    log.setLevel(mozlog.DEBUG)
    dm1 = DeviceManagerSUT(options.host1)
    dm2 = DeviceManagerSUT(options.host2)
    remote_info = [{'dm': dm1, 'is_initiator': True},
                   {'dm': dm2, 'is_initiator': False}]
    # first, push app
    for info in remote_info:
        dm = info['dm']
        test_root = dm.getDeviceRoot() + "/steeplechase"
        if options.setup:
            if dm.dirExists(test_root):
                dm.removeDir(test_root)
            dm.mkDir(test_root)
        info['test_root'] = test_root
        app_path = options.binary
        remote_app_dir = test_root + "/app"
        if options.setup:
            dm.mkDir(remote_app_dir)
            dm.pushDir(os.path.dirname(app_path), remote_app_dir)
        info['remote_app_path'] = remote_app_dir + "/" + os.path.basename(app_path)

    result = True
    #TODO: only start httpd if we have HTML tests
    httpd = MozHttpd(host=moznetwork.get_ip(),
                     docroot=os.path.join(os.path.dirname(__file__), "..", "webharness"))
    httpd.start(block=False)
    #TODO: support test manifests
    test = HTMLTests(httpd, remote_info, options)
    result = test.run()
    httpd.stop()
    return 0 if result else 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
