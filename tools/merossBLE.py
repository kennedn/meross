#!/usr/bin/env python3

import os
import sys
import struct
import argparse
import json
import asyncio
from zlib import crc32
from hashlib import md5
from string import Template
from base64 import b64encode, b64decode
from bleak import BleakClient, BleakScanner
from Crypto.Cipher import AES

# Constants, see https://github.com/Fabi019/MerossBLE?tab=readme-ov-file#protocol
SERVICE_UUID = '0000a00a-0000-1000-8000-00805f9b34fb'
WRITE_CHAR_UUID = '0000b002-0000-1000-8000-00805f9b34fb'
NOTIFY_CHAR_UUID = '0000b003-0000-1000-8000-00805f9b34fb'
HEADER_TEMPLATE = Template('{"header":{"from":"","messageId":"$messageId","method":"$method","namespace":"$namespace","payloadVersion":1,"sign":"$sign","timestamp":"$ts"},"payload":$payload}')
MAGIC_START = b'\x55\xaa'
MAGIC_END = b'\xaa\x55'


def print_wifi(payload, ssid=None):
    wifi_list = json.loads(payload)
    filtered_list = [
        {
            "ssid": b64decode(wifi['ssid']).decode(),
            "bssid": wifi['bssid'],
            "channel": wifi['channel'],
            "encryption": wifi['encryption'],
            "cipher": wifi['cipher'],
            "signal strength": wifi['signal']
        }
        for wifi in wifi_list['payload']['wifiList']
        if ssid is None or b64decode(wifi['ssid']).decode() == ssid
    ]
    if len(filtered_list) == 1:
        filtered_list = filtered_list[0]
    print(json.dumps(filtered_list, separators=(',', ':')))


def generate_config_payload(host, port, key, userid):
    return json.dumps({
        "key": {
            "gateway": {
                "host": host,
                "port": port
            },
            "key": key,
            "userId": userid
        }
    }, separators=(',', ':'))


def generate_wifi_payload(ssid, password, bssid, channel, encryption, cipher):
    return json.dumps({
        "wifi": {
            "ssid": b64encode(ssid.encode('utf-8')).decode(),
            "password": password,
            "bssid": bssid,
            "channel": channel,
            "encryption": encryption,
            "cipher": cipher
        },
    }, separators=(',', ':'))


def wifix_aes_password(password, type, uuid, mac_address):
    key = md5((type + uuid + mac_address).encode('utf-8')).hexdigest().encode('utf-8')
    iv = b'0' * AES.block_size
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return b64encode(cipher.encrypt(password.ljust(AES.block_size, '\0').encode('utf-8'))).decode()


def encode_request(method, namespace, payload):
    # messageId must be random on newer firmwares
    messageId = os.urandom(16).hex()
    # ts is supposed to be the current unix timestamp but in practise can be set to anything
    ts = '0'
    # sign is an md5sum of messageId + key + ts, key is not available until configuration is completed, so can be safely ignored in the sum for now
    sign = md5(f"{messageId}{ts}".encode('utf-8')).hexdigest()
    # Substitute template with variables to build up JSON request to be sent to device
    data = bytes(HEADER_TEMPLATE.substitute(messageId=messageId, method=method, namespace=namespace, sign=sign, ts=ts, payload=payload), 'utf-8')
    # Pack length into 2 byte big endian
    length = struct.pack('>H', len(data))
    # Pack crc into 4 byte big endian
    crc = struct.pack('>I', crc32(data))

    # Packet structure is:
    # |----------------------------------------------------------------|
    # |       55aa (2 bytes)         |     Data Length (2 bytes)       |
    # |----------------------------------------------------------------|
    # |                                                                |
    # |                      Data (Data Length Bytes)                  |
    # |                                                                |
    # |----------------------------------------------------------------|
    # |                     CRC32 Checksum (4 bytes)                   |
    # |----------------------------------------------------------------|
    # |      aa55 (2 bytes)          |
    # |------------------------------|
    return MAGIC_START + length + data + crc + MAGIC_END


def process_response(raw_concat):
    # Packet structure is:
    # |----------------------------------------------------------------|
    # |       55aa (2 bytes)         |     Data Length (2 bytes)       |
    # |----------------------------------------------------------------|
    # |                                                                |
    # |                      Data (Data Length Bytes)                  |
    # |                                                                |
    # |----------------------------------------------------------------|
    # |                     CRC32 Checksum (4 bytes)                   |
    # |----------------------------------------------------------------|
    # |      aa55 (2 bytes)          |
    # |------------------------------|
    # Extract data length from packet
    _, data_length = struct.unpack('>2sH', raw_concat[:4])
    # Extract data from packet using data length
    data = raw_concat[4:4 + data_length]
    # Extract crc from packet
    crc = struct.unpack('>I', raw_concat[4 + data_length: 4 + data_length + 4])[0]
    # Compute our own crc
    computed_crc = crc32(data)

    if crc != computed_crc:
        print("CRC mismatch on data", file=sys.stderr)
    return data.decode()


def decode_response(sender, value, future_response, raw_concat):
    # Response data is sent piece meal (MTU seem to always negotiate to 244), must be re-constructed piece meal
    if value.startswith(MAGIC_START):
        raw_concat.clear()
    raw_concat.extend(value)

    # Last packet obtained, can process data now
    if value.endswith(MAGIC_END):
        resp = process_response(raw_concat)
        future_response.set_result(resp)


# Look for Bluetooth devices that advertise the meross custom service
async def meross_scan():
    devices = await BleakScanner(service_uuids=[SERVICE_UUID]).discover()
    if len(devices) == 0:
        print("No devices found")
    else:
        for device in devices:
            print(device.address)


async def meross_send(method, namespace, payload, client):
    payload = encode_request(method, namespace, payload)
    future_response = asyncio.Future()
    raw_concat = bytearray()

    async def decode_response_wrapper(sender, value):
        return decode_response(sender, value, future_response, raw_concat)

    async def bleak_io():
        # BlueZ doesn't have a proper way to get the MTU, so we have this hack. see https://github.com/hbldh/bleak/blob/develop/examples/mtu_size.py
        if client._backend.__class__.__name__ == "BleakClientBlueZDBus" and client._backend._mtu_size is None:
            await client._backend._acquire_mtu()
        chunk_size = client.mtu_size - 3

        await client.start_notify(NOTIFY_CHAR_UUID, decode_response_wrapper)

        for chunk in [payload[i:i + chunk_size] for i in range(0, len(payload), chunk_size)]:
            await client.write_gatt_char(WRITE_CHAR_UUID, chunk, response=False)
        response = await future_response

        await client.stop_notify(NOTIFY_CHAR_UUID)

        return response

    if client.is_connected:
        return await bleak_io()
    else:
        async with client as client:
            return await bleak_io()


async def meross_onboard(args):
    async with BleakClient(args.mac_address) as client:
        # BlueZ doesn't have a proper way to get the MTU, so we have this hack. see https://github.com/hbldh/bleak/blob/develop/examples/mtu_size.py
        if client._backend.__class__.__name__ == "BleakClientBlueZDBus" and client._backend._mtu_size is None:
            await client._backend._acquire_mtu()

        response = await meross_send("GET", "Appliance.System.Hardware", "{}", client)
        print(response)

        try:
            hardware = json.loads(response)['payload']['hardware']
        except json.JSONDecodeError:
            print("response was not valid json")

        type = hardware['type']
        uuid = hardware['uuid']
        mac_address = hardware['macAddress']

        print(await meross_send("SET", "Appliance.Config.Key", generate_config_payload(
            args.host,
            args.port,
            args.key,
            args.userid
        ), client))

        password = wifix_aes_password(args.password, type, uuid, mac_address)

        print(await meross_send("SET", "Appliance.Config.WifiX", generate_wifi_payload(
            args.ssid,
            password,
            args.bssid,
            args.channel,
            args.encryption,
            args.cipher
        ), client))


def main():
    parser = argparse.ArgumentParser(description="Interact with a Meross Bluetooth Device.")

    subparsers = parser.add_subparsers(dest="command", help="Sub-command help")

    # Subcommand for device scan
    subparsers.add_parser("scan", help="Scan for Meross Bluetooth LE device")

    # Subcommand for wifi scan
    wifi_scan_parser = subparsers.add_parser("wifi_scan", help="Scan for Wifi Networks")
    wifi_scan_parser.add_argument("-a", "--mac_address", required=True, help="MAC address of the Meross device")
    wifi_scan_parser.add_argument("-s", "--ssid", default=None, help="Filter the returned Wifi list by SSID")

    # Subcommand for sending a packet
    packet_parser = subparsers.add_parser("send", help="Send a packet to the Meross device")
    packet_parser.add_argument("-a", "--mac_address", required=True, help="MAC address of the Meross device")
    packet_parser.add_argument("-m", "--method", required=True, help="Method for the packet")
    packet_parser.add_argument("-n", "--namespace", required=True, help="Namespace for the packet")
    packet_parser.add_argument("-p", "--payload", required=True, help="Payload for the packet")

    # Subcommand for onboarding a device
    onboard_parser = subparsers.add_parser("onboard", help="Onboard a Meross Bluetooth LE device")
    onboard_parser.add_argument("-a", "--mac-address", required=True, help="Mac address of BLE Meross device")
    onboard_parser.add_argument("-d", "--host", required=True, help="Specify the host to connect to")
    onboard_parser.add_argument("-P", "--port", required=True, help="Specify the port to connect to")
    onboard_parser.add_argument("-k", "--key", required=True, help="Specify the key for authentication")
    onboard_parser.add_argument("-p", "--password", required=True, help="Specify the password for the WiFi network")
    onboard_parser.add_argument("-j", "--from-json", help="Specify a wifi JSON object")
    onboard_parser.add_argument("-u", "--userid", default="0", help="Specify the user ID")
    onboard_parser.add_argument("-s", "--ssid", help="Specify the SSID of the WiFi network")
    onboard_parser.add_argument("-b", "--bssid", help="Specify the BSSID of the WiFi network")
    onboard_parser.add_argument("-c", "--channel", help="Specify the channel of the WiFi network")
    onboard_parser.add_argument("-e", "--encryption", help="Specify the encryption type of the WiFi network")
    onboard_parser.add_argument("-C", "--cipher", help="Specify the cipher type of the WiFi network")
    onboard_parser.add_argument("-w", "--wifi", action="store_true", help="List available WiFi networks")

    args = parser.parse_args()

    if args.command == "scan":
        asyncio.run(meross_scan())
    elif args.command == "wifi_scan":
        print_wifi(asyncio.run(meross_send("GET", "Appliance.Config.WifiList", "{}", BleakClient(args.mac_address))), args.ssid)
    elif args.command == "send":
        print(asyncio.run(meross_send(args.method, args.namespace, args.payload, BleakClient(args.mac_address))))
    elif args.command == "onboard":
        if args.from_json:
            wifi_config = json.loads(args.from_json)
            args.ssid = args.ssid or wifi_config.get("ssid")
            args.bssid = args.bssid or wifi_config.get("bssid")
            args.channel = args.channel or wifi_config.get("channel")
            args.encryption = args.encryption or wifi_config.get("encryption")
            args.cipher = args.cipher or wifi_config.get("cipher")

        if not all([args.ssid, args.password, args.bssid, args.channel, args.encryption, args.cipher]):
            print("Error: Required WiFi connection parameters are missing.", file=sys.stderr)
            parser.print_help()
            sys.exit(1)
        asyncio.run(meross_onboard(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
