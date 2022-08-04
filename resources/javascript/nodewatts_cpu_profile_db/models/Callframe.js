const mongoose = require("mongoose");

const CallframeSchema = new mongoose.Schema({
    functionName: {type: String, required: false},
    scriptId: {type: Number, required: true},
    bailoutReason: {type: String, required: false, default: ""},
    url: {type: String, required: false},
    lineNumber: {type: Number, required: true},
    columnNumber: {type: Number, required: true}
})

module.exports = CallframeSchema;