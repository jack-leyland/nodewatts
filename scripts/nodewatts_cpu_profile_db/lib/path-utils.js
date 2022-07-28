const fs = require("fs");

const directoryExists = (path) => {
    return fs.existsSync(path);
}

const validExtension = (path) => {
    const splitPath = path.split(".")
    return splitPath[splitPath.length-1] !== ".cpuprofile";
}

module.exports = {
    directoryExists,
    validExtension
}
