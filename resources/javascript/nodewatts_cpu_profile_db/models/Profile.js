const mongoose = require("mongoose"),
        NodeSchema = require("./Node");

const ProfileSchema = new mongoose.Schema({
    userProvidedName: {type: String, required: true},
    typeId: {type: String, required: true},
    uid: {type: String, required: true},
    title: {type: String, required: true},
    startTime: {type: Number, required: true},
    endTime: {type: Number, required: true},
    nodes: {type: [NodeSchema], required: false},
    samples: {type: [Number], required: true},
    timeDeltas: {type: [Number], required: true}
})

module.exports = ProfileSchema;