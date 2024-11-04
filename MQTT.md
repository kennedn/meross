# MQTT Setup

> NOTE: MQTT server setup is entirely optional since meross devices do not care whether the configured MQTT server is online or not

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