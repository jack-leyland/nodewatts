import { createRequire } from "module";
const NWrequire = createRequire(import.meta.url);
var nodeWattsZmq = NWrequire("zeromq");
const nodeWattsV8Profiler = NWrequire('v8-profiler-next');
const nodeWattsFs = NWrequire("fs");
var nodeWattsSaveToDB = require(process.env.PATH_TO_DB_SERVICE).ingestFile;
const nodeWattsTitle = String(process.env.PROFILE_TITLE);
const nodeWattsPort = String(process.env.TEST_SOCKET_PORT);
const nodeWattsPath = String(process.env.NODEWATTS_TMP_PATH);
nodeWattsV8Profiler.setGenerateType(1);