import asyncio
from bleak import BleakScanner, BleakClient

async def main():
    device = await BleakScanner.find_device_by_address('86996732-BF5A-433D-AACE-5611D4C6271D')
    print(device)
    print("name: ", device.name)
    print("address: ", device.address)
    print("details: ", device.details)
    print("metadata: ", device.metadata)

asyncio.run(main())
