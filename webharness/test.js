var log = window.opener.log_result;
var pass_count = 0;
var fail_count = 0;

function ok(condition, message) {
  log(!!condition, message);
}

function is(a, b, message) {
  ok(a == b, message);
}

function isnot(a, b, message) {
  ok(a != b, message);
}

function finish() {
  window.opener.test_finished();
}

var wait_for_message = window.opener.wait_for_message;
var send_message = window.opener.send_message;
