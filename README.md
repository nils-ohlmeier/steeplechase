Steeplechase is a test harness for running [WebRTC] tests on pairs of test machines. Its primary purpose is to test NAT traversal by running tests on a carefully crafted test network.

Steeplechase is designed to run with at least three test machines: a _controller_ machine which runs the Python test harness as well as two _client_ machines that run the [Negatus] agent to accept commands from the controller. For a production testing setup you may also want separate machines for running the signalling server and STUN/TURN servers. The controller runs a browser on each of the clients to execute the HTML+JavaScript test harness, loaded from a local HTTP server on the controller. The clients use a simple [signalling server] to exchange signalling information in order to establish WebRTC connections. The controller collects and presents the results of the tests.

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

    python steeplechase/runsteeplechase.py --binary=/tmp/firefox/firefox --specialpowers-path=/tmp/test-package/steeplechase/specialpowers --prefs-file=/tmp/test-package/steeplechase/prefs_general.js --host1=<client 1 address> --host2=<client 2 address> --signalling-server=http://<signalling server address:port>/ --html-manifest=/tmp/test-package/steeplechase/tests/steeplechase.ini

`--host1` and `--host2` in this commandline should specify the IP address (and port if necessary) of the client machines running Negatus. `--signalling-server` should specify the full URL of the signalling server wherever it is running. The `--html-manifest` argument specifies the test manifest containing the list of tests to use. You can use the manifest from the Firefox test package, or run the tests contained in the `sample_tests` directory in this repository.

When re-running tests with the same binary you can use the `--noSetup` option to speed up the process, it will skip copying the Firefox binaries to each client. (You must have already done this once in order for this to work.)

If you would like to use a different Firefox binary for each client machine you may pass `--binary2` to specify a second binary. The argument to `--binary` will be run on host 1, and the argument to `--binary2` will be run on host 2.

Writing Steeplechase tests
==========================

The biggest thing to keep in mind when writing Steeplechase tests is that they are executed in two separate browser instances on two separate machines at the same time. The Steeplechase harness will pass a boolean flag to both tests indicating which test is the _initiator_. The initiator should start whatever actions the test requires. For example, it might create a WebRTC offer to send to the other test instance.

Tests must include the `test.js` script like so:

    <script src="/test.js"></script>

Tests must also include a `run_test` function which will be called to start the test. The function takes one parameter: `is_initiator`, which is either `true` or `false` as described in the paragraph above.

    function run_test(is_initiator) {
      if (is_initiator) {
        // start test...
      } else {
        // wait for message from initiator...
      }
    }

The test.js script provides a very simple API for writing tests:
* `ok(condition, message)`: Generate a test failure if `condition` evaluates to `false`.
* `is(a, b, message)`: Generate a test failure if `a != b`.
* `isnot(a, b, message)`: Generate a test failure if `a == b`.
* `finish()`: End the test
* `send_message(data)`: Send `data` as a JSON string to the other test instance.
* `wait_for_message()`: Returns a promise which, when resolved, provides the next message received from the other test instance.

The [sample.html] file in the [sample_tests] directory in this repository shows a small example test.

Mochitest integration
=====================

The majority of the tests that are run on Steeplechase in practice are actually [Mochitests]. As of this writing some of the [Firefox WebRTC Mochitests] have been modified to run in Steeplechase, but not all. The [WebRTC Mochitest sub-harness] contains Steeplechase support, but individual tests may need changes to work properly. Some things to note when writing Mochitests to run in Steeplechase:
* The callback passed to the `runTest` function will be called with an `options` parameter, which will have `is_local` and `is_remote` properties reflecting whether this test instance is the initiator or not.
* If writing a test that uses `PeerConnectionTest` most of the hard work is already done, you just need to follow a few simple rules:
1. Start the names of the commands in the command chain with _PC_LOCAL_ or _PC_REMOTE_ if they should only execute on one side of the connection. The appropriate commands will be filtered out automatically.
2. If you have state that needs to be passed from one side to the other you must use `send_message` to send it and `wait_message` to receive it if you're running under Steeplechase. You can check whether the other side of the connection is running in the same page (see [templates.js] for an example) and send the data if not.

[WebRTC]: http://www.webrtc.org/
[Negatus]: https://github.com/mozilla/Negatus
[signalling server]: https://github.com/luser/simplesignalling
[Firefox nightly build]: http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-mozilla-central/
[sample.html]: sample_tests/sample.html
[sample_tests]: sample_tests/
[Mochitests]: https://developer.mozilla.org/en-US/docs/Mochitest
[Firefox WebRTC Mochitests]: http://mxr.mozilla.org/mozilla-central/source/dom/media/tests/mochitest/
[WebRTC Mochitest sub-harness]: http://mxr.mozilla.org/mozilla-central/source/dom/media/tests/mochitest/head.js
[templates.js]: http://mxr.mozilla.org/mozilla-central/source/dom/media/tests/mochitest/templates.js
