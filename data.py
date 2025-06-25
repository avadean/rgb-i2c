from numpy import loadtxt, inf
from pickle import dump as pickle_dump, load as pickle_load
from time import time as get_time
from tqdm import tqdm
from display import Display, get_display_ID
from parameters import COLOR_DEFAULT, COLOR_GRADIENT_DEFAULT, COLOR_METHODS, COLOR_METHOD_DEFAULT, \
    ENERGY_METHODS, ENERGY_METHOD_DEFAULT, ENERGY_TICK_RATE_DEFAULT, \
    EVENT_TIME_DIFFERENCE_TOLERANCE, GRADIENT_DELAY
from utility import get_color_from_gradient, get_num_ticks, get_quantity


def preprocess_data(file_=None, displays=None,
                    energy_method=ENERGY_METHOD_DEFAULT,
                    normalise=True, mirror=False, out_file='example'):

    time_start = get_time()

    data = process_data(file_, displays, energy_method=energy_method, normalise=normalise, mirror=mirror)
    store_data(_file=out_file,data=data)

    time_end = get_time()

    print(f'Pre-processing complete in {time_end-time_start}s', )


def process_data(file_,
                 displays,
                 color_method=COLOR_METHOD_DEFAULT,
                 energy_method=ENERGY_METHOD_DEFAULT,
                 energy_tick_rate=ENERGY_TICK_RATE_DEFAULT,
                 gradient_delay=GRADIENT_DELAY,
                 color_gradient=COLOR_GRADIENT_DEFAULT,
                 normalise=True,mirror=False):

    assert isinstance(file_, str)
    assert all(isinstance(display, Display) for display in displays)
    assert isinstance(color_method, str)
    assert isinstance(energy_tick_rate, (float, int))
    assert isinstance(gradient_delay, (float, int))
    assert isinstance(color_gradient, tuple)
    assert len(color_gradient) == 2
    assert all(isinstance(energy, (float, int)) and isinstance(color, int) for energy, color in zip(*color_gradient))
    assert isinstance(normalise, bool)  # Do we want to normalise the time of the data to have on avg. 100 data points per 5 sec?
    assert isinstance(mirror, bool)  # Do we want half the displays to "mirror" the other half? (Used when two composite displays are back-to-back)

    color_method = color_method.strip().lower()
    energy_method = energy_method.strip().lower()

    assert color_method in COLOR_METHODS, f'{color_method} is an unknown colour method.'
    assert energy_method in ENERGY_METHODS, f'{energy_method} is an unknown energy method.'

    data_raw = process_file(file_)  # The raw data from file.
    data_processed = []
    events = []

    if color_method == 'energy':  # Base the colouring on the energy of the detection.

        # Collect the list of DataPoints, accounting for the energy method.
        if energy_method == 'accumulate':
            data_processed += get_energy_accum_data(data_raw)
        elif energy_method == 'tick':
            data_processed += get_energy_tick_data(data_raw)

        # Now turn the DataPoints into events, accounting for the energy method.
        if energy_method == 'accumulate':
            events += get_energy_accum_events(data_processed, displays, color_gradient)
        elif energy_method == 'tick':
            events += get_energy_tick_events(data_processed, displays, color_gradient)

    # Make sure the events are in time order.
    events = sorted(events)

    final_data_point_time = data_processed[-1].start_time

    # Get rid of any events that occur after the file Data Point.
    # This means any pixels with huge counts and thus very long tick away time are just chopped off when the...
    # ... final interesting piece of data has occured.
    events = [event for event in events if event.start_time < final_data_point_time]

    if normalise:
        normalise_events(events)

    # All events at the moment are individual pixel updates.
    # Let's group multiple pixel updates together into a single event, IF they are very close together in time.
    events = group_events(events)

    return events


def normalise_events(events):
    assert isinstance(events, list)
    assert all(isinstance(e, Event) for e in events)

    minimum = min([event.start_time for event in events])
    difference = max([event.start_time for event in events]) - minimum

    num_data_points = len(events)
    factor = 5.0 * float(num_data_points) / 500.0

    for event in events:
        event.start_time = factor * (event.start_time - minimum) / difference


def process_file(file_):
    assert isinstance(file_, str)

    data = loadtxt(file_, delimiter=',')

    assert len(data.shape) == 2, 'Need more than 1 data point.'  # Dealing with numpy's awkward shape size.
    assert data.shape[0] > 0, f'No data in file {file_}.'
    assert data.shape[1] == 6, 'Number of columns of data should be 6.'

    # We need four pieces of data: the initial photon hits on each detector, and
    # the two hits from those photons scattering
    assert data.shape[0] % 4 == 0, 'We require 4 pieces of data for each event.'

    # Extract the time, crystal ID, detector side, x, y and energy from the data
    # as tuples
    time, ID, side, x, y, energy = zip(*data)

    # Convert the tuples to lists
    time = list(map(float, time))
    ID = list(map(int, ID))
    side = list(map(int, side))
    x = list(map(int, x))  # NB lowercase x refers to the pixel coordinate in (16,16)
    y = list(map(int, y))  # NB lowercase y refers to the pixel coordinate in (16,16)
    energy = list(map(float, energy))

    assert all(t >= 0.0 for t in time), 'Data point with time < 0.'
    assert all(s >= 0 for s in side), 'Data point with side < 0.'
    assert all(x_i >= 0 for x_i in x), 'Data point with x pixel < 0.'
    assert all(y_i >= 0 for y_i in y), 'Data point with y pixel < 0.'
    #assert all(e >= 0.0 for e in energy), 'Data point with energy < 0.'  # TODO: include?

    energy = [1.0 for _ in energy]  # TODO: add mode for this.

    return list(zip(time, ID, x, y, side, energy))  # Note: we have put side to the right of (x, y) rather than the left.


def group_events(events):
    ''' Group events together that occur within the EVENT_TIME_DIFFERENCE_TOLERANCE. '''

    assert all(isinstance(e, Event) for e in events)

    grouped_events = []

    n = 0  # Manual counter, so we can avoid already-processed events.

    while n < len(events):

        m = n

        while (m + 1) < len(events) and (events[m+1].start_time - events[n].start_time) < EVENT_TIME_DIFFERENCE_TOLERANCE:
            m += 1

        x_values, y_values, colors, display_IDs = [], [], [], []

        for i in range(n,m+1):
            x_values += events[i].x_values
            y_values += events[i].y_values
            colors += events[i].colors
            display_IDs += events[i].display_IDs

        grouped_events.append(Event(x_values, y_values, colors, display_IDs, events[n].start_time))

        n = m + 1

    return grouped_events


def get_energy_accum_data(data_raw):
    ''' Takes in the raw data, and returns the organised data points. This initially
        gets the data points with their own energy. It then ensures the data is sorted
        and the energies of the pixels updated to be accumulative. '''

    data_processed = []

    for t, ID, x, y, s, e in data_raw:  # time, crystal_ID, x, y, side, energy.
        data_processed.append(DataPoint(x, y, s, e, start_time=t))

    data_processed = sorted(data_processed)  # Sorted based on start_time.

    # We need to make the energy of the data point equal to itself plus the previous energy of the pixel.
    # If there are no hits of the pixel before data point, then its energy is left unchanged.
    for n, dA in enumerate(data_processed):  # d for data point.

        # We ignore the first data point as this will never need its energy updated.
        if n == 0:
            continue

        # Only bother look at data points before the currently considered one **in reverse**.
        for dB in data_processed[n-1::-1]:

            # We're looking for data points that hit the same pixel.
            if (dA.side == dB.side) and (dA.x == dB.x) and (dA.y == dB.y):

                # Both data points hit the same pixel. The energy of dA should be itself plus dB.
                dA.energy += dB.energy

                # Don't want to add any energies, as we would be double counting.
                break

    return data_processed


def get_energy_tick_data(data_raw, energy_tick_rate=ENERGY_TICK_RATE_DEFAULT, gradient_delay=GRADIENT_DELAY):
    ''' Takes in the raw data, and returns the organised data points. This initially
        gets the number of ticks and thus the alight-time of the data point. It then
        also carefully checks if any of the data points overlap in time and thus need
        to be merged. '''

    data_processed = []

    for t, ID, x, y, s, e in data_raw:  # time, crystal_ID, x, y, side, energy.
        num_ticks = get_num_ticks(e, energy_tick_rate)  # *** Number of ticks this pixel has is based on the energy. ***
        alight_time = get_quantity(num_ticks, gradient_delay)  # How long should this pixel be lit up for?

        data_processed.append(DataPoint(x, y, s, e, energy_tick_rate, num_ticks, start_time=t, end_time=t+alight_time))

    data_processed = sorted(data_processed)  # Sorted based on start_time.

    # We need to make sure that any hits on pixels that are already lit up do not overwrite, but instead add, energy to the pixel.
    for n, dA in tqdm(enumerate(data_processed), desc="Processing tick data"):  # d for data point.

        # Only bother looking at data points ahead of the currently considered one.
        for dB in data_processed[n+1:]:
            # Data is sorted in time, so if event B starts after A has "ticked away" then no later events
            # need to be checked
            if dB.start_time > dA.end_time:
                break

            # We're looking for data points that hit the same pixel and iB starts before the end of iA.
            if (dA.side == dB.side) and (dA.x == dB.x) and (dA.y == dB.y):

                # An event, dB, occurs within the time frame that dA is still alight.

                # Therefore, we erase the ticks of the initial iA event that would occur after iB has started.
                # This includes remove the final background colour tick of iA, which iB will now deal with.
                dA.ticks -= get_num_ticks(dA.end_time-dB.start_time, gradient_delay)

                # The initial iA event end time is now equal to the latter iB event start time.
                dA.end_time = dB.start_time

                # The energy of the latter iB event will be itself plus |the energy of the initial iA event minus the amount it has decayed by|.
                dB.energy += dA.energy - dA.ticks * energy_tick_rate

                # Now re-compute the (greater) number of ticks and the (later) end time for the latter iB event.
                dB.ticks = get_num_ticks(dB.energy, energy_tick_rate)  # *** Number of ticks this pixel has is based on the energy. ***
                dB.end_time = dB.start_time + get_quantity(dB.ticks, gradient_delay)  # Start time + alight time.

                # If dA overlaps with a dC, this will be dealt with by dB, so may as well break here to save time.
                break

    return data_processed


def get_energy_accum_events(data_points, displays, color_gradient=COLOR_GRADIENT_DEFAULT):
    ''' get_energy_accum_data should be used before this to obtain the data_points. '''
    ''' This takes a DataPoint and creates the associated events based on the energy,
        given the energy_method is accumulate. This is just one event per data point. '''

    events = []
    for data_point in data_points:
        color = COLOR_DEFAULT if data_point.energy <= 0.0 else get_color_from_gradient(data_point.energy, color_gradient,len(data_points))

        display_ID = get_display_ID(displays, data_point.x, data_point.y, data_point.side)

        x = data_point.x % displays[display_ID].size  # Turns global x into local.
        y = data_point.y % displays[display_ID].size  # Turns global y into local.

        events.append(Event([x], [y], [color], [display_ID], data_point.start_time))  # x, y, color, ID are lists.

    # Add an extra event at the end so the display doesn't vanish immediately.
    if len(events) > 0:
        e = events[-1]
        events.append(Event(e.x_values, e.y_values, e.colors, e.display_IDs, e.start_time+1.0))  # 1 second later.

    return events


def get_energy_tick_events(data_points, displays, color_gradient=COLOR_GRADIENT_DEFAULT):
    ''' get_energy_tick_data should be used before this to obtain the data_points. '''
    ''' This takes a DataPoint and creates the associated events based on the energy, given the energy_method
        is ticks. For example, if a data point is a pixel light-up with 13eV, then if the energy_tick_rate is
        5eV, then the events will be a 13eV colour, 8eV colour `gradient_delay` seconds later, 3 eV colour
        `gradient_delay` seconds later, 0 eV (blank) colour `gradient_delay` seconds later. '''

    events = []

    print("Total points ",len(data_points))

    for data_point in tqdm(data_points, desc="Processing tick events"):
        for tick in range(data_point.ticks+1):
            energy = data_point.energy - tick * data_point.energy_tick_rate

            color = COLOR_DEFAULT if energy <= 0.0 else get_color_from_gradient(energy, color_gradient,len(data_points))

            display_ID, mirror_ID = get_display_ID(displays, data_point.x, data_point.y, data_point.side)

            # If this side or pixel don't map to a display, we ignore it

            if display_ID >= 0:
                x = data_point.x % displays[display_ID].size  # Turns global x into local.
                y = data_point.y % displays[display_ID].size  # Turns global y into local.

                events.append(Event([x], [y], [color], [display_ID], data_point.start_time+tick*data_point.gradient_delay))  # x, y, color, ID are lists.

            if mirror_ID >= 0:
                x = displays[mirror_ID].size - 1 - data_point.x % displays[mirror_ID].size  # Turns global x into local and *mirrors*
                y = data_point.y % displays[mirror_ID].size  # Turns global y into local.

                events.append(Event([x], [y], [color], [mirror_ID], data_point.start_time+tick*data_point.gradient_delay))  # x, y, color, ID are lists.

    return events


def store_data(data, _file='example'):
    ''' Function to store preprocessed event data in a file for displaying later'''

    print(f"Dumping processed data to file: {_file}" )
    # Dump data to file
    with open(_file, 'ab') as dbfile:
        pickle_dump(data, dbfile) # source, destination
    print('Done')
    return

def load_data(_file='example'):
    ''' Function to load preprocessed event data from file for displaying.'''

    print(f"Loading processed data from file: {_file}" )
    with open(_file, 'rb') as dbfile:
        data = pickle_load(dbfile)
    print('Done')

    return data


class DataPoint:
    def __init__(self, x, y, side=0, energy=0.0, energy_tick_rate=ENERGY_TICK_RATE_DEFAULT,
                 ticks=0, gradient_delay=GRADIENT_DELAY, start_time=0.0, end_time=inf):
        assert isinstance(x, int)
        assert isinstance(y, int)
        assert isinstance(side, int)
        assert isinstance(energy, (float, int))
        assert isinstance(energy_tick_rate, (float, int))
        assert isinstance(ticks, int)
        assert isinstance(gradient_delay, (float, int))
        assert isinstance(start_time, (float, int))
        assert isinstance(end_time, (float, int))

        self.x = x  # This is the global x co-ordinate.
        self.y = y  # This is the global y co-ordinate.
        self.side = side
        self.energy = energy
        self.energy_tick_rate = energy_tick_rate
        self.ticks = ticks  # With the given energy, how many `GRADIENT_DELAY` ticks will occur until the pixel is DEFAULT_COLOR again?
        self.gradient_delay = gradient_delay
        self.start_time = start_time
        self.end_time = end_time

    def __lt__(self, other):
        return self.start_time < other.start_time

    def __repr__(self):
        return f'({self.x},{self.y})  {self.energy:6.2f}  {self.start_time:6.2f}'


class Event:
    def __init__(self, x_values, y_values, colors, display_IDs, start_time=0.0):
        assert all(isinstance(x, int) for x in x_values)
        assert all(isinstance(y, int) for y in y_values)
        assert all(isinstance(color, int) for color in colors)
        assert all(isinstance(ID, int) for ID in display_IDs)
        assert all(255 >= color >= 0 for color in colors)
        assert isinstance(start_time, (float, int))

        self.x_values = x_values  # These are the local x co-ordinates.
        self.y_values = y_values  # These are the local y co-ordinates.
        self.colors = colors
        self.display_IDs = display_IDs
        self.start_time = start_time

    def __iter__(self):
        return iter(zip(self.x_values, self.y_values, self.colors, self.display_IDs))

    def __lt__(self, other):
        return self.start_time < other.start_time

    def __repr__(self):
        s = ''

        for x, y, color, display_ID in self:
            s += f'({x},{y})  {color}  {self.start_time:6.2f}\n'

        return s[:-1]
