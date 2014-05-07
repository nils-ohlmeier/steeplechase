Steeplechase is a test harness for running [WebRTC] tests on pairs of test machines. Its primary purpose is to test NAT traversal by running tests on a carefully crafted test network.

Steeplechase is designed to run with at least three test machines: a controller machine which runs the Python test harness as well as two client machines that run the [Negatus] agent to accept commands from the controller. For a production testing setup you may also want separate machines for running the signalling server and STUN/TURN servers. The controller runs a browser on each of the clients to execute the HTML+JavaScript test harness, loaded from a local HTTP server on the controller. The clients use a simple [signalling server] to exchange signalling information in order to establish WebRTC connections. The controller collects and presents the results of the tests.

Installation and Configuration
==============================
You will need a minimum of two machines to run Steeplechase. In a production environment you will want at least three.

Run `python setup.py install` on the controller to install Python prerequisites.

Install [Negatus] on each of the client machines and run it. (For testing purposes you may use the controller machine as one of the clients.) Note: Negatus is only known to work on Linux currently.

Install the [signalling server] on a machine. This can be on the controller machine, the only requirement is that the client machines be able to access this server via HTTP.

(Optional) Install and configure STUN/TURN servers. You may want to do this to improve reliability of the tests.

Running Steeplechase tests
==========================

Running Steeplechase tests requires a Firefox binary as well as some supporting test files that are a product of the Firefox build. Your best bet is to download a [Firefox nightly build], and get the supporting files from the test package that is present next to the build package (as .tests.zip).

Download and unpack the Firefox build and the test package on the controller machine. Assuming you've unpacked the Firefox build to /tmp/firefox and the tests to /tmp/test-package, to run tests, execute:

    python steeplechase/runsteeplechase.py --binary=/tmp/firefox/firefox --specialpowers-path=/tmp/test-package/steeplechase/specialpowers --prefs-file=/tmp/test-package/steeplechase/prefs_general.js --host1=<client 1 address> --host2=<client 2 address> --signalling-server=http://<signalling server address:port>/ /tmp/test-package/steeplechase/tests/steeplechase.ini

`--host1` and `--host2` in this commandline should specify the IP address (and port if necessary) of the client machines running Negatus. `--signalling-server` should specify the full URL of the signalling server wherever it is running. The final argument is the test manifest containing the list of tests to use. You can use the manifest from the Firefox test package, or run the tests contained in the `sample_tests` directory in this repository.

[WebRTC]: http://www.webrtc.org/
[Negatus]: https://github.com/mozilla/Negatus
[signalling server]: https://github.com/luser/simplesignalling
[Firefox nightly build]: http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-mozilla-central/