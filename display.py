from copy import deepcopy
from numpy import ceil, sqrt
from smbus import SMBus
from time import sleep

from parameters import DEFAULT_I2C_ADDR, I2C_CMD_DISP_OFF, I2C_CMD_GET_DEV_ID, I2C_CMD_SET_ADDR, \
    I2C_CMD_DISP_EMOJI, I2C_CMD_DISP_NUM, I2C_CMD_DISP_STR, I2C_CMD_DISP_CUSTOM, I2C_CMD_CONTINUE_DATA, \
    I2C_MULTIPLEXER_ID, I2C_MULTIPLEXER_CHANNEL_IDs, \
    DEVICE_NUM_MIN, DEVICE_NUM_MAX, CHANNEL_NUM_MIN, CHANNEL_NUM_MAX, LETTERS, \
    COLORS, COLOR_DEFAULT, WAIT_READ, WAIT_WRITE, I2C_CMD_DISP_ROTATE

from utility import int_to_bytes


def get_displays(bus, layout=None, mirror=False):
    assert isinstance(bus, SMBus)
    assert isinstance(mirror, bool)  # Can we reuse displays if not enough are found for the requested layout?

    # Check for sensible layout. The layout represents a number of composite
    # displays, e.g. (a,b) means two composite displays with "a" and "b" actual
    # LED displays each. Thus layout should be either a single int (for one
    # composite display) or a tuple of ints (for many composite displays).
    if layout is not None:
        if isinstance(layout, int):
            layout = (layout,)  # If a single number is supplied, turn it into a tuple.
        else:
            assert isinstance(layout, tuple)
            assert all(isinstance(i, int) for i in layout)

    # Let's first work out how many displays we have by collecting the addresses.
    print("Scanning for devices on I2C bus")
    addresses, channels = get_addresses(bus)
    print("Found devices with addresses: ",addresses)

    # If a layout was supplied, ensure we have at least enough devices.
    # If Force is True, then this check is faked in the sense that if
    # there aren't enough addresses we just pad the address list with
    # copies of the addresses which are present.
    if layout is not None:
        if mirror:
            if len(addresses) < 2*sum(layout):
                raise ValueError(f'Requested layout size is {sum(layout)}, but only {len(addresses)} display(s) found.')
            # We only keep the addresses that are needed if a layout is supplied. We're mirroring each
            # display, so we need twice as many for each composite display.
            addresses = addresses[:2*sum(layout)]
        else:
            if len(addresses) < sum(layout):
                raise ValueError(f'Requested layout size is {sum(layout)}, but only {len(addresses)} display(s) found.')
            # We only keep the addresses that are needed if a layout is supplied.
            addresses = addresses[:sum(layout)]
    
            
    else:  # Just create a dummy layout if none was supplied.
        if mirror:
            layout = (len(addresses) // 2,)
        else:
            layout = (len(addresses),)

    # Let's now create the Display objects.
    print(f"stored addresses: {addresses}")
    displays = []

    # The side, X and Y data for each display.
    # E.g. if side_size is 4, sqrt(side_size) is 2 and the appropriate coordinates for display n are
    #      X = n%2 and Y = n//2. Note that divmod returns these in the opposite order, i.e. Y , X.
    coordinates = [[divmod(n, int(ceil(sqrt(side_size)))) for n in range(side_size)] for side_size in layout]

    current_ID = 0

    for (side, YXs) in enumerate(coordinates):
        # First give IDs to the principle displays; for testing when using fewer displays ("sides"), can set side
        # to a different value to plot the data for another side instead
        for Y, X in YXs:  # divmod() gives (Y, X) co-ordinates so need to be careful.
            displays.append(Display(side=side, X=X, Y=Y, ID=current_ID, address=addresses[current_ID], channel=channels[current_ID]))
            current_ID += 1

        # Now give IDs to any displays which are "mirroring" a principal display. When mirroring, the mirror display should
        # have the same display coordinates (the actual mirroring is done at setup for the addresses, and when plotting)
        if mirror:
             for Y, X in YXs:  # divmod() gives (Y, X) co-ordinates so need to be careful.
                displays.append(Display(side=side, X=X, Y=Y, ID=current_ID, address=addresses[current_ID], channel=channels[current_ID], mirror=True))
                current_ID += 1
            
    return displays


def get_addresses(bus):
    assert isinstance(bus, SMBus)

    addresses = []
    channels = []

    for channel in I2C_MULTIPLEXER_CHANNEL_IDs:

        activate_channel(bus, channel)
        bus.write_byte(I2C_MULTIPLEXER_ID, channel)
        sleep(WAIT_WRITE)

        for device in range(DEVICE_NUM_MIN, DEVICE_NUM_MAX+1):
            if device == I2C_MULTIPLEXER_ID:
                continue
    
            found = False
    
            try:
                bus.read_byte(device)
                sleep(WAIT_READ)
                found = True
            except OSError:
                pass
    
            if found:
                addresses.append(device)
                channels.append(channel)

    return addresses, channels


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


def display_rainbow(bus,displays):
    c = ["red","orange","yellow","green","cyan","blue","purple","pink"] * len(displays)
    for i in range(len(displays)):
        print(f"{c[i]} = ",end="")
        displays[i].display_string(bus,displays[i].char,color=c[i],forever=True)


def display_rainbow_2(bus,display):
    for i in range(255):
        display.display_string(bus,"X",color=i,forever=True)
        sleep(0.3)


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


def rotate_display_from_char(bus,displays,char,num):
    assert isinstance(char, str)
    assert len(char) == 1
    assert isinstance(num, int)
    display = get_display_from_char(displays, char)
    print(f"address: {display.addr}")
    print(bus.read_byte_data(display.addr,I2C_CMD_DISP_ROTATE))
    bus.write_byte_data(display.addr,I2C_CMD_DISP_ROTATE,num)
    sleep(WAIT_WRITE)
    print(bus.read_byte_data(display.addr,I2C_CMD_DISP_ROTATE))

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

    # Uppercase X and Y are *not* pixel coordinates, but rather they refer to the display coordinates
    # within the composite display
    X = x // display_size  # This is the display.X value we want to search for.
    Y = y // display_size  # This is the display.Y value we want to search for.

    # Default the display ID to nonsensical value
    main_ID   = -1
    mirror_ID = -1

    for display in displays:
        if (display.X == X) and (display.Y == Y) and (display.side == side):
            if display.mirror:
                mirror_ID = display.ID
            else:
                main_ID = display.ID

    return main_ID, mirror_ID


def set_global_orientation(bus, orientation=1):
    assert isinstance(bus, SMBus)
    assert isinstance(orientation, int)

    addresses, channels = get_addresses(bus)

    for address, channel in zip(addresses, channels):
        activate_channel(bus, channel)

        bus.write_byte_data(address, I2C_CMD_DISP_ROTATE, orientation)
        sleep(WAIT_WRITE)


def activate_channel(bus, channel):
    assert isinstance(bus, SMBus)
    assert isinstance(channel, int)
    assert channel in I2C_MULTIPLEXER_CHANNEL_IDs

    bus.write_byte(I2C_MULTIPLEXER_ID, channel)
    sleep(WAIT_WRITE)


class Display:
    def __init__(self, size=8, side=0, X=0, Y=0,
                 ID=0, address=DEFAULT_I2C_ADDR, channel=I2C_MULTIPLEXER_ID, mirror=False):
        assert isinstance(size, int)
        assert isinstance(side, int)
        assert isinstance(X, int)
        assert isinstance(Y, int)
        assert isinstance(ID, int)
        assert isinstance(address, int)
        assert isinstance(channel, int)
        assert isinstance(mirror, bool)

        assert size == 8, 'HARD CODED SIZE OF 8 FOR NOW.'  # TODO: displays are currently hard coded to a size of 8x8.
        assert size > 0, 'Size of display must be > 0.'
        assert side >= 0, 'Side must be >= 0.'
        assert X >= 0, 'X location of display should be >= 0.'
        assert Y >= 0, 'Y location of display should be >= 0.'
        assert CHANNEL_NUM_MAX >= channel >= CHANNEL_NUM_MIN, f'Device channel {channel} outside of range.'
        assert DEVICE_NUM_MAX >= address >= DEVICE_NUM_MIN, f'Device address {address} outside of sensible range.'

        self.size = size
        self.side = side
        self.X = X
        self.Y = Y
        self.ID = ID
        self.char = LETTERS[ID % len(LETTERS)]
        self.addr = address
        self.channel = channel
        self.mirror = mirror

        self.frame_A = [COLOR_DEFAULT for _ in range(self.size * self.size)]
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

    def set_device_address(self, bus, new_address=DEFAULT_I2C_ADDR, force=False):
        assert isinstance(bus, SMBus)
        assert isinstance(new_address, int)
        assert isinstance(force, bool)

        assert DEVICE_NUM_MAX >= new_address >= DEVICE_NUM_MIN, f'Device address {new_address} outside of sensible range.'

        current_addresses, _ = get_addresses(bus)

        if new_address in current_addresses and not force:
            raise ValueError(f'Device address {new_address} already exists. Use force to overwrite.')

        bus.write_byte_data(self.addr, I2C_CMD_SET_ADDR, new_address)
        sleep(WAIT_WRITE)

        self.addr = new_address

    def clear_display(self, bus):
        assert isinstance(bus, SMBus)

        activate_channel(bus, self.channel)

        bus.write_byte_data(self.addr, I2C_CMD_DISP_OFF, 0)

    def display_emoji(self, bus, emoji, duration=1, forever=False, update_channel=True):
        assert isinstance(bus, SMBus)
        assert isinstance(emoji, int)
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)
        assert isinstance(update_channel, bool)
    
        assert duration > 0.001, 'Error: duration should be at least 1 ms.'
    
        duration_bytes = int_to_bytes(int(duration * 1000)) # Duration is in ms.
    
        data = [emoji, duration_bytes[1], duration_bytes[0], forever]

        if update_channel:
            activate_channel(bus, self.channel)
    
        bus.write_i2c_block_data(self.addr, I2C_CMD_DISP_EMOJI, data)
        sleep(WAIT_WRITE)
    
    def display_number(self, bus, number, color='blue', duration=1, forever=False, update_channel=True):
        assert isinstance(bus, SMBus)
        assert isinstance(number, int)
        assert isinstance(color, (str, int))
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)
        assert isinstance(update_channel, bool)
    
        assert duration > 0.001, 'Error: duration should be at least 1 ms.'

        if isinstance(color, str):
            assert color in COLORS.keys(), f'Error: invalid colour {color} must be one of {COLORS.keys()}.'
            color = COLORS[color]
        elif isinstance(color, int):
            assert 255 >= color >= 0, 'Colour number should be between 0 and 255.'

        number_bytes = int_to_bytes(number)
        duration_bytes = int_to_bytes(int(duration * 1000)) # Duration is in ms.
    
        data = [number_bytes[1], number_bytes[0], duration_bytes[1], duration_bytes[0], forever, color]

        if update_channel:
            activate_channel(bus, self.channel)

        bus.write_i2c_block_data(self.addr, I2C_CMD_DISP_NUM, data)
        sleep(WAIT_WRITE)

    def display_string(self, bus, string, color='blue', duration=1, forever=False, update_channel=True):
        assert isinstance(bus, SMBus)
        assert isinstance(string, str)
        assert isinstance(color, (str, int))
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)
        assert isinstance(update_channel, bool)
    
        assert duration > 0.001, 'Error: duration should be at least 1 ms.'

        if isinstance(color, str):
            assert color in COLORS.keys(), f'Error: invalid colour {color} must be one of {COLORS.keys()}.'
            color = COLORS[color]
            print(color)
        elif isinstance(color, int):
            assert 255 >= color >= 0, 'Colour number should be between 0 and 255.'

        assert len(string) <= 27, 'Length of string too long to display.'

        duration_bytes = int_to_bytes(int(duration * 1000)) # Duration is in ms.
    
        data = [forever, duration_bytes[1], duration_bytes[0], len(string), color] + list(string.encode('ascii'))

        if update_channel:
            activate_channel(bus, self.channel)
    
        bus.write_i2c_block_data(self.addr, I2C_CMD_DISP_STR, data)
        sleep(WAIT_WRITE)
    
    def display_pixel(self, bus, x, y, color='blue', duration=1, forever=False, update_channel=True):
        assert isinstance(bus, SMBus)
        assert isinstance(x, int)
        assert isinstance(y, int)
        assert isinstance(color, (str, int))
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)
        assert isinstance(update_channel, bool)

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

        if update_channel:
            activate_channel(bus, self.channel)
    
        # Now send the data.
        # Maximum of 32 bytes allowed per send, so the 71 pieces of info are split into 3 chunks of 7, 32, 32.
        bus.write_i2c_block_data(self.addr, I2C_CMD_DISP_CUSTOM, data)
        sleep(WAIT_WRITE)
        bus.write_i2c_block_data(self.addr, I2C_CMD_CONTINUE_DATA, frame[:32])  # TODO: remove assumption that we have 8x8.
        sleep(WAIT_WRITE)
        bus.write_i2c_block_data(self.addr, I2C_CMD_CONTINUE_DATA, frame[32:])  # TODO: remove assumption that we have 8x8.
        sleep(WAIT_WRITE)

    def display_current_frame(self, bus, duration=1, forever=False, update_channel=True):
        assert isinstance(bus, SMBus)
        assert isinstance(duration, (float, int))
        assert isinstance(forever, bool)
        assert isinstance(update_channel, bool)
    
        assert duration > 0.001, 'Error: duration should be at least 1 ms.'
        
        duration_bytes = int_to_bytes(int(duration * 1000)) # Duration is in ms.
        
        # Data of the frame.
        # The latter 3 zeroes are redundant data.
        data = [duration_bytes[1], duration_bytes[0], forever, 1, 0, 0, 0]  # The 1 is the number of frames.

        frame = self.frame_A if self.display_frame_A else self.frame_B

        if update_channel:
            activate_channel(bus, self.channel)

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
        #print(color)
        #if color>255:
        #    color=251
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
