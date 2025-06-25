from smbus import SMBus
from time import sleep, time

from data import Event, process_data, store_data, load_data
from display import clear_displays, get_displays, activate_channel
from parameters import EVENT_TIME_DIFFERENCE_TOLERANCE, ENERGY_METHOD_DEFAULT
from utility import wait_for_matrix_ready


def get_bus():
    return SMBus(1)


def initialise(layout=None, bus=None, displays=None, mirror=False):
    if displays is not None:
        assert bus is not None, 'Need to supply bus with displays.'

    bus = get_bus() if bus is None else bus

    wait_for_matrix_ready()

    displays = get_displays(bus, layout, mirror) if displays is None else displays

    assert len(displays) > 0, 'No displays found.'

    clear_displays(bus, displays)

    return bus, displays


def animate(data, bus, displays):
    assert isinstance(data, (list, tuple))
    assert all(isinstance(d, Event) for d in data)

    previous_start_time = 0.0
    no_new_data = False
    event = None
    current_channel = None

    display_IDs = [display.ID for display in displays]

    while True:
        start_time = time()

        # Get the next event.
        try:
            event = data.pop(0)
        except IndexError:
            no_new_data = True

        if no_new_data:
            break

        # First, go and get all the IDs of the displays that are to be updated.
        updated_display_IDs = set(event.display_IDs)

        assert all(ID in display_IDs for ID in updated_display_IDs), f'Got an event on display ID that does not exist'
        
        # Then, use the set here so we only copy the buffers once.
        for ID in updated_display_IDs:
            displays[ID].copy_buffer()
        sleep(0.1) # without this, the copy doesn't always complete in time

        # Finally, actually do the pixel updates.
        for x, y, color, ID in event:
            displays[ID].set_buffer_pixel(x, y, color)

        end_time = time()

        wait_time = event.start_time - previous_start_time - (end_time - start_time)

        previous_start_time = event.start_time

        if wait_time < EVENT_TIME_DIFFERENCE_TOLERANCE:
            pass
        else:
            sleep(wait_time)

        # The pre-processed event is now ready to be displayed, switch the buffers and set the update flags for the display thread.
        for ID in updated_display_IDs:
            displays[ID].switch_buffer()

            if (current_channel is None) or (current_channel != displays[ID].channel):
                activate_channel(bus, displays[ID].channel)
                current_channel = displays[ID].channel

            displays[ID].display_current_frame(bus, forever=True, update_channel=False)  # forever=True as timing is handled by this data manager.


def run(file_=None, layout=None, bus=None, displays=None,
        energy_method=ENERGY_METHOD_DEFAULT,
        force_displays=False, normalise=True, mirror=False,data_file='',
        run_count=None):

    if file_ is not None:
        assert isinstance(file_, str)

    if displays is not None:
        assert bus is not None, 'Need to supply bus with displays.'

    assert isinstance(force_displays, bool)
    assert isinstance(normalise, bool)
    assert isinstance(mirror, bool)

    if run_count is not None:
        assert isinstance(run_count, int)
        assert run_count > 0

    time_start = time()

    bus, displays = initialise(layout, bus, displays, mirror)

    if data_file == '':
        data = process_data(file_, displays, energy_method=energy_method, normalise=normalise, mirror=mirror)
    else:
        data = load_data(data_file)

    time_middle = time()

    print('Initialisation time', time_middle-time_start)

    run_number = 0

    while True:
        run_number += 1

        time_middle = time()

        animate(data, bus, displays)

        time_end = time()

        print('Run time', time_end-time_middle)
    
        clear_displays(bus, displays)

        if (run_count is not None) and (run_number >= run_count):
            break
