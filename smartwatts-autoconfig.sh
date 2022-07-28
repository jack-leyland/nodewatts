#!/usr/bin/env bash

maxfrequency=$(lscpu -b -p=MAXMHZ | tail -n -1| cut -d , -f 1)
minfrequency=$(lscpu -b -p=MINMHZ | tail -n -1 | cut -d , -f 1)
basefrequency=$(lscpu | grep "Model name" | cut -d @ -f 2 | cut -d G -f 1)
basefrequency=$(expr ${basefrequency}\*1000 | bc | cut -d . -f 1)
maxfrequency=${maxfrequency%?????}
minfrequency=${minfrequency%?????}

echo "
{
  \"verbose\": false,
  \"stream\": false,
  \"input\": {
    \"puller\": {
      \"model\": \"HWPCReport\",
      \"type\": \"mongodb\",
      \"uri\": \"mongodb://127.0.0.1\",
      \"db\": \"nodewatts\",
      \"collection\": \"sensor_raw\"
    }
  },
  \"output\": {
    \"pusher_power\": {
      \"type\": \"mongodb\",
      \"uri\": \"mongodb://127.0.0.1\",
      \"db\": \"nodewatts\",
      \"collection\": \"cpu\"
    }
  },
  \"cpu-frequency-base\": $basefrequency,
  \"cpu-frequency-min\": $minfrequency,
  \"cpu-frequency-max\": $maxfrequency,
  \"cpu-error-threshold\": 2.0,
  \"disable-dram-formula\": true,
  \"sensor-report-sampling-interval\": 1
}
" > ./nodewatts/config/smartwatts_config.json