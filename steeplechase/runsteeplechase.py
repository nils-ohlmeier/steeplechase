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
                        help="second remote host to run tests on")
        self.add_option("--remote-webserver",
                        action="store", type="string", dest="remote_webserver",
                        help="ip address to use for webserver")

        self.set_usage(usage)

class RunThread(threading.Thread):
    def __init__(self, args=(), **kwargs):
        threading.Thread.__init__(self, args=args, **kwargs)
        self.args = args

    def run(self):
        dm, cmd, env, cond, results = self.args
        try:
            output = dm.shellCheckOutput(cmd, env=env)
        finally:
            #TODO: actual result
            cond.acquire()
            results.append((self, 0))
            cond.notify()
            cond.release()
            del self.args

class HTMLTest(object):
    def __init__(self, test_file, remote_info, options):
        self.test_file = os.path.abspath(test_file)
        self.remote_info = remote_info
        self.options = options
        #XXX: start httpd in main, not here
        self.httpd = MozHttpd(host=moznetwork.get_ip(), port=8888,
                              docroot=os.path.dirname(self.test_file))

    def run(self):
        self.httpd.start(block=False)
        locations = ServerLocations()
        if self.options.remote_webserver:
            httpd_host = self.options.remote_webserver
        else:
            httpd_host = self.httpd.host

        locations.add_host(host=httpd_host,
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

        specialpowers_path = self.options.specialpowers
        with mozfile.TemporaryDirectory() as profile_path:
            # Create and push profile
            print "Writing profile..."
            profile = FirefoxProfile(profile=profile_path,
                                     preferences=prefs,
                                     addons=[specialpowers_path],
                                     locations=locations)
            for info in self.remote_info:
                print "Pushing profile..."
                remote_profile_path = os.path.join(info['test_root'], "profile")
                info['dm'].mkDir(remote_profile_path)
                info['dm'].pushDir(profile_path, remote_profile_path)
                info['remote_profile_path'] = remote_profile_path

            env = {}
            env["MOZ_CRASHREPORTER_NO_REPORT"] = "1"
            env["XPCOM_DEBUG_BREAK"] = "warn"
            env["DISPLAY"] = ":0"

            threads = []
            results = []
            cond = threading.Condition()
            for info in self.remote_info:
                cmd = [info['remote_app_path'], "-no-remote",
                       "-profile", info['remote_profile_path'],
                       'http://%s:%d/%s' % (httpd_host, self.httpd.port, os.path.basename(self.test_file))]
                print "cmd: %s" % (cmd, )
                t = RunThread(args=(info['dm'], cmd, env, cond, results))
                t.start()
                threads.append(t)
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
            self.httpd.stop()
        return True

def main(args):
    parser = Options()
    options, args = parser.parse_args()
    if not args or not options.binary or not options.specialpowers or not options.host1 or not options.host2:
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
    dm1 = DeviceManagerSUT(options.host1)
    dm2 = DeviceManagerSUT(options.host2)
    remote_info = [{'dm': dm1}, {'dm': dm2}]
    # first, push app
    for info in remote_info:
        dm = info['dm']
        test_root = dm.getDeviceRoot() + "/steeplechase"
        if dm.dirExists(test_root):
            dm.removeDir(test_root)
        dm.mkDir(test_root)
        info['test_root'] = test_root
        app_path = options.binary
        remote_app_dir = test_root + "/app"
        dm.mkDir(remote_app_dir)
        dm.pushDir(os.path.dirname(app_path), remote_app_dir)
        info['remote_app_path'] = remote_app_dir + "/" + os.path.basename(app_path)

    result = True
    for arg in args:
        test = None
        if arg.endswith(".html"):
            test = HTMLTest(arg, remote_info, options)
        else:
            #TODO: support C++ tests
            log.error("Unknown test type: %s", arg)
            continue
        result = result and test.run()

    return 0 if result else 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
