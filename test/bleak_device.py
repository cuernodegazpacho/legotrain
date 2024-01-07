import asyncio
from bleak import BleakScanner, BleakClient

async def main():
    device = await BleakScanner.find_device_by_address('C8DEE900-B1ED-F26B-7992-6DC06438ADB5')
    print(device)
    print("name: ", device.name)
    print("address: ", device.address)
    print("details: ", device.details)
    print("metadata: ", device.metadata)

    device = await BleakScanner.find_device_by_address('CA1ADD7D-6619-B0DF-5D02-99B731959396')
    print(device)
    print("name: ", device.name)
    print("address: ", device.address)
    print("details: ", device.details)
    print("metadata: ", device.metadata)

asyncio.run(main())
