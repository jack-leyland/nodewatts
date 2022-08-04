#!/usr/bin/env node 
const program = require("commander")
const {ingestFile} = require("../main/index")

program
  .version('1.0.0')
  .name('ingest-prof')
  .description('CLI utility to ingest .cpuprofile files into the exiting mongo database')
  .usage('[.cpuprofile filepath]')
  .option('-n,--name [filename]', 'optional custom filename, will otherwise default to current UTC timestamp')
  .parse(process.argv)

  const main = async () => {
    try {
        //is this right?
        const path = program.args[0]
        ingestFile(path, program._optionValues.name)
        
    } catch (err) {
        console.log(err);
    }
  }

  main();