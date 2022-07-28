const port = process.env.TEST_SOCKET_PORT; // Nodewatts processs will inject these vars
const testCmd = process.env.TESTCMD.split(' ')
const zmqModule = process.env.ZMQ_INSTALLED_PATH
var zmq = require(zmqModule);
const { spawn } = require('child_process');
const events = require('events');
const { exit } = require("process");
const emitter = new events.EventEmitter();

var cmd = testCmd[0]
testCmd.splice(0,1)
var args = testCmd

async function testRunner() {
  const sock = new zmq.Request();
  sock.connect("tcp://127.0.0.1:" + String(port));
  console.log("Runner: Test runner started.")
  await sock.send("start");
  const [res] = await sock.receive();
  if (res.toString() === "start-success") {
    console.log("Runner: Test Runner received successful start msg from server. Running test suite")
    testingProc = spawn(cmd, args);
    // Parrot child output stream up to parent so python script can use for debugging output
    testingProc.stderr.on('data',(data)=>{
      console.error(data.toString('utf8'))
    })
    testingProc.stdout.on('data', (data) => {
      console.log(data.toString('utf8'))
    })
    testingProc.on('close', async function(exitCode) {
      if (parseInt(exitCode) !== 0) {
          console.error("Runner: Testing child process exited with return code " + String(exitCode))
          console.error("Runner: Telling server to discard profile.")
          await sock.send('stop-discard')
          exit(1)
      }
      emitter.emit('tests-success');
    });
    emitter.on('tests-success', async function() {
      console.log("Runner: Tests completed Successfully. Sending stop message to server")
      await sock.send("stop-save")
      const [res] = await sock.receive();
      if (res.toString() === "stop-success") {
        console.log("Runner: Received stop success message from server. Exiting")
        exit(0)
      };
    })
  }
}

testRunner();