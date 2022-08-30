# NodeWatts
NodeWatts is a novel tool for NodeJS developers allowing them to generate power profiles of their NodeJS web servers at function-level granularity, enabling the identification of potential energy hotspots in their code. It leverages the power modelling functionality of [SmartWatts](https://github.com/powerapi-ng/smartwatts-formula), which in turn is built on top of [PowerAPI](https://github.com/powerapi-ng/powerapi).

A user may run a power profile by supplying a path to the root directory of the project, a path to the entry file of the application and a test suite that subjects the server to a workload representative of its full functionality. Once the profile is generated, the results may be viewed using a built-in graphical user interface (GUI) and/or simply exported in raw data form to a MongoDB database.

## Platform limitations
NodeWatts has the following system requirements:

 - Debian-based Linux distribution - preferably Ubuntu 20.04.
 - An Intel processor of the Sandy Bridge generation onward.
 - Python 3.10
 - Root access to the machine. NodeWatts requires root priviledges in order to collect the hardware performance counter data it needs from the CPU to perform its power modeling. Source code for the component which performs this data collection (included in this repo as binary) can be found [here](https://github.com/jack-leyland/hwpc-sensor/tree/nodewatts).

# Installation
To install NodeWatts, it must be built from the source using ```setuptools``` using the following steps:

 - Clone the repsitory.
 - From the root directory, run ```$ python3.10 setup.py sdist bdist_wheel``` 
 - Navigate to ```dist\``` subdirectory and run ```$ sudo pip install nodewatts-0.1.1-py3-none-any.whl```
 
# Usage
Prior to using NodeWatts, several setup steps are required after installation:
- Ensure that there is a local running instance of MongoDB, listening on its default port (27017) on your machine.
- Ensure that the directory for the web server they would like to profile has all of the npm dependencies it requires installed beforehand.
- Ensure that there is an npm or yarn command available that will execute a suite of API tests on the server in question. NodeWatts is not currently compatible with test suites which instatiate the server as a part of the testing pipeline. The tests should consist of a series of API calls to a localhost port where an already existing server instance is running.

Once the setup is complete, create a NodeWatts configuration JSON file in the following format: 
	

    {
    	  "rootDirectoryPath": "/home/jack/projectroot/",
    	  "entryFile": "app.js",
    	  "user": "jack",
    	  "testRuns": 10,
    	  "nvm-mode": true,
    	  "nvm-node-version": "16.15.1",
    	  "visualize": true,
    	  "reportName": "amazing-nodewatts-profile",
    	  "cpu-tdp": 84,
    	  "es6-mode": true,
    	  "commands": {
    	    "serverStart": "npm start",
    	    "runTests": "node test.js"
    	  },
    	  "database": {
    	    "exportRawData": true,
    	    "exportUri": "mongodb://remote.mongodb.uri",
    	    "exportDbName": "exported-nodewatts-raw-data"
    	  },
    	  "dev-serverWait": 5,
    	  "dev-subprocessShell": "/bin/zsh",
    	  "dev-testRunnerTimeout": 20,
    	  "dev-enableSmartWattsLogs": false,
    	  "dev-nvmPathOverride": "/home/jack/.nvm/v16.15.1/bin/node"
    	} 

Some key configuration options are: 
- **es6-mode**:  the setting which NodeWatts will fall back to regarding whether to use ES Module syntax imports in the injected code if it fails to infer what the project is using from the package.json. Use "true" if you are using ES Modules and false for CommonJS
 - **cpu-tdp**: is the thermal design power of the user's CPU, which is needed by SmartWatts for its estimates.
 - **visualize**:  determines whether NodeWatts should launch the GUI when it completes its profiling. A user seeking to perform a automated series of profiles with NodeWatts should disable this as the NodeWatts process will not exit by itself while running the visualization server.
  - **commands**:  the shell commands, executed in the project directory, needed to start the server and run the tests.
 - **user**:  is the operating system username you would like to use for executing the commands. It should be a user which has permissions for the project directory.
 - **testRuns**: determines the number of times to run the test suite when building the profile. Selecting a high number will generate much more data, but can result is very long runtimes for the tool to process the data.
  - **dev-enableSmartWattsLogs**: tells SmartWatts to run in verbose mode, which is disabled by default in NodeWatts. When set to true, SmartWatts will print a significant amount of logs to stdout as it processes the data.

The simplest way to do this is to run the ```sudo nodewatts --config_file <config>.json``` command. The ```config_file``` argument is required in all cases when running the tool. There are also two other CLI options available for usage:

 - **-v**, or **--verbose** runs the tool in debug mode and print additional debugging logs. 
 - **--visualizer** bypasses the profiling process and simply runs the visualization server such that existing profiles can be viewed from the GUI.

Once the profile is generated, if **visualize** is set to true, NodeWatts will launch a browser window where the user may interact with the GUI to view the results.

