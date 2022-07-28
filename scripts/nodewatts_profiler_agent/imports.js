//Profiling deps
var nodeWattsZmq = require("nw-zeromq");
const nodeWattsV8Profiler = require('nw-prof');
const nodeWattsFs = require("fs");
var nodeWattsSaveToDB = require(process.env.PATH_TO_DB_SERVICE).ingestFile;
const nodeWattsTitle = String(process.env.PROFILE_TITLE);
const nodeWattsPort = String(process.env.TEST_SOCKET_PORT);
const nodeWattsPath = String(process.env.NODEWATTS_TMP_PATH);
nodeWattsV8Profiler.setGenerateType(1);
