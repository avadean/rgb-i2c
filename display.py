from copy import deepcopy
from numpy import ceil, sqrt
from smbus import SMBus
from time import sleep

from parameters import DEFAULT_I2C_ADDR, I2C_CMD_DISP_OFF, I2C_CMD_GET_DEV_ID, I2C_CMD_SET_ADDR, \
    I2C_CMD_DISP_EMOJI, I2C_CMD_DISP_NUM, I2C_CMD_DISP_STR, I2C_CMD_DISP_CUSTOM, I2C_CMD_CONTINUE_DATA, \
    DEVICE_NUM_MIN, DEVICE_NUM_MAX, LETTERS, \
    COLORS, COLOR_DEFAULT, WAIT_READ, WAIT_WRITE

from utility import int_to_bytes


def get_displays(bus, layout=None, force=False):
    assert isinstance(bus, SMBus)
    assert isinstance(force, bool)  # Can we reuse displays if not enough are found for the requested layout?

    if layout is not None:
        if isinstance(layout, int):
            layout = (layout,)  # If a single number is supplied, turn it into a tuple.
        else:
            assert isinstance(layout, tuple)
            assert all(isinstance(i, int) for i in layout)

    # Let's first work out how many displays we have by collecting the addresses.
    print("Scanning for devices on I2C bus")
    addresses = get_addresses(bus)
    print("Found devices with addresses: ",addresses)

    # If a layout was supplied, ensure we have at least enough devices.
    if layout is not None:
        if len(addresses) < sum(layout):
            if not force:
                raise ValueError(f'Requested layout size is {sum(layout)}, but only {len(addresses)} display(s) found.')
            else:
                addresses *= 1 + sum(layout) // len(addresses)  # Duplicate addresses until we have enough.

        # We only keep the addresses that are needed if a layout is supplied.
        addresses = addresses[:sum(layout)]

    else:  # Just create a dummy layout if none was supplied.
        layout = (len(addresses),)

    # Let's now create the Display objects.
    displays = []

    # The side, X and Y data for each display.
    coordinates = [[divmod(n, int(ceil(sqrt(side_size)))) for n in range(side_size)] for side_size in layout]

    current_ID = 0

    for (side, YXs) in enumerate(coordinates):
        for Y, X in YXs:  # divmod() gives (Y, X) co-ordinates so need to be careful.
            displays.append(Display(side=side, X=X, Y=Y, ID=current_ID, address=addresses[current_ID]))
            current_ID += 1

    return displays


def get_addresses(bus):
    assert isinstance(bus, SMBus)

    addresses = []

    for device in range(DEVICE_NUM_MIN, DEVICE_NUM_MAX+1):
        found = False

        try:
            bus.read_byte(device)
            sleep(WAIT_READ)
            found = True
        except OSError:
            pass

        if found:
            addresses.append(device)

    return addresses


def display_arranger(bus, displays):
    num_sides = max([display.side for display in displays]) + 1

    string = ''

    for side in range(num_sides):
        len_X = max([display.X for display in displays]) + 1
        len_Y = max([display.Y for display in displays]) + 1

        array = [['' for _ in range(len_X)] for _ in range(len_Y)]

        for display in displays:
            if display.side == side:
                array[display.Y][display.X] = display.char

        string += f'Side {side} ->\n'

        for rows in array:
            string += '  '

            for char in rows:
                string += char + ' '

            string = string[:-1] + '\n'

    for display in displays:
        display.display_string(bus, display.char, forever=True)

    return string[:-1]


def switch_displays(display_A, display_B):
    assert isinstance(display_A, Display)
    assert isinstance(display_B, Display)

    display_A.addr, display_B.addr = display_B.addr, display_A.addr


def switch_displays_from_chars(displays, char1, char2):
    assert isinstance(char1, str)
    assert isinstance(char2, str)
    assert len(char1) == 1
    assert len(char2) == 1

    display1 = get_display_from_char(displays, char1)
    display2 = get_display_from_char(displays, char2)

    switch_displays(display1, display2)


def get_display_from_char(displays, char):
    assert isinstance(char, str)
    assert len(char) == 1

    for display in displays:
        if display.char == char:
            return display

    raise ValueError(f'No display with char {char}.')


def clear_displays(bus, displays):
    assert isinstance(bus, SMBus)

    for display in displays:
        display.clear_display(bus)


def get_display_ID(displays, x, y, side):
    ''' Returns the display which handles the given global (x, y) co-ordinate and side. '''

    assert len(displays) > 0, 'No displays found.'
    assert len({d.size for d in displays}) == 1, 'Can currently only work with all displays of equal size.'

    display_size = displays[0].size  # We are assuming they are all the same size.

    X = x // display_size  # This is the display.X value we want to search for.
    Y = y // display_size  # This is the display.Y value we want to search for.

    for display in displays:
        if (display.X == X) and (display.Y == Y) and (display.side == side):
            return display.ID

    raise ValueError(f'Could not find display to show pixel ({x}, {y}) on side {side}.')


class Display:
    def __init__(self, size=8, side=0, X=0, Y=0,
                 ID=0, address=DEFAULT_I2C_ADDR):
        assert isinstance(size, int)
        assert isinstance(side, int)
        assert isinstance(X, int)
        assert isinstance(Y, int)
        assert isinstance(ID, int)
        assert isinstance(address, int)

        assert size == 8, 'HARD CODED SIZE OF 8 FOR NOW.'  # TODO: displays are currently hard coded to a size of 8x8.
        assert size > 0, 'Size of display must be > 0.'
        assert side >= 0, 'Side must be >= 0.'
        assert X >= 0, 'X location of display should be >= 0.'
        assert Y >= 0, 'Y location of display should be >= 0.'
        assert len(LETTERS) >= ID >= 0, f'Device ID should be {len(LETTERS)} >= 0.'
        assert DEVICE_NUM_MAX >= address >= DEVICE_NUM_MIN, f'Device address {address} outside of sensible range.'

        self.size = size
        self.side = side
        self.X = X
        self.Y = Y
        self.ID = ID
        self.char = LETTERS[ID]
        self.addr = address

        self.frame_A = [COLOR_DEFAULT for _ in range(self.size * self.size)]  # [Pixel() for _ in range(self.size * self.size)]
        self.frame_B = deepcopy(self.frame_A)

        self.display_frame_A = True  # Do we use the A or B frame for displaying?
        self.change_detected = False  # Has a change been detected on this display from the data manager?
        self.needs_updating = False  # So the display thread knows whether to bother updating this display or not.

    def __repr__(self):
        return f'{self.addr}: ({self.X},{self.Y}) side {self.side}'

    def get_VID(self, bus):
        assert isinstance(bus, SMBus)
    
        bus.write_byte_data(self.addr, 0, I2C_CMD_GET_DEV_ID)
    
        result = bus.read_i2c_block_data(self.addr, 0, 2)
    
        return hex(result[1]), hex(result[0])

    def set_device_address(self, bus, new_address=DEFAULT_I2C_ADDR):
        assert isinstance(bus, SMBus)
        assert isinstance(new_address, int)

        assert DEVICE_NUM_MAX >= new_address >= DEVICE_NUM_MIN, f'Device address {address} outside of sensible range.'

        bus.write_byte_data(self.addr, I2C_CMD_SET_ADDR, new_address)
        sleep(WAIT_WRITE)

        self.addr = new_address

    def clear_display(self, bus):
        assert isinstance(bus, SMBus)

        bus.write_byte_data(self.addr, I2C_CMD_DISP_OFF, 0)

    def display_emoji(self, bus, emoji, duration=1, forever=False):
        assert isinstance(bus, SMBus)
        assert isinstance(emoji, int)
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)
    
        assert duration > 0.001, 'Error: duration should be at least 1 ms.'
    
        duration_bytes = int_to_bytes(int(duration * 1000)) # Duration is in ms.
    
        data = [emoji, duration_bytes[1], duration_bytes[0], forever]
    
        bus.write_i2c_block_data(self.addr, I2C_CMD_DISP_EMOJI, data)
        sleep(WAIT_WRITE)
    
    def display_number(self, bus, number, color='blue', duration=1, forever=False):
        assert isinstance(bus, SMBus)
        assert isinstance(number, int)
        assert isinstance(color, (str, int))
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)
    
        assert duration > 0.001, 'Error: duration should be at least 1 ms.'

        if isinstance(color, str):
            assert color in COLORS.keys(), f'Error: invalid colour {color} must be one of {COLORS.keys()}.'
            color = COLORS[color]
        elif isinstance(color, int):
            assert 255 >= color >= 0, 'Colour number should be between 0 and 255.'

        number_bytes = int_to_bytes(number)
        duration_bytes = int_to_bytes(int(duration * 1000)) # Duration is in ms.
    
        data = [number_bytes[1], number_bytes[0], duration_bytes[1], duration_bytes[0], forever, color]
    
        bus.write_i2c_block_data(self.addr, I2C_CMD_DISP_NUM, data)
        sleep(WAIT_WRITE)

    def display_string(self, bus, string, color='blue', duration=1, forever=False):
        assert isinstance(bus, SMBus)
        assert isinstance(string, str)
        assert isinstance(color, (str, int))
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)
    
        assert duration > 0.001, 'Error: duration should be at least 1 ms.'

        if isinstance(color, str):
            assert color in COLORS.keys(), f'Error: invalid colour {color} must be one of {COLORS.keys()}.'
            color = COLORS[color]
        elif isinstance(color, int):
            assert 255 >= color >= 0, 'Colour number should be between 0 and 255.'

        assert len(string) <= 27, 'Length of string too long to display.'

        duration_bytes = int_to_bytes(int(duration * 1000)) # Duration is in ms.
    
        data = [forever, duration_bytes[1], duration_bytes[0], len(string), color] + list(string.encode('ascii'))
    
        bus.write_i2c_block_data(self.addr, I2C_CMD_DISP_STR, data)
        sleep(WAIT_WRITE)
    
    def display_pixel(self, bus, x, y, color='blue', duration=1, forever=False):
        assert isinstance(bus, SMBus)
        assert isinstance(x, int)
        assert isinstance(y, int)
        assert isinstance(color, (str, int))
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)

        assert self.size > x >= 0, 'Error: x value supplied is outside of frame range.'
        assert self.size > y >= 0, 'Error: y value supplied is outside of frame range.'
        assert duration > 0.001, 'Error: duration should be at least 1 ms.'

        if isinstance(color, str):
            assert color in COLORS.keys(), f'Error: invalid colour {color} must be one of {COLORS.keys()}'
            color = COLORS[color]
        elif isinstance(color, int):
            assert 255 >= color >= 0, 'Colour number should be between 0 and 255.'

        num_frames = 1 # For now.
        
        frame = [COLORS['black']] * self.size * self.size  # Start as blank frame.
        index = x + self.size * y  # 2D index to integer.
        frame[index] = color  # Colour the requested pixel.
    
        duration_bytes = int_to_bytes(int(duration * 1000))  # Duration is in ms.
        
        # Data of the frame.
        # The latter 3 zeroes are redundant data.
        data = [duration_bytes[1], duration_bytes[0], forever, num_frames, 0, 0, 0]
    
        # Now send the data.
        # Maximum of 32 bytes allowed per send, so the 71 pieces of info are split into 3 chunks of 7, 32, 32.
        bus.write_i2c_block_data(self.addr, I2C_CMD_DISP_CUSTOM, data)
        sleep(WAIT_WRITE)
        bus.write_i2c_block_data(self.addr, I2C_CMD_CONTINUE_DATA, frame[:32])  # TODO: remove assumption that we have 8x8.
        sleep(WAIT_WRITE)
        bus.write_i2c_block_data(self.addr, I2C_CMD_CONTINUE_DATA, frame[32:])  # TODO: remove assumption that we have 8x8.
        sleep(WAIT_WRITE)

    def display_current_frame(self, bus, duration=1, forever=False):
        assert isinstance(bus, SMBus)
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)
    
        assert duration > 0.001, 'Error: duration should be at least 1 ms.'
        
        duration_bytes = int_to_bytes(int(duration * 1000)) # Duration is in ms.
        
        # Data of the frame.
        # The latter 3 zeroes are redundant data.
        data = [duration_bytes[1], duration_bytes[0], forever, 1, 0, 0, 0]  # The 1 is the number of frames.

        frame = self.frame_A if self.display_frame_A else self.frame_B

        # Now send the data.
        # Maximum of 32 bytes allowed per send, so the 71 pieces of info are split into 3 chunks of 7, 32, 32.
        bus.write_i2c_block_data(self.addr, I2C_CMD_DISP_CUSTOM, data)
        sleep(WAIT_WRITE)
        bus.write_i2c_block_data(self.addr, I2C_CMD_CONTINUE_DATA, frame[:32])  # TODO: remove assumption that we have 8x8.
        sleep(WAIT_WRITE)
        bus.write_i2c_block_data(self.addr, I2C_CMD_CONTINUE_DATA, frame[32:])  # TODO: remove assumption that we have 8x8.
        sleep(WAIT_WRITE)

    def set_buffer_pixel(self, x, y, color):
        ''' Updates whichever frame is not in use for displaying with a provided pixel co-ordinate and colour. '''

        assert isinstance(x, int)
        assert isinstance(y, int)
        assert isinstance(color, int)

        assert self.size > x >= 0, 'Error: x value supplied is outside of frame range.'
        assert self.size > y >= 0, 'Error: y value supplied is outside of frame range.'
        assert 255 >= color >= 0, 'Colour number should be between 0 and 255.'

        if self.display_frame_A:                                         
            self.frame_B[x + self.size * y] = color
        else:
            self.frame_A[x + self.size * y] = color

    def copy_buffer(self):
        if self.display_frame_A:
            self.frame_B = deepcopy(self.frame_A)
        else:
            self.frame_A = deepcopy(self.frame_B)

    def switch_buffer(self):
        self.display_frame_A = not self.display_frame_A

