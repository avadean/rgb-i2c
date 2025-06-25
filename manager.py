from smbus import SMBus
from threading import Thread
from time import sleep, time

from data import Event, process_data, store_data, load_data
from display import clear_displays, get_displays, activate_channel
from parameters import EVENT_TIME_DIFFERENCE_TOLERANCE, WAIT_DISPLAY, ENERGY_METHOD_DEFAULT
from utility import wait_for_matrix_ready


global g_bus
global g_displays
global g_break
global g_current_channel


def get_bus():
    return SMBus(1)


def reset():
    global g_bus
    global g_displays
    global g_break
    global g_current_channel

    g_bus = None  # The SMBus.
    g_displays = [] # List of displays.
    g_break = False  # Global break statement so each thread knows when to quit.
    g_current_channel = None  # What channel of the multiplexer are we currently on?


def initialise(layout=None, bus=None, displays=None, mirror=False):
    global g_bus
    global g_displays

    if displays is not None:
        assert bus is not None, 'Need to supply bus with displays.'

    reset()

    g_bus = get_bus() if bus is None else bus

    wait_for_matrix_ready()

    g_displays = get_displays(g_bus, layout, mirror) if displays is None else displays

    assert len(g_displays) > 0, 'No displays found.'

    clear_displays(g_bus, g_displays)



def display_manager():
    global g_bus
    global g_displays
    global g_break
    global g_current_channel

    while True:
        for display in g_displays:
            if display.needs_updating:

                if (g_current_channel is None) or (g_current_channel != display.channel):
                    activate_channel(g_bus, display.channel)
                    g_current_channel = display.channel

                display.display_current_frame(g_bus, forever=True, update_channel=False)  # forever=True as timing is handled by the data manager. update_channel=False as is handled by display_manager (just above).

                display.needs_updating = False

        sleep(WAIT_DISPLAY)

        if g_break:
            clear_displays(g_bus, g_displays)
            break


def data_manager(data):
    global g_bus
    global g_displays
    global g_break

    assert isinstance(data, (list, tuple))
    assert all(isinstance(d, Event) for d in data)

    time_last_error_msg = -999.0
    previous_start_time = 0.0

    first_pass = True
    no_new_data = False

    event = None

    while True:
        start_time = time()

        # Get the next event.
        try:
            event = data.pop(0)
            #print(event)
        except IndexError:
            no_new_data = True

        if no_new_data:
            g_break = True

        if g_break:
            break

        # First, go and get all the IDs of the displays that are to be updated.
        updated_display_IDs = set(event.display_IDs)
        #print("Updated display IDs ",updated_display_IDs)
        
        # Then, use the set here so we only copy the buffers once.
        for ID in updated_display_IDs:
            #print("ID ",ID,g_displays[ID].ID,g_displays[ID].addr)
            g_displays[ID].copy_buffer()
        sleep(0.1) # without this, the copy doesn't always complete in time

        # Finally, actually do the pixel updates.
        for x, y, color, ID in event:
            #print("x,y,color,ID ",x,y,color,ID)
            g_displays[ID].set_buffer_pixel(x, y, color)

        end_time = time()

        wait_time = event.start_time - previous_start_time - (end_time - start_time)

        previous_start_time = event.start_time

        if wait_time < EVENT_TIME_DIFFERENCE_TOLERANCE:
            if (time() - time_last_error_msg) > 1.0 and not first_pass:
                print('Warning: time to update frame longer than time between events.')
                time_last_error_msg = time()
        else:
            sleep(wait_time)

        # The pre-processed event is now ready to be displayed, switch the buffers and set the update flags for the display thread.
        for ID in updated_display_IDs:
            g_displays[ID].switch_buffer()
            g_displays[ID].needs_updating = True

        first_pass = False


def run(file_=None, layout=None, bus=None, displays=None,
        energy_method=ENERGY_METHOD_DEFAULT,
        force_displays=False, normalise=True, mirror=False,
        preprocessed_file=None):
    global g_displays

    if displays is not None:
        assert bus is not None, 'Need to supply bus with displays.'

    assert isinstance(force_displays, bool)
    assert isinstance(normalise, bool)
    assert isinstance(mirror, bool)

    time_start = time()

    initialise(layout, bus, displays, mirror)

    if preprocessed_file is not None:
        assert isinstance(preprocessed_file, str)

        if file_ is not None:
            print(f'Both input and pre-processed file given. Using pre-processed file.')

        data = load_data(preprocessed_file)
    else:
        assert isinstance(file_, str)

        data = process_data(file_, g_displays, energy_method=energy_method, normalise=normalise, mirror=mirror)

    thread_display = Thread(target=display_manager, name='Display')
    thread_data = Thread(target=data_manager, args=(data,), name='Data')

    time_middle = time()
    
    thread_display.start()
    thread_data.start()
    
    thread_display.join()
    thread_data.join()
    
    time_end = time()
    
    print('Initialisation time', time_middle-time_start)
    print('Run time', time_end-time_middle)
    
    clear_displays(g_bus, g_displays)

    reset()

