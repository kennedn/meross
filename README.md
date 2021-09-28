<!-- TABLE OF CONTENTS -->
# Table of Contents

- [Table of Contents](#table-of-contents)
- [About The Project](#about-the-project)
- [Provisioning](#provisioning)
  - [MQTT server setup](#mqtt-server-setup)
    - [Set up the Certificates](#set-up-the-certificates)
    - [Minimal config](#minimal-config)
    - [Running](#running)
  - [Bulb setup](#bulb-setup)
  - [Usage](#usage)
  - [Acknowledgements](#acknowledgements)

<!-- ABOUT THE PROJECT -->
# About The Project

This is a fork of arandalls [repository](https://github.com/arandall/meross). I purchased a number of Meross Smart bulbs recently and wanted to completely disassosiate them from the meross cloud to use locally with my custom built [REST API](https://github.com/kennedn/roomAPI). I have created a fork to document my own process for doing this and some additional protocol information related to the bulbs.


# Provisioning

If we were to setup the bulbs normally, the flow would look like this:

* Bulb is started in a configuration mode, it advertises its own wifi network
* Phone app connects to the local bulb wifi network and calls the following endpoints:
  * Appliance.Config.Key
  * Appliance.Config.Wifi
* Once the Wifi endpoint has been called the device automatically reboots into its normal mode
* The bulb will attempt to make a connection with the meross cloud, using parameters setup during initialisation
* Depending on whether the initial connection succeeds or not the device will either settle into normal mode or reboot to configuration mode

So in order to fully detach from the meross cloud, we must satisfy the following requirements:
* Call `Appliance.Config.Key` and `Applicance.Config.Wifi` ourselves to configure our own connection parameters
* Host our own MQTT server **during initial setup** so that the bulb makes one successful connection to the MQTT we configure

If we can satisfy these requirements the bulb will remain in normal mode and we can turn off the MQTT server, using direct REST calls to communicate with the bulb going forward.

## MQTT server setup

Mosquitto can be used to host a local MQTT server.

###  Set up the Certificates

The device will try to make a secure connection the the MQTT server, we need to create a local certificate chain to satisfy this. 

_**Make sure that your CA Root uses a different Common Name to your server and the common name for the server is the server IP address**_

##Create the Certificate Authority
```sh
openssl genrsa -des3 -out ca.key 2048
openssl req -new -x509 -days 1826 -key ca.key -out ca.crt
```

##Create the certificate signing request.
It's important when asked for the FQDN in these next step to use the IP or domain name of the machine your MQTT instance is on. 
```sh
openssl genrsa -out server.key 2048
openssl req -new -out server.csr -key server.key
```

##Create the final certificate
```sh
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 360
```

### Minimal config
Using Mosquitto, this minimal config sets up the server allowing the device to connect, ensure the path to the cert files is correct.

```nginx
port 8883

allow_anonymous true
require_certificate false

# replace with your CA Root
cafile ../certs/ca.crt

# replace with your server certificate and key paths
certfile ../certs/server.crt
keyfile ../certs/server.key
```

### Running
```bash
mosquitto -c /path/to/minimal.config
```

## Bulb setup
A simple shell script is provided under tools/mCurl to be able to perform REST calls to the bulb. **You must connect to the bulbs local network before running the setup commands**. We can first configure the Appliance.Config.Key endpoint to point at our newly provisioned MQTT server:

Example payload:
```json
{
  "key": {
    "gateway": {
      "host": "192.168.1.100",
      "port": 8883
    },
    "key": "",
    "userId": ""
  }
}
```

`Host` should be the same ip used to generate the certificates during the Mosquitto setup.

`key` and `userId` can be left deliberatly blank, this simplifies REST calls later on after we enter normal mode

Example Command:
```bash
mCurl 10.10.10.1 SET Appliance.Config.Key '{ "key": { "gateway": { "host": "192.168.1.100", "port": 8883 }, "key": "", "userId": ""}}'
```

We then need to configure the wifi network to connect to. You can ask the bulb to return the available wifi networks by issuing the following:
```bash
> mCurl 10.10.10.1 GET Appliance.Config.WifiList '{}' | jq -r
{
  "header": {
    "messageId": "roomAPI",
    "namespace": "Appliance.Config.WifiList",
    "method": "GETACK",
    "payloadVersion": 1,
    "from": "/appliance/2102255504461490842748e1e94daf56/publish",
    "timestamp": 1632787239,
    "timestampMs": 549,
    "sign": "00001eb7ce289f869256bc95485467de"
  },
  "payload": {
    "wifiList": [
      {
        "ssid": "RElSRUNULUQzNUMyN0Q0",
        "bssid": "9e:ae:d3:5c:a7:d4",
        "channel": 5,
        "signal": 83,
        "encryption": 7,
        "cipher": 6
      },
...
```

You can then use this to build up the Appliance.Config.Wifi payload, example:
```json
{
  "wifi": {
    "ssid": "RElSRUNULUQzNUMyN0Q0",
    "bssid": "9e:ae:d3:5c:a7:d4",
    "channel": 5,
    "encryption": 7,
    "cipher": 6,
    "password": "Y29vbF9wYXNzd29yZA=="
  }
}
```

`password` is a base64 encoded string of your wifi password, you can obtain this by doing:
```bash
printf "cool_password" | base64 -w0
```
Example Command:
```bash
mCurl 10.10.10.1 SET Appliance.Config.Wifi '{"wifi":{"ssid":"RElSRUNULUQzNUMyN0Q0","bssid":"9e:ae:d3:5c:a7:d4","channel":5,"encryption":7,"cipher":6,"password":"Y29vbF9wYXNzd29yZA=="}}'
```

If all goes well the device should now reboot, connect to your network and then you should see a connection come in on the MQTT server logs.

After this point the device is configured and you can switch off the MQTT server. If something went wrong you can get the bulb back to configuration mode by slowly turning the light switch on and off ~ 5 times.

## Usage

You can now use the same mCurl tool to call endpoints, if the bulb has taken ip 192.168.1.148 for example you can toggle the bulb on and off by issuing the following:

```bash
mCurl 192.168.1.148 SET Appliance.Control.ToggleX '{"togglex":{"onoff": 0}}'
mCurl 192.168.1.148 SET Appliance.Control.ToggleX '{"togglex":{"onoff": 1}}'
```

See the [[protocol]](doc/protocol.md) page for details on how to construct your own REST calls. The two important commands for bulbs are `Appliance.Control.ToggleX` and `Appliance.Control.Light`


<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements

Thanks to the following project that got me off to a good start.

* https://github.com/bapirex/meross-api for providing details for `meross-cloud` to obtain existing device keys.
* https://github.com/mrgsts/mss310-kontrol for showing the JSON API details.
* https://github.com/arandall/meross for extensive documentation on API
* https://github.com/bytespider/Meross/ for the mosquitto setup steps