#!/usr/bin/env python
from smbus import SMBus
from parameters import DEFAULT_I2C_ADDR , I2C_CMD_SET_ADDR, WAIT_INITIAL
from time import sleep

# Assume we want bus number 1
bus = SMBus(1)

print("Reading from default address... ",bus.read_byte(DEFAULT_I2C_ADDR))

# For the PET imaging our convention is that the first decimal digit is the detector number (1,2,...,6)
# and the second decimal digit is which display it is. 0-3 are the ones facing the source, 4-7 are the ones
# facing away.
new_address = 87
print("Setting address to ",int(new_address))
bus.write_byte_data(DEFAULT_I2C_ADDR,I2C_CMD_SET_ADDR,int(new_address))

sleep(WAIT_INITIAL)

print("Reading from new address... ",bus.read_byte(int(new_address)))


#bus.read_byte(DEFAULT_I2C_ADDR)
#bus.read_byte(new_address)
